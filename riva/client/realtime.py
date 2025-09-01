#!/usr/bin/env python3

import argparse
import asyncio
import base64
import json
import logging
import queue
from typing import Dict, Any, List

import requests
import websockets
import ssl
from websockets.exceptions import WebSocketException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RealtimeClient:
    """Client for real-time transcription via WebSocket connection."""

    def __init__(self, args: argparse.Namespace):
        """Initialize the RealtimeClient.

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
            raise
        except WebSocketException as e:
            logger.error("WebSocket connection failed: %s", e)
            raise
        except Exception as e:
            raise

    async def _initialize_http_session(self) -> Dict[str, Any]:
        """Initialize session via HTTP POST request."""
        headers = {"Content-Type": "application/json"}
        uri = f"http://{self.args.server}/v1/realtime/transcription_sessions"
        if self.args.use_ssl:
            uri = f"https://{self.args.server}/v1/realtime/transcription_sessions"
        logger.debug("Initializing session via HTTP POST request to: %s", uri)
        
        try:
            response = requests.post(
                uri,
                headers=headers,
                json={},
                cert=(self.args.ssl_client_cert, self.args.ssl_client_key) if self.args.ssl_client_cert and self.args.ssl_client_key else None,
                verify=self.args.ssl_root_cert if self.args.ssl_root_cert else True,
                timeout=30  # Add timeout to prevent hanging
            )

            if response.status_code != 200:
                raise Exception(
                    f"Failed to initialize session. Status: {response.status_code}, "
                    f"Error: {response.text}"
                )

            session_data = response.json()
            logger.debug("Session initialized: %s", session_data)
            return session_data
            
        except requests.exceptions.ConnectionError as e:
            # Handle connection errors more gracefully
            if "Connection refused" in str(e):
                error_msg = f"Cannot connect to server at {self.args.server}. The server may be down or not running."
            elif "Name or service not known" in str(e):
                error_msg = f"Cannot resolve server hostname '{self.args.server}'. Please check the server address."
            elif "timeout" in str(e).lower():
                error_msg = f"Connection to {self.args.server} timed out. The server may be overloaded or unreachable."
            elif "Connection aborted." in str(e):
                error_msg = f"Connection aborted. Failed to establish a new connection to {self.args.server}. The server may be down or not running."
            else:
                error_msg = f"Connection failed to {self.args.server}: {str(e)}"
            
            logger.error("HTTP connection error: %s", error_msg)
            raise Exception(error_msg) from e
            
        except requests.exceptions.SSLError as e:
            error_msg = f"SSL/TLS connection failed to {self.args.server}: {str(e)}"
            logger.error("SSL error: %s", error_msg)
            raise Exception(error_msg) from e
            
        except requests.exceptions.Timeout as e:
            error_msg = f"Request to {self.args.server} timed out after 30 seconds"
            logger.error("Request timeout: %s", error_msg)
            raise Exception(error_msg) from e
            
        except requests.exceptions.RequestException as e:
            # Handle other HTTP-related errors
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                try:
                    error_text = e.response.text
                except:
                    error_text = "Unable to read error response"
                
                if status_code == 401:
                    error_msg = f"Authentication failed (401). Please check your SSL certificates and credentials."
                elif status_code == 403:
                    error_msg = f"Access forbidden (403). You may not have permission to access this service."
                elif status_code == 404:
                    error_msg = f"Service not found (404). The transcription service endpoint may not exist at {uri}"
                elif status_code == 500:
                    error_msg = f"Server error (500). The transcription service encountered an internal error."
                else:
                    error_msg = f"HTTP request failed with status {status_code}: {error_text}"
            else:
                error_msg = f"HTTP request failed: {str(e)}"
            
            logger.error("HTTP request error: %s", error_msg)
            raise Exception(error_msg) from e
            
        except Exception as e:
            # Handle any other unexpected errors
            error_msg = f"Unexpected error during HTTP session initialization: {str(e)}"
            logger.error("Unexpected error: %s", error_msg)
            raise Exception(error_msg) from e

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
        
        try:
            self.websocket = await websockets.connect(
                ws_url, 
                ssl=ssl_context,
                ping_interval=20,  # Send ping every 20 seconds
                ping_timeout=10,   # Wait 10 seconds for pong response
                close_timeout=10   # Wait 10 seconds for close response
            )
        except websockets.exceptions.InvalidURI as e:
            error_msg = f"Invalid WebSocket URI: {ws_url}. Please check the server address and endpoint."
            logger.error("WebSocket URI error: %s", error_msg)
            raise Exception(error_msg) from e
        except websockets.exceptions.InvalidHandshake as e:
            error_msg = f"WebSocket handshake failed. The server may not support WebSocket connections or the endpoint is incorrect."
            logger.error("WebSocket handshake error: %s", error_msg)
            raise Exception(error_msg) from e
        except websockets.exceptions.ConnectionClosed as e:
            error_msg = f"WebSocket connection was closed unexpectedly: {str(e)}"
            logger.error("WebSocket connection closed: %s", error_msg)
            raise Exception(error_msg) from e
        except websockets.exceptions.WebSocketException as e:
            error_msg = f"WebSocket connection failed: {str(e)}"
            logger.error("WebSocket error: %s", error_msg)
            raise Exception(error_msg) from e
        except ConnectionRefusedError as e:
            error_msg = f"Cannot connect to WebSocket server at {self.args.server}. The server may be down or not running."
            logger.error("WebSocket connection refused: %s", error_msg)
            raise Exception(error_msg) from e
        except OSError as e:
            if "Name or service not known" in str(e):
                error_msg = f"Cannot resolve server hostname '{self.args.server}'. Please check the server address."
            elif "timeout" in str(e).lower():
                error_msg = f"WebSocket connection to {self.args.server} timed out."
            else:
                error_msg = f"WebSocket connection failed: {str(e)}"
            logger.error("WebSocket OS error: %s", error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error during WebSocket connection: {str(e)}"
            logger.error("Unexpected WebSocket error: %s", error_msg)
            raise Exception(error_msg) from e

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

