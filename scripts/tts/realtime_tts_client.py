# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
import asyncio
import base64
import json
import logging
import os
import sys
import signal
from types import NoneType
import uuid
import wave
from pathlib import Path
from typing import Dict, Any, Optional, List

import requests
import ssl
import websockets
from websockets.exceptions import WebSocketException

from riva.client.argparse_utils import add_connection_argparse_parameters
from riva.client.audio_io import SoundCallBack

from riva.client.realtime import RealtimeClientTTS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def read_file_to_dict(file_path):
    """Read a file and parse it into a dictionary with key-value pairs separated by double spaces."""
    result_dict = {}
    with open(file_path, 'r') as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            try:
                key, value = line.split('  ', 1)  # Split by double space
                result_dict[str(key.strip())] = str(value.strip())
            except ValueError:
                print(f"Warning: Malformed line {line}")
                continue
    if not result_dict:
        raise ValueError("Error: No valid entries found in the file.")
    return result_dict

def parse_args() -> argparse.Namespace:
    """Parse command line arguments for the realtime TTS client."""
    parser = argparse.ArgumentParser(
        description=(
            "Realtime text-to-speech client that connects to a Riva AI TTS WebSocket server. "
            "This script supports text input from files. "
            "The script connects to a WebSocket server and streams text data in real-time, "
            "receiving synthesized speech audio as it becomes available. "
            "Audio output can be played directly or saved to files."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Input configuration
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--text",
        help="Direct text input to synthesize"
    )
    input_group.add_argument(
        "--list-devices",
        action="store_true",
        help="List output audio devices indices."
    )
    input_group.add_argument(
        "--list-voices",
        action="store_true",
        help="List available voices."
    )
    input_group.add_argument(
        "--input-file",
        help="Input file to synthesize"
    )

    # TTS Configuration
    parser.add_argument(
        "--language-code",
        default="en-US",
        help="Language code for synthesis (e.g., 'en-US', 'es-ES')"
    )
    parser.add_argument(
        "--voice",
        default="",
        help="A voice name to use. If this parameter is missing, then the server will try a first available model "
        "based on parameter `--language-code`."
    )
    parser.add_argument(
        "--sample-rate-hz",
        type=int,
        default=44100,
        help="Output audio sample rate in Hz"
    )
    parser.add_argument(
        "--encoding",
        default="LINEAR_PCM",
        choices={"LINEAR_PCM", "OGGOPUS"},
        help="Output audio encoding, only LINEAR_PCM and OGGOPUS are supported."
    )
    parser.add_argument(
        "--custom-dictionary",
        default="",
        help="Path to a file containing custom dictionary entries. Each line should contain "
             "grapheme and corresponding phoneme separated by double spaces."
    )

    # Zero-shot voice cloning
    parser.add_argument(
        "--zero-shot-audio-prompt-file",
        help="Audio prompt file for zero-shot voice cloning (3-10 seconds)"
    )
    parser.add_argument(
        "--zero-shot-audio-prompt-transcript",
        default="",
        help="Transcript of the zero-shot audio prompt"
    )
    parser.add_argument(
        "--zero-shot-prompt-quality",
        type=int,
        default=20,
        help="Quality setting for zero-shot (1-40)"
    )

    parser.add_argument(
        "--exaggeration-factor",
        type=float,
        default=1.0,
        help="Exaggeration factor for generated voice."
    )
    # Output configuration
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default="",
        help="Output file to write synthesized audio. For single requests, uses the filename as-is. For parallel requests, uses as prefix (e.g., 'output.wav' becomes 'output_0.wav', 'output_1.wav', etc.). If not specified, no audio file will be saved."
    )
    parser.add_argument(
        "--play-audio",
        action="store_true",
        help="Play audio output in real-time. Audio will be played regardless of whether an output file is specified."
    )

    # Add connection parameters
    parser = add_connection_argparse_parameters(parser)

    # Override default server for realtime TTS (WebSocket endpoint, not gRPC)
    parser.set_defaults(server="localhost:9000")
    parser.set_defaults(endpoint="/v1/realtime")
    parser.set_defaults(query_params="intent=synthesize")

    # Add debug option
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    # Parallel processing option
    parser.add_argument(
        "--num-parallel-requests",
        type=int,
        default=1,
        help="Number of parallel requests to process simultaneously (default: 1)"
    )

    args = parser.parse_args()
    
    # Validate num_parallel_requests
    if args.num_parallel_requests < 1:
        parser.error("--num-parallel-requests must be a positive integer")
    
    return args

def setup_signal_handler():
    """Set up signal handler for graceful shutdown."""
    def signal_handler(sig, frame):
        print("Interrupt received, stopping...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)


async def get_text_input_generator(args, text_lines=None):
    """Generator that yields text input line by line based on the specified mode."""
    if text_lines is not None:
        # For parallel processing, yield from provided text lines
        for line in text_lines:
            line = line.strip()
            if line:  # Only yield non-empty lines
                yield line
                yield None
    elif args.text:
        # Split text by lines and yield each line
        for line in args.text.split('\n'):
            line = line.strip()
            if line:  # Only yield non-empty lines
                yield line
                yield None
    elif args.input_file:
        try:
            with open(args.input_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:  # Only yield non-empty lines
                        yield line
                    else: 
                        yield None
        except Exception as e:
            logger.error("Error reading input text file: %s", e)
            raise
    else:
        raise ValueError("No input method specified")

def read_text_file(file_path: str) -> List[str]:
    """Read text file and return list of non-empty lines.
    
    Supports two formats:
    1. Plain text file: each line is text to synthesize
    2. Pipe-separated file: each line is "id|text_to_synthesize"
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = []
            for line in f:
                line = line.strip()
                if line:
                    # Check if line contains pipe separator (format: audio_path|text)
                    if '|' in line:
                        # Extract text part after the pipe
                        text_part = line.split('|', 1)[1].strip()
                        if text_part:  # Only add non-empty text
                            lines.append(text_part)
                    else:
                        # Plain text line
                        lines.append(line)
        
        logger.info(f"Read {len(lines)} text lines from {file_path}")
        return lines
    except Exception as e:
        logger.error(f"Error reading text file {file_path}: {e}")
        raise

def init_wav_file(output_file: str, sample_rate_hz: int):
    if not output_file or not output_file.strip():
        return
        
    # Validate that output_file is not a directory
    if os.path.isdir(output_file):
        logger.error("Output file path is a directory: %s", output_file)
        raise ValueError(f"Output file path is a directory: {output_file}")
        
    try:
        # Ensure the output directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            logger.info("Created output directory: %s", output_dir)
        
        nchannels = 1
        sampwidth = 2

        out_f = wave.open(output_file, 'wb')
        
        out_f.setnchannels(nchannels)
        out_f.setsampwidth(sampwidth)
        out_f.setframerate(sample_rate_hz)
        
        logger.info("WAV file initialized for streaming write: %s", output_file)
        logger.info("  Sample Rate: %d Hz", sample_rate_hz)
        logger.info("  Channels: %d", nchannels)
        logger.info("  Sample Width: %d bytes (16-bit)", sampwidth)
        
        return out_f
    
    except Exception as e:
        logger.error("Error initializing WAV file %s: %s", output_file, e)
        raise

def write_audio_chunk(out_f, audio_chunks):
    if out_f is not None and audio_chunks is not None:
        try:
            for data in audio_chunks:
                out_f.writeframesraw(data)
        except Exception as e:
            logger.error("Error writing audio chunk: %s", e)

def close_wav_file(out_f):
    if out_f is not None:
        try:
            out_f.close()
            out_f = None
            logger.info("WAV file closed successfully")
        except Exception as e:
            logger.error("Error closing WAV file: %s", e)

def play_audio(audio_chunks, sample_rate_hz, nchannels=1, sampwidth=2):
    """Play audio chunk in real-time."""
    if audio_chunks is not None:
        try:
            import pyaudio
            
            # Initialize PyAudio
            p = pyaudio.PyAudio()
            
            # Create audio stream
            stream = p.open(
                format=pyaudio.paInt16,
                channels=nchannels,
                rate=sample_rate_hz,
                output=True
            )
            
            # Concatenate all audio chunks into a single byte string
            audio_data = b''.join(audio_chunks)
            
            # Play audio data
            stream.write(audio_data)
            
            # Clean up
            stream.stop_stream()
            stream.close()
            p.terminate()
            
        except ImportError:
            logger.warning("PyAudio not available for real-time playback")
        except Exception as e:
            logger.error("Error playing audio: %s", e)

async def run_synthesis(args, client_id: int = None, text_lines: List[str] = None, output_file: str = None):
    """Run the text-to-speech synthesis process."""
    # Process custom dictionary if provided
    if args.custom_dictionary and str(args.custom_dictionary).strip():
        try:
            custom_dict = read_file_to_dict(args.custom_dictionary)
            custom_dict_string = ','.join([f"{key}  {value}" for key, value in custom_dict.items()])
            args.custom_dictionary = custom_dict_string
        except Exception as e:
            logger.error(f"Error reading custom dictionary file {args.custom_dictionary}: {e}")
            args.custom_dictionary = ""
    
    client = RealtimeClientTTS(args=args)
    send_task = None
    receive_task = None
    text_generator = get_text_input_generator(args, text_lines)
    audio_chunks = []
    success = False
    
    await client.connect()
    
    try:
        out_f = None
        
        # Determine output file
        if output_file:
            out_f = init_wav_file(output_file, args.sample_rate_hz)
        elif args.output and str(args.output).strip() and not os.path.isdir(str(args.output)):
            out_f = init_wav_file(str(args.output), args.sample_rate_hz)

        # Run send and receive tasks concurrently
        send_task = asyncio.create_task(
            client.send_text(text_generator)
        )
        receive_task = asyncio.create_task(
            client.receive_audio(audio_chunks)
        )

        await asyncio.gather(send_task, receive_task)
        success = not client.error_occurred

        if out_f:
            write_audio_chunk(out_f, audio_chunks)
        if args.play_audio:
            play_audio(audio_chunks, args.sample_rate_hz)
        
        audio_chunks = None
        
        if client_id:
            logger.info(f"Client {client_id}: Synthesis completed successfully")
        else:
            logger.info("Synthesis completed successfully")
        
    except KeyboardInterrupt:
        if client_id:
            logger.info(f"Client {client_id}: Synthesis interrupted by user")
        else:
            logger.info("Synthesis interrupted by user")
        success = False

        # Cancel the receive task
        if receive_task and not receive_task.done():
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass

        # Save partial audio if available
        if (output_file or args.output) and audio_chunks:
            if client_id:
                logger.info(f"Client {client_id}: Saving partial audio due to interruption")
            else:
                logger.info("Saving partial audio due to interruption")
            write_audio_chunk(out_f, audio_chunks)

    except Exception as e:
        if client_id:
            logger.error(f"Client {client_id}: Error during synthesis: %s", e)
        else:
            logger.error("Error during synthesis: %s", e)
        success = False
        raise

    finally:
        close_wav_file(out_f)
        await client.disconnect()
    
    return success

async def run_parallel_synthesis(args):
    """Run multiple parallel TTS synthesis tasks - one WAV file per text line."""
    logger.info(f"Starting parallel synthesis with {args.num_parallel_requests} concurrent workers")
    
    # Read input text
    if args.input_file:
        text_lines = read_text_file(args.input_file)
    elif args.text:
        text_lines = [line.strip() for line in args.text.split('\n') if line.strip()]
    else:
        raise ValueError("No input method specified for parallel processing")
    
    if not text_lines:
        raise ValueError("No text lines found for parallel processing")
    
    logger.info(f"Processing {len(text_lines)} text lines into {len(text_lines)} WAV files")
    
    # Create a semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(args.num_parallel_requests)
    
    async def process_single_text(text_idx, text_line):
        """Process a single text line with concurrency control."""
        async with semaphore:
            # Create output file for this specific text line
            output_file = None
            if args.output and str(args.output).strip() and not os.path.isdir(str(args.output)):
                output_path = Path(args.output)
                output_file = str(output_path.parent / f"{output_path.stem}{text_idx}{output_path.suffix}")
            
            logger.info(f"Processing text {text_idx + 1}/{len(text_lines)}: {text_line[:50]}...")
            return await run_synthesis(args, client_id=text_idx + 1, text_lines=[text_line], output_file=output_file)
    
    # Create tasks for each text line
    tasks = []
    for i, text_line in enumerate(text_lines):
        task = asyncio.create_task(process_single_text(i, text_line))
        tasks.append(task)
    
    # Run all tasks concurrently (limited by semaphore)
    logger.info(f"Launching {len(text_lines)} synthesis tasks with {args.num_parallel_requests} concurrent workers...")
    start_time = asyncio.get_event_loop().time()
    
    try:
        results = await asyncio.gather(*tasks)
        total_time = asyncio.get_event_loop().time() - start_time
        logger.info(f"All {len(text_lines)} synthesis tasks completed in {total_time:.2f}s")
        return all(results)  # Return True if all tasks succeeded
    except Exception as e:
        logger.error(f"Error in parallel synthesis: %s", e)
        return False


async def main() -> int:
    """Main entry point for the realtime TTS client."""
    args = parse_args()
    success = False
    setup_signal_handler()

    try:
        if args.list_voices:
            voices = RealtimeClientTTS(args=args).list_voices()
            print(json.dumps(voices, indent=4))
        elif args.list_devices:
            import riva.client.audio_io
            riva.client.audio_io.list_output_devices()
        else:
            # Use parallel processing if num_parallel_requests > 1
            if args.num_parallel_requests > 1:
                logger.info(f"Using parallel processing mode with {args.num_parallel_requests} concurrent requests")
                success = await run_parallel_synthesis(args)
            else:
                logger.info("Using single request mode")
                success = await run_synthesis(args)
        return 0 if success else 1
    except Exception as e:
        logger.error("Fatal error: %s", e)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
