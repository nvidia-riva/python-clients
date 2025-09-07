# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
import asyncio
import base64
import json
import logging
import os
import signal
import sys
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
        help="A string containing comma-separated key-value pairs of "
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

    # Output configuration
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default="output.wav",
        help="Output file .wav file to write synthesized audio."
    )
    parser.add_argument(
        "--play-audio",
        action="store_true",
        help="Play audio output in real-time. If `--output` is specified, then audio is played in real-time."
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

    args = parser.parse_args()
    return args

def setup_signal_handler():
    """Set up signal handler for graceful shutdown."""
    def signal_handler(sig, frame):
        print("Interrupt received, stopping...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)


async def get_text_input_generator(args):
    """Generator that yields text input line by line based on the specified mode."""
    if args.text:
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

def init_wav_file(output_file: str, sample_rate_hz: int):
    if not output_file:
        return
        
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
    if audio_chunks is not None:
        """Play audio chunk in real-time."""
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
            
            # Play audio data
            stream.write(audio_chunks)
            
            # Clean up
            stream.stop_stream()
            stream.close()
            p.terminate()
            
        except ImportError:
            logger.warning("PyAudio not available for real-time playback")
        except Exception as e:
            logger.error("Error playing audio: %s", e)
            
async def run_synthesis(args):
    """Run the text-to-speech synthesis process."""
    client = RealtimeClientTTS(args=args)
    send_task = None
    receive_task = None
    text_generator = get_text_input_generator(args)
    audio_chunks = []
    
    await client.connect()
    
    try:
        out_f = None
        
        if args.output:
            out_f = init_wav_file(str(args.output), args.sample_rate_hz)

        # Run send and receive tasks concurrently
        send_task = asyncio.create_task(
            client.send_text(text_generator)
        )
        receive_task = asyncio.create_task(
            client.receive_audio(audio_chunks)
        )

        await asyncio.gather(send_task, receive_task)

        if out_f:
            write_audio_chunk(out_f, audio_chunks)
        elif args.play_audio:
            play_audio(audio_chunks, args.sample_rate_hz)
        
        audio_chunks = None
        
    except KeyboardInterrupt:
        logger.info("Synthesis interrupted by user")

        # Cancel the receive task
        if receive_task and not receive_task.done():
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass

        # Save partial audio if available
        if args.output and client.audio_data:
            logger.info("Saving partial audio due to interruption")

    except Exception as e:
        logger.error("Error during synthesis: %s", e)
        raise

    finally:
        close_wav_file(out_f)
        await client.disconnect()


async def main() -> None:
    """Main entry point for the realtime TTS client."""
    args = parse_args()

    setup_signal_handler()

    try:
        if args.list_voices:
            voices = RealtimeClientTTS(args=args).list_voices()
            print(json.dumps(voices, indent=4))
        elif args.list_devices:
            import riva.client.audio_io
            riva.client.audio_io.list_output_devices()
        else:
            await run_synthesis(args)
    except Exception as e:
        logger.error("Fatal error: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
