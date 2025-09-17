#!/usr/bin/env python3

import argparse
import asyncio
import base64
import json
import logging
import queue
import uuid
from typing import Dict, Any, Generator

import requests
import websockets
import ssl
from websockets.exceptions import WebSocketException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RealtimeClientASR:
    """Client for real-time transcription via WebSocket connection."""

    def __init__(self, args: argparse.Namespace):
        """Initialize the RealtimeClientASR.

        Args:
            args: Command line arguments containing configuration
        """
        self.args = args
        self.websocket = None
        self.session_config = None

        # Input audio playback
        self.input_audio_queue = queue.Queue()
        self.input_playback_thread = None
        self.is_input_playing = False
        self.input_buffer_size = 1024  # Buffer size for input audio playback
        self.final_transcript: str = ""
        self.is_config_updated = False


    async def connect(self):
        """Establish connection to the ASR server."""
        try:
            # Initialize session via HTTP POST
            session_data = await self._initialize_http_session()
            self.session_config = session_data

            # Connect to WebSocket
            await self._connect_websocket()
            await self._initialize_session()

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
        uri = f"http://{self.args.server}/v1/realtime/transcription_sessions"
        if self.args.use_ssl:
            uri = f"https://{self.args.server}/v1/realtime/transcription_sessions"
        logger.debug("Initializing session via HTTP POST request to: %s", uri)
        response = requests.post(
            uri,
            headers=headers,
            json={},
            cert=(self.args.ssl_client_cert, self.args.ssl_client_key) if self.args.ssl_client_cert and self.args.ssl_client_key else None,
            verify=self.args.ssl_root_cert if self.args.ssl_root_cert else True
        )

        if response.status_code != 200:
            raise Exception(
                f"Failed to initialize session. Status: {response.status_code}, "
                f"Error: {response.text}"
            )

        session_data = response.json()
        logger.debug("Session initialized: %s", session_data)
        return session_data

    async def _connect_websocket(self):
        """Connect to WebSocket endpoint."""
        ssl_context = None
        ws_url = f"ws://{self.args.server}{self.args.endpoint}?{self.args.query_params}"
        if self.args.use_ssl:
            ws_url = f"wss://{self.args.server}{self.args.endpoint}?{self.args.query_params}"

            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            # Load a custom CA certificate bundle
            if self.args.ssl_root_cert:
                ssl_context.load_verify_locations(self.args.ssl_root_cert)
            # Load a client certificate and key
            if self.args.ssl_client_cert and self.args.ssl_client_key:
                ssl_context.load_cert_chain(self.args.ssl_client_cert, self.args.ssl_client_key)
            # Disable hostname verification
            ssl_context.check_hostname = False
            # ssl_context.verify_mode = ssl.CERT_REQUIRED

        logger.debug("Connecting to WebSocket: %s", ws_url)
        self.websocket = await websockets.connect(ws_url, ssl=ssl_context)

    async def _initialize_session(self):
        """Initialize the WebSocket session."""
        try:
            # Handle first response: "conversation.created"
            response = await self.websocket.recv()
            response_data = json.loads(response)
            logger.debug("Session created: %s", response_data)

            event_type = response_data.get("type", "")
            if event_type == "conversation.created":
                logger.debug("Conversation created successfully")
                logger.debug("Response structure: %s", list(response_data.keys()))
            else:
                logger.warning("Unexpected first response type: %s", event_type)
                logger.debug("Full response: %s", response_data)

            # Update session configuration
            self.is_config_updated = await self._update_session()
            if not self.is_config_updated:
                logger.error("Failed to update session")
                raise Exception("Failed to update session")

            logger.debug("Session initialization complete")

        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response: %s", e)
            raise
        except KeyError as e:
            logger.error("Missing expected key in response: %s", e)
            raise
        except Exception as e:
            logger.error("Unexpected error during session initialization: %s", e)
            raise

    def _safe_update_config(self, config: Dict[str, Any], key: str, value: Any, section: str = None):
        """Safely update a configuration value, creating the section if it doesn't exist.

        Args:
            config: The configuration dictionary to update
            key: The key to update
            value: The value to set
            section: The section name (e.g., 'input_audio_transcription')
        """
        if section:
            if section not in config:
                config[section] = {}
            config[section][key] = value
            logger.debug("Updated %s.%s = %s", section, key, value)
        else:
            config[key] = value
            logger.debug("Updated %s = %s", key, value)

    async def _update_session(self) -> bool:
        """Update session configuration by selectively overriding server defaults.

        Returns:
            True if session was updated successfully, False otherwise
        """
        logger.debug("Updating session configuration...")
        logger.debug("Server default config: %s", self.session_config)

        # Create a copy of the session config from server defaults
        session_config = self.session_config.copy()

        # Track what we're overriding
        overrides = []
        
        # Check if the input is microphone, then set the encoding to pcm16
        if hasattr(self.args, 'mic') and self.args.mic:
            self._safe_update_config(session_config, "input_audio_format", "pcm16")
            overrides.append("input_audio_format")
        else:
            self._safe_update_config(session_config, "input_audio_format", "none")
            overrides.append("input_audio_format")

        # Update input audio transcription - only override if args are provided
        if hasattr(self.args, 'language_code') and self.args.language_code:
            self._safe_update_config(session_config, "language", self.args.language_code, "input_audio_transcription")
            overrides.append("language")

        if hasattr(self.args, 'model_name') and self.args.model_name:
            self._safe_update_config(session_config, "model", self.args.model_name, "input_audio_transcription")
            overrides.append("model")

        if hasattr(self.args, 'prompt') and self.args.prompt:
            self._safe_update_config(session_config, "prompt", self.args.prompt, "input_audio_transcription")
            overrides.append("prompt")

        # Update input audio parameters - only override if args are provided
        if hasattr(self.args, 'sample_rate_hz') and self.args.sample_rate_hz:
            self._safe_update_config(session_config, "sample_rate_hz", self.args.sample_rate_hz, "input_audio_params")
            overrides.append("sample_rate_hz")

        if hasattr(self.args, 'num_channels') and self.args.num_channels:
            self._safe_update_config(session_config, "num_channels", self.args.num_channels, "input_audio_params")
            overrides.append("num_channels")

        # Update recognition settings - only override if args are provided
        if hasattr(self.args, 'max_alternatives') and self.args.max_alternatives is not None:
            self._safe_update_config(session_config, "max_alternatives", self.args.max_alternatives, "recognition_config")
            overrides.append("max_alternatives")

        if hasattr(self.args, 'automatic_punctuation') and self.args.automatic_punctuation is not None:
            self._safe_update_config(session_config, "enable_automatic_punctuation", self.args.automatic_punctuation, "recognition_config")
            overrides.append("automatic_punctuation")

        if hasattr(self.args, 'word_time_offsets') and self.args.word_time_offsets is not None:
            self._safe_update_config(session_config, "enable_word_time_offsets", self.args.word_time_offsets, "recognition_config")
            overrides.append("word_time_offsets")

        if hasattr(self.args, 'profanity_filter') and self.args.profanity_filter is not None:
            self._safe_update_config(session_config, "enable_profanity_filter", self.args.profanity_filter, "recognition_config")
            overrides.append("profanity_filter")

        if hasattr(self.args, 'no_verbatim_transcripts') and self.args.no_verbatim_transcripts is not None:
            self._safe_update_config(session_config, "enable_verbatim_transcripts", self.args.no_verbatim_transcripts, "recognition_config")
            overrides.append("verbatim_transcripts")

        # Configure speaker diarization if enabled
        if hasattr(self.args, 'speaker_diarization') and self.args.speaker_diarization:
            session_config["speaker_diarization"] = {
                "enable_speaker_diarization": True,
                "max_speaker_count": getattr(self.args, 'diarization_max_speakers', 2)
            }
            overrides.append("speaker_diarization")

        # Configure word boosting if enabled
        if (hasattr(self.args, 'boosted_lm_words') and
            self.args.boosted_lm_words and
            len(self.args.boosted_lm_words)):
            word_boosting_list = [
                {
                    "phrases": self.args.boosted_lm_words,
                    "boost": getattr(self.args, 'boosted_lm_score', 1.0)
                }
            ]
            session_config["word_boosting"] = {
                "enable_word_boosting": True,
                "word_boosting_list": word_boosting_list
            }
            overrides.append("word_boosting")

        # Configure endpointing if any parameters are set
        if self._has_endpointing_config():
            session_config["endpointing_config"] = self._build_endpointing_config()
            overrides.append("endpointing_config")

        # Configure custom configuration if provided
        if hasattr(self.args, 'custom_configuration') and self.args.custom_configuration:
            custom_config = self._parse_custom_configuration(self.args.custom_configuration)
            if custom_config:
                session_config["custom_configuration"] = custom_config
                overrides.append("custom_configuration")

        if overrides:
            logger.debug("Overriding server defaults for: %s", ', '.join(overrides))
        else:
            logger.debug("Using server default configuration (no overrides)")

        logger.debug("Final session config: %s", session_config)

        # Send update request
        update_session_request = {
            "type": "transcription_session.update",
            "session": session_config
        }
        await self._send_message(update_session_request)

        # Handle response
        return await self._handle_session_update_response()

    def _has_endpointing_config(self) -> bool:
        """Check if any endpointing configuration parameters are set."""
        return (
            self.args.start_history > 0 or
            self.args.start_threshold > 0 or
            self.args.stop_history > 0 or
            self.args.stop_history_eou > 0 or
            self.args.stop_threshold > 0 or
            self.args.stop_threshold_eou > 0
        )

    def _build_endpointing_config(self) -> Dict[str, Any]:
        """Build endpointing configuration dictionary."""
        return {
            "start_history": self.args.start_history,
            "start_threshold": self.args.start_threshold,
            "stop_history": self.args.stop_history,
            "stop_threshold": self.args.stop_threshold,
            "stop_history_eou": self.args.stop_history_eou,
            "stop_threshold_eou": self.args.stop_threshold_eou
        }

    def _parse_custom_configuration(self, custom_configuration: str) -> Dict[str, str]:
        """Parse custom configuration string into a dictionary.

        Args:
            custom_configuration: String in format "key1:value1,key2:value2"

        Returns:
            Dictionary of custom configuration key-value pairs

        Raises:
            ValueError: If the custom configuration format is invalid
        """
        custom_config = {}
        custom_configuration = custom_configuration.strip().replace(" ", "")

        if not custom_configuration:
            return custom_config

        for pair in custom_configuration.split(","):
            key_value = pair.split(":")
            if len(key_value) == 2:
                custom_config[key_value[0]] = key_value[1]
            else:
                raise ValueError(f"Invalid key:value pair {key_value}")

        return custom_config

    async def _handle_session_update_response(self) -> bool:
        """Handle session update response.

        Returns:
            True if session was updated successfully, False otherwise
        """
        response = await self.websocket.recv()
        response_data = json.loads(response)
        logger.info("Current Session Config: %s", response_data)

        event_type = response_data.get("type", "")
        if event_type == "transcription_session.updated":
            logger.debug("Transcription session updated successfully")
            logger.debug("Response structure: %s", list(response_data.keys()))
            self.session_config = response_data["session"]
            return True
        else:
            logger.warning("Unexpected response type: %s", event_type)
            logger.debug("Full response: %s", response_data)
            return False

    async def _send_message(self, message: Dict[str, Any]):
        """Send a JSON message to the WebSocket server."""
        await self.websocket.send(json.dumps(message))

    async def send_audio_chunks(self, audio_chunks):
        """Send audio chunks to the server for transcription."""
        logger.debug("Sending audio chunks...")

        # Check if the audio_chunks supports async iteration
        if hasattr(audio_chunks, '__aiter__'):
            # Use async for for async iterators - this allows proper task switching
            async for chunk in audio_chunks:
                try:
                    chunk_base64 = base64.b64encode(chunk).decode("utf-8")

                    # Send chunk to the server
                    await self._send_message({
                        "type": "input_audio_buffer.append",
                        "audio": chunk_base64,
                    })

                    # Commit the chunk
                    await self._send_message({
                        "type": "input_audio_buffer.commit",
                    })
                except TimeoutError:
                    # Handle timeout from AsyncAudioIterator - no audio available, continue
                    logger.debug("No audio chunk available within timeout, continuing...")
                    continue
                except Exception as e:
                    logger.error(f"Error processing audio chunk: {e}")
                    continue
        else:
            # Fallback for regular iterators
            for chunk in audio_chunks:
                chunk_base64 = base64.b64encode(chunk).decode("utf-8")

                # Send chunk to the server
                await self._send_message({
                    "type": "input_audio_buffer.append",
                    "audio": chunk_base64,
                })

                # Commit the chunk
                await self._send_message({
                    "type": "input_audio_buffer.commit",
                })
            
        logger.debug("All chunks sent")

        # Tell the server that we are done sending chunks
        await self._send_message({
            "type": "input_audio_buffer.done",
        })

    async def receive_responses(self):
        """Receive and process transcription responses from the server."""
        logger.debug("Listening for responses...")
        received_final_response = False

        while not received_final_response:
            try:
                response = await asyncio.wait_for(self.websocket.recv(), 10.0)
                event = json.loads(response)
                event_type = event.get("type", "")

                if event_type == "conversation.item.input_audio_transcription.delta":
                    delta = event.get("delta", "")
                    logger.info("Transcript: %s", delta)

                elif event_type == "conversation.item.input_audio_transcription.completed":
                    is_last_result = event.get("is_last_result", False)
                    interim_final_transcript = event.get("transcript", "")
                    self.final_transcript = interim_final_transcript

                    if is_last_result:
                        logger.info("Final Transcript: %s", self.final_transcript)
                        logger.info("Transcription completed")
                        received_final_response = True
                        break
                    else:
                        logger.info("Interim Transcript: %s", interim_final_transcript)

                    # Format Words Info similar to print_streaming function
                    words_info = event.get("words_info", {})
                    if words_info and "words" in words_info:
                        print("Words Info:")
                        
                        # Create header format similar to print_streaming
                        header_format = '{: <40s}{: <16s}{: <16s}{: <16s}{: <16s}'
                        header_values = ['Word', 'Start (ms)', 'End (ms)', 'Confidence', 'Speaker']
                        print(header_format.format(*header_values))
                        
                        # Print each word with formatted information
                        for word_data in words_info["words"]:
                            word = word_data.get("word", "")
                            start_time = word_data.get("start_time", 0)
                            end_time = word_data.get("end_time", 0)
                            confidence = word_data.get("confidence", 0.0)
                            speaker_tag = word_data.get("speaker_tag", 0)
                            
                            # Format the word info line similar to print_streaming
                            word_format = '{: <40s}{: <16.0f}{: <16.0f}{: <16.4f}{: <16d}'
                            word_values = [word, start_time, end_time, confidence, speaker_tag]
                            print(word_format.format(*word_values))

                elif "error" in event_type.lower():
                    logger.error(
                        f"Error: {event.get('error', {}).get('message', 'Unknown error')}"
                    )
                    received_final_response = True
                    break

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("Error: %s", e)
                break

    def save_responses(self, output_text_file: str):
        """Save collected transcription text to a file.

        Args:
            output_text_file: Path to the output text file
        """
        if self.final_transcript:
            try:
                with open(output_text_file, "w") as f:
                    f.write(self.final_transcript)
            except Exception as e:
                logger.error("Error saving text: %s", e)

    async def disconnect(self):
        """Close the WebSocket connection."""
        if self.websocket:
            await self.websocket.close()

class RealtimeClientTTS:
    """Client for real-time text-to-speech synthesis via WebSocket connection."""

    def __init__(self, args: argparse.Namespace):
        """Initialize the RealtimeClientTTS.

        Args:
            args: Command line arguments containing configuration
        """
        self.args = args
        self.websocket = None
        self.session_config = None
        self.audio_data = []
        self.is_synthesis_complete = False
        self.wav_file = None  # WAV file handle for streaming write
        self.error_occurred = False

    def list_voices(self):
        """List available voices."""
        headers = {"Content-Type": "application/json"}
        uri = f"http://{self.args.server}/v1/audio/list_voices"
        if self.args.use_ssl:
            uri = f"https://{self.args.server}/v1/audio/list_voices"
        
        logger.info("Listing voices via HTTP GET request to: %s", uri)
        response = requests.get(uri, headers=headers)
        response.raise_for_status()
        return response.json()



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
            session_updated = await self._update_session()
            if not session_updated:
                logger.error("Failed to update session")
                raise Exception("Failed to update session")
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

        # Make HTTP request with proper error handling
        try:
            # Handle SSL parameters safely
            cert_params = None
            if hasattr(self.args, 'ssl_client_cert') and hasattr(self.args, 'ssl_client_key'):
                if self.args.ssl_client_cert and self.args.ssl_client_key:
                    cert_params = (self.args.ssl_client_cert, self.args.ssl_client_key)
            
            verify_param = True
            if hasattr(self.args, 'ssl_root_cert') and self.args.ssl_root_cert:
                verify_param = self.args.ssl_root_cert
            
            response = requests.post(
                uri,
                headers=headers,
                json={},
                cert=cert_params,
                verify=verify_param,
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

    def _safe_update_config(self, config: Dict[str, Any], key: str, value: Any, section: str = None):
        """Safely update a configuration value, creating the section if it doesn't exist.

        Args:
            config: The configuration dictionary to update
            key: The key to update
            value: The value to set
            section: The section name (e.g., 'input_text_synthesis')
        """
        if section:
            if section not in config:
                config[section] = {}
            config[section][key] = value
        else:
            config[key] = value
        logger.debug("Updated %s = %s", key, value)

    async def _update_session(self, timeout=1):
        """Update session configuration by selectively overriding server defaults."""
        logger.info("Updating session configuration...")
        logger.debug("Server default config: %s", self.session_config)

        # Create a copy of the session config from server defaults
        session_config = self.session_config.copy()

        # Track what we're overriding
        overrides = []

        # Update input text synthesis - only override if args are provided
        if hasattr(self.args, 'language_code') and self.args.language_code:
            self._safe_update_config(session_config, "language_code", self.args.language_code, "input_text_synthesis")
            overrides.append("language_code")

        if hasattr(self.args, 'voice') and self.args.voice:
            self._safe_update_config(session_config, "voice_name", self.args.voice, "input_text_synthesis")
            overrides.append("voice_name")

        # Update output audio parameters - only override if args are provided
        if hasattr(self.args, 'sample_rate_hz') and self.args.sample_rate_hz:
            self._safe_update_config(session_config, "sample_rate_hz", self.args.sample_rate_hz, "output_audio_params")
            overrides.append("sample_rate_hz")

        if hasattr(self.args, 'encoding') and self.args.encoding:
            self._safe_update_config(session_config, "audio_format", self.args.encoding, "output_audio_params")
            overrides.append("audio_format")

        # Update custom dictionary - only override if args are provided
        if hasattr(self.args, 'custom_dictionary') and self.args.custom_dictionary:
            self._safe_update_config(session_config, "custom_dictionary", self.args.custom_dictionary)
            overrides.append("custom_dictionary")

        # Update zero-shot config - only override if args are provided
        if (hasattr(self.args, 'zero_shot_audio_prompt_file') and self.args.zero_shot_audio_prompt_file):
            try:
                with open(self.args.zero_shot_audio_prompt_file, 'rb') as f:
                    audio_data = f.read()
                    base64_audio_data = base64.b64encode(audio_data).decode('utf-8')
                    self._safe_update_config(session_config["zero_shot_config"], "audio_prompt_bytes", base64_audio_data)
                    logger.info("Zero-shot audio prompt bytes: %s", len(base64_audio_data))
                overrides.append("zero_shot_audio_prompt_file")
            except Exception as e:
                logger.warning("Failed to load zero-shot audio prompt: %s", e)
            
            if hasattr(self.args, 'zero_shot_audio_prompt_transcript') and self.args.zero_shot_audio_prompt_transcript:
                self._safe_update_config(session_config["zero_shot_config"], "audio_prompt_transcript", self.args.zero_shot_audio_prompt_transcript)
                logger.info("Zero-shot audio prompt transcript: %s", self.args.zero_shot_audio_prompt_transcript)
                overrides.append("zero_shot_transcript")
            
            if hasattr(self.args, 'zero_shot_prompt_quality') and self.args.zero_shot_prompt_quality:
                self._safe_update_config(session_config["zero_shot_config"], "prompt_quality", self.args.zero_shot_prompt_quality)
                logger.info("Zero-shot quality: %s", self.args.zero_shot_prompt_quality)
                overrides.append("zero_shot_prompt_quality")
                
        logger.debug("Overriding parameters: %s", overrides)

        update_request = {
            "event_id": f"event_{uuid.uuid4()}",
            "type": "synthesize_session.update",
            "session": session_config
        }

        await self._send_message(update_request)

        session_created = False
        session_updated = False
        
        while not session_created or not session_updated:
            response = await asyncio.wait_for(
                self.websocket.recv(), timeout
            )
            response_data = json.loads(response)
            event_type = response_data.get("type", "")
            if event_type == "conversation.created":
                logger.info("Synthesis session created successfully")
                session_created = True
            elif event_type == "synthesize_session.updated":
                logger.info("Synthesis session updated successfully")
                self.session_config = response_data["session"]
                session_updated = True
            elif event_type == "error":
                error_info = response_data.get("error", {})
                logger.error("Error: %s", error_info.get("message", "Unknown error"))
                self.is_synthesis_complete = True
                return False
            else:
                logger.warning("Unexpected response type: %s", event_type)

        return True
    
    async def _send_message(self, message: Dict[str, Any]):
        """Send a JSON message to the WebSocket server."""
        await self.websocket.send(json.dumps(message))

    async def send_text(self, text_generator: Generator[str, None, None]):
        """Send text to the server for synthesis."""
        logger.info("Sending text for synthesis...")

        async for text in text_generator:
            if text is not None:
                await self._send_message({
                    "event_id": f"event_{uuid.uuid4()}",
                            "type": "input_text.append",
                            "text": text
                        })
            else:
                await self._send_message({
                    "event_id": f"event_{uuid.uuid4()}",
                    "type": "input_text.commit"
                })
        await self._send_message({
            "event_id": f"event_{uuid.uuid4()}",
            "type": "input_text.done"
        })
        logger.info("Text input marked as done")
        
    async def receive_audio(self, audio_chunks, timeout=10.0):
        """Receive and process audio responses from the server."""
        logger.info("Listening for audio responses...")
        self.error_occurred = False
        
        while not self.is_synthesis_complete and not self.error_occurred:
            try:
                response = await asyncio.wait_for(self.websocket.recv(), timeout)
                event = json.loads(response)
                event_type = event.get("type", "")

                if event_type == "conversation.item.speech.data":
                    # Handle audio data
                    import base64
                    audio_data_b64 = event.get("audio", "")
                    if audio_data_b64:
                        audio_data = base64.b64decode(audio_data_b64)
                        audio_chunks.append(audio_data)
                        
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
                    self.error_occurred = True

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("Error receiving audio: %s", e)
                break
    
    async def disconnect(self):
        """Close the WebSocket connection."""
        if self.websocket:
            await self.websocket.close()