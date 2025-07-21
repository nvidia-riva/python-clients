# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
import asyncio
import signal
import sys

from riva.client.audio_io import MicrophoneStream
from riva.client.asr import get_wav_file_parameters, AudioChunkFileIterator
from riva.client.realtime import RealtimeASRClient
from riva.client.argparse_utils import (
    add_asr_config_argparse_parameters,
    add_realtime_config_argparse_parameters,
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
    parser.add_argument(
        "--input-file", 
        required=True, 
        help="Input audio file"
    )
    parser.add_argument(
        "--mic", 
        action="store_true", 
        help="Use microphone input instead of file input", 
        default=False
    )
    parser.add_argument(
        "--duration", 
        type=int, 
        help="Duration in seconds to record from microphone (only used with --mic)", 
        default=None
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
    
    # Add ASR and realtime configuration parameters
    parser = add_asr_config_argparse_parameters(
        parser, 
        max_alternatives=True, 
        profanity_filter=True, 
        word_time_offsets=True
    )
    parser = add_realtime_config_argparse_parameters(parser)
    
    return parser.parse_args()


def setup_signal_handler():
    """Set up signal handler for graceful shutdown."""
    def signal_handler(sig, frame):
        print("Interrupt received, stopping...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)


async def create_audio_iterator(args):
    """Create appropriate audio iterator based on input type."""
    if args.mic:
        audio_chunk_iterator = MicrophoneStream(
            args.sample_rate_hz, 
            args.file_streaming_chunk, 
            device=args.input_device
        )
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
    """Run the transcription process."""
    client = RealtimeASRClient(args=args)
    
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
            
    except Exception as e:
        print(f"Error: {e}")
        raise
    finally:
        await client.disconnect()


async def main() -> None:
    """Main entry point for the realtime ASR client."""
    args = parse_args()
    setup_signal_handler()

    try:
        await run_transcription(args)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
