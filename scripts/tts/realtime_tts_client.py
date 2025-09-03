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
import uuid
import wave
from typing import Dict, Any, Optional, List

import requests
import websockets
import ssl
from websockets.exceptions import WebSocketException

from riva.client.argparse_utils import (
    add_connection_argparse_parameters,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments for the realtime TTS client."""
    parser = argparse.ArgumentParser(
        description=(
            "Realtime text-to-speech client that connects to a Riva AI TTS WebSocket server. "
            "This script supports text input from files or interactive input. "
            "The script connects to a WebSocket server and streams text data in real-time, "
            "receiving synthesized speech audio as it becomes available. "
            "Audio output can be played directly or saved to files."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Input configuration
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input-text",
        help="Input text file to synthesize"
    )
    input_group.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive mode - type text to synthesize"
    )
    input_group.add_argument(
        "--text",
        help="Direct text input to synthesize"
    )
    
    # TTS Configuration
    parser.add_argument(
        "--language-code",
        default="en-US",
        help="Language code for synthesis (e.g., 'en-US', 'es-ES')"
    )
    parser.add_argument(
        "--voice-name",
        default="",
        help="Voice name for synthesis (e.g., 'ljspeech', 'tacotron2')"
    )
    parser.add_argument(
        "--sample-rate-hz",
        type=int,
        default=22050,
        help="Output audio sample rate in Hz"
    )
    parser.add_argument(
        "--num-channels",
        type=int,
        default=1,
        help="Number of audio channels"
    )
    parser.add_argument(
        "--audio-format",
        default="LINEAR_PCM",
        help="Output audio format"
    )
    parser.add_argument(
        "--custom-dictionary",
        default="",
        help="Custom pronunciation dictionary"
    )

    # Zero-shot voice cloning
    parser.add_argument(
        "--zero-shot-audio-prompt",
        help="Audio prompt file for zero-shot voice cloning (3-10 seconds)"
    )
    parser.add_argument(
        "--zero-shot-transcript",
        default="",
        help="Transcript of the zero-shot audio prompt"
    )
    parser.add_argument(
        "--zero-shot-quality",
        type=int,
        default=20,
        help="Quality setting for zero-shot (1-40)"
    )

    # Output configuration
    parser.add_argument(
        "--output-audio",
        help="Output audio file (WAV format)"
    )
    parser.add_argument(
        "--play-audio",
        action="store_true",
        help="Play audio output in real-time"
    )

    # Add connection parameters
    parser = add_connection_argparse_parameters(parser)

    # Override default server for realtime TTS (WebSocket endpoint, not gRPC)
    parser.set_defaults(server="localhost:9090")
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


class RealtimeTTSClient:
    """Client for real-time text-to-speech synthesis via WebSocket connection."""

    def __init__(self, args: argparse.Namespace):
        """Initialize the RealtimeTTSClient.

        Args:
            args: Command line arguments containing configuration
        """
        self.args = args
        self.websocket = None
        self.session_config = None
        self.audio_data = []
        self.is_synthesis_complete = False
        self.wav_file = None  # WAV file handle for streaming write

    def _init_wav_file(self, output_file: str):
        """Initialize WAV file for streaming write, following talk.py pattern.
        
        Args:
            output_file: Path to the output WAV file
        """
        if not output_file:
            return
            
        try:
            # Ensure the output directory exists
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                logger.info("Created output directory: %s", output_dir)
            
            # Open WAV file for writing, following talk.py pattern
            self.wav_file = wave.open(output_file, 'wb')
            self.wav_file.setnchannels(self.args.num_channels)
            self.wav_file.setsampwidth(2)  # 16-bit audio (2 bytes), same as talk.py
            self.wav_file.setframerate(self.args.sample_rate_hz)
            
            logger.info("WAV file initialized for streaming write: %s", output_file)
            logger.info("  Sample Rate: %d Hz", self.args.sample_rate_hz)
            logger.info("  Channels: %d", self.args.num_channels)
            logger.info("  Sample Width: 2 bytes (16-bit)")
            
        except Exception as e:
            logger.error("Error initializing WAV file %s: %s", output_file, e)
            raise

    def _write_audio_chunk(self, audio_data: bytes):
        """Write audio chunk to WAV file, following talk.py pattern.
        
        Args:
            audio_data: Raw audio data bytes
        """
        if self.wav_file is not None:
            try:
                self.wav_file.writeframesraw(audio_data)
            except Exception as e:
                logger.error("Error writing audio chunk: %s", e)

    def _close_wav_file(self):
        """Close WAV file, following talk.py pattern."""
        if self.wav_file is not None:
            try:
                self.wav_file.close()
                self.wav_file = None
                logger.info("WAV file closed successfully")
            except Exception as e:
                logger.error("Error closing WAV file: %s", e)

    async def connect(self):
        """Establish connection to the TTS server."""
        try:
            logger.info("Starting connection to TTS server...")
            
            # Initialize session via HTTP POST
            logger.info("Initializing HTTP session...")
            session_data = await self._initialize_http_session()
            self.session_config = session_data
            logger.info("HTTP session initialized successfully")

            # Connect to WebSocket
            logger.info("Connecting to WebSocket...")
            await self._connect_websocket()
            logger.info("WebSocket connected successfully")
            
            # Initialize WebSocket session
            logger.info("Initializing WebSocket session...")
            await self._update_session()
            logger.info("WebSocket session initialized successfully")
            
            logger.info("Connection established successfully!")

        except requests.exceptions.RequestException as e:
            logger.error("HTTP request failed: %s", e)
            raise
        except WebSocketException as e:
            logger.error("WebSocket connection failed: %s", e)
            raise
        except Exception as e:
            logger.error("Unexpected error during connection: %s", e)
            raise

    async def _initialize_http_session(self) -> Dict[str, Any]:
        """Initialize session via HTTP POST request."""
        headers = {"Content-Type": "application/json"}
        uri = f"http://{self.args.server}/v1/realtime/synthesis_sessions"
        if self.args.use_ssl:
            uri = f"https://{self.args.server}/v1/realtime/synthesis_sessions"
        
        logger.info("Initializing session via HTTP POST request to: %s", uri)
        
        # Prepare session configuration
        session_config = {
            "input_text_synthesis": {
                "language_code": self.args.language_code,
                "voice_name": self.args.voice_name,
            },
            "output_audio_params": {
                "sample_rate_hz": self.args.sample_rate_hz,
                "num_channels": self.args.num_channels,
                "audio_format": self.args.audio_format
            },
            "custom_dictionary": self.args.custom_dictionary,
            "zero_shot_config": {
                "audio_prompt_bytes": "",
                "audio_prompt_transcript": self.args.zero_shot_transcript,
                "prompt_quality": self.args.zero_shot_quality,
                "prompt_encoding": "LINEAR_PCM",
            }
        }

        # Add zero-shot audio prompt if provided
        if self.args.zero_shot_audio_prompt:
            try:
                with open(self.args.zero_shot_audio_prompt, 'rb') as f:
                    audio_data = f.read()
                    session_config["zero_shot_config"]["audio_prompt_bytes"] = base64.b64encode(audio_data).decode('utf-8')
            except Exception as e:
                logger.warning("Failed to load zero-shot audio prompt: %s", e)

        # Make HTTP request with proper error handling
        try:
            response = requests.post(
                uri,
                headers=headers,
                json=session_config,
                cert=(self.args.ssl_client_cert, self.args.ssl_client_key) if self.args.ssl_client_cert and self.args.ssl_client_key else None,
                verify=self.args.ssl_root_cert if self.args.ssl_root_cert else True,
                timeout=30  # Add timeout to prevent hanging
            )
            
        except requests.exceptions.Timeout:
            logger.error("Request timeout - server not responding")
            raise Exception("Server timeout - check if TTS server is running")
        except requests.exceptions.ConnectionError:
            logger.error("Connection error - cannot reach server")
            raise Exception("Connection failed - check server address and port")
        except Exception as e:
            logger.error("HTTP request failed: %s", e)
            raise

        if response.status_code != 200:
            raise Exception(
                f"Failed to initialize session. Status: {response.status_code}, "
                f"Error: {response.text}"
            )

        session_data = response.json()
        logger.info("Session initialized: %s", session_data)
        return session_data

    async def _connect_websocket(self):
        """Connect to WebSocket endpoint."""
        ssl_context = None
        ws_url = f"ws://{self.args.server}{self.args.endpoint}?{self.args.query_params}"
        if self.args.use_ssl:
            ws_url = f"wss://{self.args.server}{self.args.endpoint}?{self.args.query_params}"

            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            if self.args.ssl_root_cert:
                ssl_context.load_verify_locations(self.args.ssl_root_cert)
            if self.args.ssl_client_cert and self.args.ssl_client_key:
                ssl_context.load_cert_chain(self.args.ssl_client_cert, self.args.ssl_client_key)
            ssl_context.check_hostname = False

        logger.info("Connecting to WebSocket: %s", ws_url)
        self.websocket = await websockets.connect(ws_url, ssl=ssl_context)

    async def _initialize_session(self):
        """Initialize the WebSocket session."""
        try:
            # Handle first response: "conversation.created"
            response = await self.websocket.recv()
            response_data = json.loads(response)
            logger.info("Session created: %s", response_data)

            event_type = response_data.get("type", "")
            if event_type == "conversation.created":
                logger.info("Conversation created successfully")
            else:
                logger.warning("Unexpected first response type: %s", event_type)

            # Update session configuration
            await self._update_session()

        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response: %s", e)
            raise
        except Exception as e:
            logger.error("Unexpected error during session initialization: %s", e)
            raise

    async def _update_session(self):
        """Update session configuration."""
        logger.info("Updating session configuration...")

        # Create session update request
        session_config = {
            "input_text_synthesis": {
                "language_code": self.args.language_code,
                "voice_name": self.args.voice_name,
            },
            "output_audio_params": {
                "sample_rate_hz": self.args.sample_rate_hz,
                "num_channels": self.args.num_channels,
                "audio_format": self.args.audio_format
            },
            "custom_dictionary": self.args.custom_dictionary,
            "zero_shot_config": {
                "audio_prompt_bytes": "",
                "audio_prompt_transcript": self.args.zero_shot_transcript,
                "prompt_quality": self.args.zero_shot_quality,
                "prompt_encoding": "LINEAR_PCM",
            }
        }

        # Add zero-shot audio prompt if provided
        if self.args.zero_shot_audio_prompt:
            try:
                with open(self.args.zero_shot_audio_prompt, 'rb') as f:
                    audio_data = f.read()
                    session_config["zero_shot_config"]["audio_prompt_bytes"] = base64.b64encode(audio_data).decode('utf-8')
            except Exception as e:
                logger.warning("Failed to load zero-shot audio prompt: %s", e)

        update_request = {
            "event_id": f"event_{uuid.uuid4()}",
            "type": "synthesize_session.update",
            "session": session_config
        }

        await self._send_message(update_request)

        # Handle response
        response = await self.websocket.recv()
        response_data = json.loads(response)
        logger.info("Session updated: %s", response_data)

        event_type = response_data.get("type", "")
        if event_type == "synthesize_session.updated":
            logger.info("Synthesis session updated successfully")
            self.session_config = response_data["session"]
            return True
        else:
            logger.warning("Unexpected response type: %s", event_type)
            return False

    async def _send_message(self, message: Dict[str, Any]):
        """Send a JSON message to the WebSocket server."""
        await self.websocket.send(json.dumps(message))

    async def send_text(self, text: str):
        """Send text to the server for synthesis."""
        logger.info("Sending text for synthesis...")

        # Send text data
        await self._send_message({
            "event_id": f"event_{uuid.uuid4()}",
            "type": "input_text.append",
            "text": text
        })

        # Commit the text
        await self._send_message({
            "event_id": f"event_{uuid.uuid4()}",
            "type": "input_text.commit"
        })

        logger.info("Text sent and committed")

    async def send_text_done(self):
        """Signal that text input is complete."""
        await self._send_message({
            "event_id": f"event_{uuid.uuid4()}",
            "type": "input_text.done"
        })
        logger.info("Text input marked as done")

    async def receive_audio(self):
        """Receive and process audio responses from the server."""
        logger.info("Listening for audio responses...")
        
        while not self.is_synthesis_complete:
            try:
                response = await asyncio.wait_for(self.websocket.recv(), 10.0)
                event = json.loads(response)
                event_type = event.get("type", "")

                if event_type == "conversation.item.speech.data":
                    # Handle audio data
                    import base64
                    audio_data_b64 = event.get("audio", "")
                    if audio_data_b64:
                        audio_data = base64.b64decode(audio_data_b64)
                        self.audio_data.append(audio_data)
                        
                        # Write audio chunk to WAV file immediately (streaming write)
                        self._write_audio_chunk(audio_data)
                        
                        # Play audio in real-time if requested
                        if self.args.play_audio:
                            await self._play_audio_chunk(audio_data)
                        
                        logger.info("Received audio chunk: %d bytes", len(audio_data))

                elif event_type == "conversation.item.speech.completed":
                    # Handle synthesis completion
                    is_last_result = event.get("is_last_result", False)
                    synthesis_metadata = event.get("synthesis_metadata", {})
                    
                    logger.info("Speech synthesis completed")
                    if synthesis_metadata:
                        logger.info("Synthesis metadata: %s", synthesis_metadata)
                    
                    if is_last_result:
                        self.is_synthesis_complete = True
                        logger.info("All synthesis completed")
                        break

                elif event_type == "error":
                    error_info = event.get("error", {})
                    logger.error("Error: %s", error_info.get("message", "Unknown error"))
                    self.is_synthesis_complete = True
                    break

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("Error receiving audio: %s", e)
                break

    async def _play_audio_chunk(self, audio_data: bytes):
        """Play audio chunk in real-time."""
        try:
            import pyaudio
            
            # Initialize PyAudio
            p = pyaudio.PyAudio()
            
            # Create audio stream
            stream = p.open(
                format=pyaudio.paInt16,
                channels=self.args.num_channels,
                rate=self.args.sample_rate_hz,
                output=True
            )
            
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

    def save_audio(self, output_file: str):
        """Save collected audio data to a WAV file (backup method).
        Note: The main synthesis process uses streaming write for better performance.
        
        Args:
            output_file: Path to the output WAV file
        """
        if not self.audio_data:
            logger.warning("No audio data to save")
            return

        try:
            # Combine all audio chunks
            import base64
            combined_audio = b''.join(self.audio_data)
            
            if not combined_audio:
                logger.warning("No audio data to save (empty audio)")
                return
            
            # Ensure the output directory exists
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                logger.info("Created output directory: %s", output_dir)
            
            # Save as WAV file, following talk.py pattern
            with wave.open(output_file, 'wb') as wav_file:
                wav_file.setnchannels(self.args.num_channels)
                wav_file.setsampwidth(2)  # 16-bit audio (2 bytes), same as talk.py
                wav_file.setframerate(self.args.sample_rate_hz)
                wav_file.writeframes(combined_audio)
            
            # Calculate and log audio statistics
            duration_seconds = len(combined_audio) / (self.args.sample_rate_hz * self.args.num_channels * 2)
            file_size_mb = len(combined_audio) / (1024 * 1024)
            
            logger.info("Audio saved successfully (backup method):")
            logger.info("  File: %s", output_file)
            logger.info("  Duration: %.2f seconds", duration_seconds)
            logger.info("  Size: %.2f MB", file_size_mb)
            logger.info("  Sample Rate: %d Hz", self.args.sample_rate_hz)
            logger.info("  Channels: %d", self.args.num_channels)
            logger.info("  Sample Width: 2 bytes (16-bit)")
            
        except Exception as e:
            logger.error("Error saving audio to %s: %s", output_file, e)
            raise

    def save_audio_with_params(self, output_file: str, sample_rate: int = None, 
                              num_channels: int = None, audio_format: str = None):
        """Save collected audio data to a WAV file with custom parameters.
        
        Args:
            output_file: Path to the output WAV file
            sample_rate: Override sample rate (default: use from args)
            num_channels: Override number of channels (default: use from args)
            audio_format: Override audio format (default: use from args)
        """
        if not self.audio_data:
            logger.warning("No audio data to save")
            return

        try:
            # Use provided parameters or fall back to args
            sr = sample_rate if sample_rate is not None else self.args.sample_rate_hz
            ch = num_channels if num_channels is not None else self.args.num_channels
            fmt = audio_format if audio_format is not None else self.args.audio_format
            
            # Combine all audio chunks
            import base64
            combined_audio = b''.join(self.audio_data)
            
            if not combined_audio:
                logger.warning("No audio data to save (empty audio)")
                return
            
            # Ensure the output directory exists
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                logger.info("Created output directory: %s", output_dir)
            
            # Determine sample width based on audio format
            sample_width = 2  # Default to 16-bit (2 bytes)
            if fmt == "LINEAR_PCM":
                sample_width = 2  # 16-bit
            elif fmt == "ULAW":
                sample_width = 1  # 8-bit
            elif fmt == "ALAW":
                sample_width = 1  # 8-bit
            
            # Save as WAV file
            with wave.open(output_file, 'wb') as wav_file:
                wav_file.setnchannels(ch)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(sr)
                wav_file.writeframes(combined_audio)
            
            # Calculate and log audio statistics
            duration_seconds = len(combined_audio) / (sr * ch * sample_width)
            file_size_mb = len(combined_audio) / (1024 * 1024)
            
            logger.info("Audio saved with custom parameters:")
            logger.info("  File: %s", output_file)
            logger.info("  Duration: %.2f seconds", duration_seconds)
            logger.info("  Size: %.2f MB", file_size_mb)
            logger.info("  Sample Rate: %d Hz", sr)
            logger.info("  Channels: %d", ch)
            logger.info("  Format: %s", fmt)
            
        except Exception as e:
            logger.error("Error saving audio to %s: %s", output_file, e)
            raise

    def get_audio_info(self) -> Dict[str, Any]:
        """Get information about the collected audio data.
        
        Returns:
            Dictionary containing audio information
        """
        if not self.audio_data:
            return {"error": "No audio data available"}
        
        import base64
        combined_audio = b''.join(self.audio_data)
        if not combined_audio:
            return {"error": "Empty audio data"}
        
        sample_width = 2  # Default to 16-bit
        if self.args.audio_format == "LINEAR_PCM":
            sample_width = 2
        elif self.args.audio_format in ["ULAW", "ALAW"]:
            sample_width = 1
        
        duration_seconds = len(combined_audio) / (self.args.sample_rate_hz * self.args.num_channels * sample_width)
        file_size_mb = len(combined_audio) / (1024 * 1024)
        
        return {
            "chunks_count": len(self.audio_data),
            "total_bytes": len(combined_audio),
            "duration_seconds": duration_seconds,
            "file_size_mb": file_size_mb,
            "sample_rate_hz": self.args.sample_rate_hz,
            "num_channels": self.args.num_channels,
            "audio_format": self.args.audio_format,
            "sample_width_bytes": sample_width
        }

    async def disconnect(self):
        """Close the WebSocket connection."""
        if self.websocket:
            await self.websocket.close()


def setup_signal_handler():
    """Set up signal handler for graceful shutdown."""
    def signal_handler(sig, frame):
        print("Interrupt received, stopping...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)


async def get_text_input(args) -> str:
    """Get text input based on the specified mode."""
    if args.text:
        return args.text
    elif args.input_text:
        try:
            with open(args.input_text, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            logger.error("Error reading input text file: %s", e)
            raise
    elif args.interactive:
        print("Interactive mode - Enter text to synthesize (press Ctrl+C to exit):")
        return input("Text: ")
    else:
        raise ValueError("No input method specified")


async def run_synthesis(args):
    """Run the text-to-speech synthesis process."""
    client = RealtimeTTSClient(args=args)
    send_task = None
    receive_task = None

    try:
        # Connect to server
        await client.connect()

        # Initialize WAV file for streaming write if output file specified
        if args.output_audio:
            client._init_wav_file(args.output_audio)

        # Get text input
        text = await get_text_input(args)
        if not text:
            logger.error("No text provided for synthesis")
            return

        logger.info("Synthesizing text: %s", text)

        # Start receiving audio
        receive_task = asyncio.create_task(client.receive_audio())

        # Send text for synthesis
        await client.send_text(text)
        await client.send_text_done()

        # Wait for synthesis to complete
        await receive_task

        # Show audio information
        audio_info = client.get_audio_info()
        if "error" not in audio_info:
            logger.info("Audio synthesis completed successfully!")
            logger.info("Audio chunks received: %d", audio_info["chunks_count"])
            logger.info("Total audio duration: %.2f seconds", audio_info["duration_seconds"])
            if args.output_audio:
                logger.info("Audio saved to: %s", args.output_audio)
        else:
            logger.warning("Could not get audio information: %s", audio_info["error"])
            
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
        if args.output_audio and client.audio_data:
            logger.info("Saving partial audio due to interruption")
        
    except Exception as e:
        logger.error("Error during synthesis: %s", e)
        raise
        
    finally:
        # Close WAV file if it was opened
        client._close_wav_file()
        await client.disconnect()


async def main() -> None:
    """Main entry point for the realtime TTS client."""
    args = parse_args()

    setup_signal_handler()

    try:
        await run_synthesis(args)
    except Exception as e:
        logger.error("Fatal error: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
