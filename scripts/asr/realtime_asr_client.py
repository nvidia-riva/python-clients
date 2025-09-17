# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
import asyncio
import signal
import sys

from riva.client.asr import get_wav_file_parameters, AudioChunkFileIterator
from riva.client.realtime import RealtimeClientASR
from riva.client.argparse_utils import (
    add_asr_config_argparse_parameters,
    add_realtime_config_argparse_parameters,
    add_connection_argparse_parameters,
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments for the realtime ASR client."""
    parser = argparse.ArgumentParser(
        description=(
            "Realtime transcription client that connects to a Riva AI ASR WebSocket server. "
            "This script supports two input modes: microphone input for live transcription "
            "or audio file input for offline processing. When using microphone input, "
            "you can specify a recording duration. The script connects to a WebSocket "
            "server and streams audio data in real-time, receiving transcription results "
            "as they become available. Results are saved to output files for both audio and text."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Input configuration
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input-file",
        help="Input audio file"
    )
    input_group.add_argument(
        "--mic",
        action="store_true",
        help="Use microphone input instead of file input"
    )
    input_group.add_argument(
        "--list-devices",
        action="store_true",
        help="List available input audio device indices"
    )
    
    parser.add_argument(
        "--duration",
        type=int,
        help="Duration in seconds to record from microphone (only used with --mic)",
        default=None
    )

    parser.add_argument(
        "--input-device",
        type=int,
        default=None,
        help="Input audio device index to use (only used with --mic). If not specified, will use default device."
    )

    # Audio parameters
    parser.add_argument(
        "--sample-rate-hz",
        type=int,
        help="Number of frames per second in audio streamed from a microphone.",
        default=16000
    )
    parser.add_argument(
        "--num-channels",
        type=int,
        help="Number of audio channels.",
        default=1
    )
    parser.add_argument(
        "--file-streaming-chunk",
        type=int,
        default=1600,
        help="Maximum number of frames in one chunk sent to server."
    )

    # Output configuration
    parser.add_argument(
        "--output-text",
        type=str,
        help="Output text file"
    )
    parser.add_argument(
        "--prompt",
        default="",
        help="Prompt to be used for transcription."
    )

    # Add connection parameters
    parser = add_connection_argparse_parameters(parser)

    # Override default server for realtime ASR (WebSocket endpoint, not gRPC)
    parser.set_defaults(server="localhost:9000")
    
    # Add ASR and realtime configuration parameters
    parser = add_asr_config_argparse_parameters(
        parser,
        max_alternatives=True,
        profanity_filter=True,
        word_time_offsets=True
    )
    parser = add_realtime_config_argparse_parameters(parser)

    args = parser.parse_args()

    return args


def get_default_device_index():
    """Get default audio device index only when needed."""
    try:
        import riva.client.audio_io
        default_device_info = riva.client.audio_io.get_default_input_device_info()
        return None if default_device_info is None else default_device_info['index']
    except ModuleNotFoundError:
        return None

def setup_signal_handler():
    """Set up signal handler for graceful shutdown."""
    def signal_handler(sig, frame):
        print("Interrupt received, stopping...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)


async def create_audio_iterator(args):
    """Create appropriate audio iterator based on input type.

    Args:
        args: Command line arguments containing input configuration

    Returns:
        Audio iterator for streaming audio data
    """
    if args.mic: 
        from riva.client.audio_io import MicrophoneStream

        # Get default device index if not specified
        device_index = args.input_device
        if device_index is None:
            device_index = get_default_device_index()

        mic_stream = MicrophoneStream(
            args.sample_rate_hz, 
            args.file_streaming_chunk, 
            device=device_index
        )
        
        # Initialize the stream (this starts the microphone)
        audio_chunk_iterator = mic_stream.__enter__()
        # Store the stream object for cleanup later
        args._mic_stream = mic_stream
        print("Recording indefinitely (press Ctrl+C to stop gracefully)...")

        class AsyncAudioIterator:
            """Async wrapper for blocking audio iterators to prevent event loop starvation."""
            def __init__(self, audio_iterator):
                self.audio_iterator = audio_iterator
                self._stop_requested = False
                self.chunk_count = 0
            
            def __aiter__(self):
                return self
            
            async def __anext__(self):
                if self._stop_requested:
                    raise StopAsyncIteration
                
                try:
                    # Add timeout to prevent hanging when no audio is available
                    chunk = await asyncio.wait_for(
                        asyncio.to_thread(lambda: next(self.audio_iterator)), 
                        timeout=1.0  # 1 second timeout
                    )
                    self.chunk_count += 1
                    return chunk
                except asyncio.TimeoutError:
                    # Return empty chunk or raise custom exception
                    raise TimeoutError("No audio chunk available within timeout")
                except StopIteration:
                    print(f"Audio iterator exhausted after {self.chunk_count} chunks")
                    raise StopAsyncIteration
                except Exception as e:
                    print(f"Error getting audio chunk #{self.chunk_count + 1}: {e}")
                    raise
            
            def stop(self):
                self._stop_requested = True
        
        # Use async iterator to prevent event loop starvation
        audio_chunk_iterator = AsyncAudioIterator(audio_chunk_iterator)
        args.num_channels = 1
    else:
        wav_parameters = get_wav_file_parameters(args.input_file)
        if wav_parameters is not None:
            args.sample_rate_hz = wav_parameters['framerate']
            args.num_channels = wav_parameters['nchannels']
        audio_chunk_iterator = AudioChunkFileIterator(
            args.input_file,
            args.file_streaming_chunk,
            delay_callback=None
        )

    return audio_chunk_iterator


async def run_transcription(args):
    """Run the transcription process.

    Args:
        args: Command line arguments containing all configuration
    """
    client = RealtimeClientASR(args=args)
    send_task = None
    receive_task = None

    try:
        # Create audio iterator
        audio_chunk_iterator = await create_audio_iterator(args)

        # Connect and start transcription
        await client.connect()

        # Run send and receive tasks concurrently
        send_task = asyncio.create_task(
            client.send_audio_chunks(audio_chunk_iterator)
        )
        receive_task = asyncio.create_task(
            client.receive_responses()
        )

        await asyncio.gather(send_task, receive_task)

        # Save results if output file specified
        if args.output_text:
            client.save_responses(args.output_text)
            
    except KeyboardInterrupt:
        if hasattr(args, '_interruptible_iterator'):
            args._interruptible_iterator.stop()
            print("Audio input stopped")
        
        # Cancel the send task and wait for it to finish
        if send_task and not send_task.done():
            print("Cancelling send task...")
            send_task.cancel()
            try:
                await send_task
            except asyncio.CancelledError:
                pass
            print("Send task cancelled")
        
        # Wait a bit for the receive task to process any remaining audio
        if receive_task and not receive_task.done():
            print("Processing remaining audio...")
            try:
                await asyncio.wait_for(receive_task, timeout=5.0)
                print("Receive task completed")
            except asyncio.TimeoutError:
                print("Receive task timeout, cancelling...")
                receive_task.cancel()
                try:
                    await receive_task
                except asyncio.CancelledError:
                    pass
                print("Receive task cancelled")
        
        print("Transcription stopped gracefully.")
        
    except Exception as e:
        print(f"Error during realtime transcription: {e}")
        raise
        
    finally:
        # Clean up microphone stream if it was created
        if hasattr(args, '_mic_stream') and args._mic_stream is not None:
            try:
                args._mic_stream.close()
                print("Microphone stream closed")
            except Exception as e:
                print(f"Warning: Error closing microphone stream: {e}")
        
        await client.disconnect()


async def main() -> None:
    """Main entry point for the realtime ASR client."""
    args = parse_args()

    # Handle list devices option
    if args.list_devices:
        try:
            import riva.client.audio_io
            riva.client.audio_io.list_input_devices()
        except ModuleNotFoundError:
            print("PyAudio not available. Please install PyAudio to list audio devices.")
        return

    setup_signal_handler()

    try:
        await run_transcription(args)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
