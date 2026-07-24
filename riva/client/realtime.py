#!/usr/bin/env python3

import argparse
import asyncio
import base64
import json
import logging
import queue
import uuid
from typing import Any, Dict, Generator, Iterable, List, Optional

import requests
import websockets
import ssl
from websockets.exceptions import WebSocketException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def _mint_auth_headers(args: argparse.Namespace) -> Dict[str, str]:
    """Build HTTP headers for session mint endpoints, including optional tier-1 auth."""
    headers = {"Content-Type": "application/json"}
    api_key = (getattr(args, "mint_api_key", None) or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _server_error_detail(response) -> str:
    """Extract the FastAPI ``detail`` message from an error response, falling back to raw text."""
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()
    if isinstance(payload, dict) and payload.get("detail"):
        return str(payload["detail"])
    return response.text.strip()


def _raise_for_session_status(response, provided_key: bool) -> None:
    """Raise a clear, actionable error when the session mint request fails."""
    if response.status_code == 200:
        return
    if response.status_code in (401, 403):
        if provided_key:
            hint = "The --mint-api-key value was rejected by the server. Verify it matches the server's REALTIME_AUTH_MINT_API_KEY."
        else:
            hint = "This server requires an API key on the session endpoint. Pass it with --mint-api-key <key>."
        raise Exception(
            f"Session authentication failed (HTTP {response.status_code}: {_server_error_detail(response)}). {hint}"
        )
    raise Exception(
        f"Failed to initialize session. Status: {response.status_code}, Error: {_server_error_detail(response)}"
    )


def _extract_client_secret_token(session_data: Dict[str, Any]) -> Optional[str]:
    """Return the ephemeral client_secret token when present, else ``None``.

    Older servers that do not mint ``client_secret`` keep the legacy
    unauthenticated WebSocket flow.  New servers that return a secret require
    it on ``Sec-WebSocket-Protocol``.
    """
    client_secret = session_data.get("client_secret")
    if not isinstance(client_secret, dict):
        return None
    token = client_secret.get("value")
    if not token:
        return None
    return str(token)

TOKEN_SUBPROTO_PREFIX = "realtime-token."
REALTIME_SUBPROTOCOL = "realtime"

def _build_websocket_url(
    server: str,
    endpoint: str,
    query_params: str,
    use_ssl: bool,
) -> str:
    """Build the WebSocket URL (intent only; auth token goes in Sec-WebSocket-Protocol)."""
    query = query_params.strip()
    scheme = "wss" if use_ssl else "ws"
    if query:
        return f"{scheme}://{server}{endpoint}?{query}"
    return f"{scheme}://{server}{endpoint}"


def _websocket_subprotocols(token: str) -> List[str]:
    """Return Sec-WebSocket-Protocol entries for the realtime handshake.

    Offers ``realtime`` plus ``realtime-token.<client_secret>``.  The server
    validates the token entry and echoes back ``realtime`` so the secret
    never appears in the response headers.
    """
    return [REALTIME_SUBPROTOCOL, f"{TOKEN_SUBPROTO_PREFIX}{token}"]


def _build_ssl_context(args: argparse.Namespace):
    """Build an optional SSL context for WebSocket connections."""
    if not getattr(args, "use_ssl", False):
        return None
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if getattr(args, "ssl_root_cert", None):
        ssl_context.load_verify_locations(args.ssl_root_cert)
    if getattr(args, "ssl_client_cert", None) and getattr(args, "ssl_client_key", None):
        ssl_context.load_cert_chain(args.ssl_client_cert, args.ssl_client_key)
    ssl_context.check_hostname = False
    return ssl_context


async def _connect_websocket(
    args: argparse.Namespace,
    client_secret_token: Optional[str],
):
    """Open the realtime WebSocket, attaching subprotocol auth when available."""
    ws_url = _build_websocket_url(
        args.server,
        args.endpoint,
        args.query_params,
        args.use_ssl,
    )
    ssl_context = _build_ssl_context(args)
    connect_kwargs = {"ssl": ssl_context}
    if client_secret_token:
        connect_kwargs["subprotocols"] = _websocket_subprotocols(client_secret_token)
    return await websockets.connect(ws_url, **connect_kwargs)


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
        self._client_secret_token: Optional[str] = None

        # Input audio playback
        self.input_audio_queue = queue.Queue()
        self.input_playback_thread = None
        self.is_input_playing = False
        self.input_buffer_size = 1024  # Buffer size for input audio playback
        self.final_transcript: str = ""
        self.is_config_updated = False
        self._force_eou_pending = False


    async def connect(self):
        """Establish connection to the ASR server."""
        try:
            # Initialize session via HTTP POST
            session_data = await self._initialize_http_session()
            self.session_config = session_data
            self._client_secret_token = _extract_client_secret_token(session_data)

            # Connect to WebSocket
            self.websocket = await _connect_websocket(
                self.args, self._client_secret_token,
            )
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
        headers = _mint_auth_headers(self.args)
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

        _raise_for_session_status(response, provided_key=bool(getattr(self.args, "mint_api_key", None)))

        session_data = response.json()
        logger.debug("Session initialized: %s", session_data)
        return session_data

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
            self._safe_update_config(
                session_config,
                "enable_verbatim_transcripts",
                not self.args.no_verbatim_transcripts,
                "recognition_config",
            )
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
                self._safe_update_config(
                    session_config,
                    "custom_configuration",
                    self.args.custom_configuration,
                    "recognition_config",
                )
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
        """Build endpointing configuration dictionary.

        Only fields the user actually set (i.e., not the -1 / -1.0 sentinel
        defaults from argparse) are included, so the server doesn't reject the
        request for out-of-range values on fields the caller never touched.
        """
        config: Dict[str, Any] = {}
        if self.args.start_history > 0:
            config["start_history"] = self.args.start_history
        if self.args.start_threshold > 0:
            config["start_threshold"] = self.args.start_threshold
        if self.args.stop_history > 0:
            config["stop_history"] = self.args.stop_history
        if self.args.stop_threshold > 0:
            config["stop_threshold"] = self.args.stop_threshold
        if self.args.stop_history_eou > 0:
            config["stop_history_eou"] = self.args.stop_history_eou
        if self.args.stop_threshold_eou > 0:
            config["stop_threshold_eou"] = self.args.stop_threshold_eou
        return config

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

    def request_force_eou(self) -> None:
        """Request end-of-utterance finalization on the next audio chunk."""
        self._force_eou_pending = True

    async def _send_audio_chunk(self, chunk: bytes, force_eou: bool = False) -> None:
        """Send and commit one audio chunk, optionally forcing end of utterance."""
        chunk_base64 = base64.b64encode(chunk).decode("utf-8")
        force_eou = force_eou or self._force_eou_pending
        self._force_eou_pending = False

        append_message = {
            "type": "input_audio_buffer.append",
            "audio": chunk_base64,
        }
        if force_eou:
            append_message["runtime_config"] = {"force_eou": "true"}

        await self._send_message(append_message)
        await self._send_message({"type": "input_audio_buffer.commit"})

    async def send_audio_chunks(
        self,
        audio_chunks,
        force_eou_chunks: Optional[Iterable[bool]] = None,
    ):
        """Send audio chunks to the server for transcription.

        Args:
            audio_chunks: A synchronous or asynchronous iterable of raw audio chunks.
            force_eou_chunks: Optional per-chunk flags. A true value forces the
                server to finalize the utterance after processing that chunk while
                keeping the stream open.
        """
        logger.debug("Sending audio chunks...")
        force_eou_iter = iter(force_eou_chunks) if force_eou_chunks is not None else None

        # Check if the audio_chunks supports async iteration
        if hasattr(audio_chunks, '__aiter__'):
            # Use async for for async iterators - this allows proper task switching
            async for chunk in audio_chunks:
                try:
                    force_eou = next(force_eou_iter, False) if force_eou_iter is not None else False
                    await self._send_audio_chunk(chunk, force_eou)
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
                force_eou = next(force_eou_iter, False) if force_eou_iter is not None else False
                await self._send_audio_chunk(chunk, force_eou)

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
                    else:
                        logger.info("Interim Transcript: %s", interim_final_transcript)

                    # Format Words Info similar to print_streaming function
                    words_info = event.get("words_info", {})
                    if self.args.word_time_offsets and words_info and words_info.get("words"):
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

                    if is_last_result:
                        logger.info("Transcription completed")
                        received_final_response = True
                        break

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
        self._client_secret_token: Optional[str] = None
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
            self._client_secret_token = _extract_client_secret_token(session_data)
            logger.info("HTTP session initialized successfully")

            # Connect to WebSocket
            logger.info("Connecting to WebSocket...")
            self.websocket = await _connect_websocket(
                self.args, self._client_secret_token,
            )
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
        headers = _mint_auth_headers(self.args)
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

        _raise_for_session_status(response, provided_key=bool(getattr(self.args, "mint_api_key", None)))

        session_data = response.json()
        logger.info("Session initialized: %s", session_data)
        return session_data

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
        """Update session configuration by sending an override-only payload.

        Builds the synthesize_session.update payload directly from CLI args
        instead of round-tripping through self.session_config (the response
        from POST /v1/realtime/synthesis_sessions).
        """
        logger.info("Updating session configuration...")
        logger.debug("Server default config: %s", self.session_config)

        session_payload: Dict[str, Any] = {}
        overrides: List[str] = []
        requested_voice: Optional[str] = None
        requested_language: Optional[str] = None

        # input_text_synthesis: language_code + voice_name
        input_text_synthesis: Dict[str, Any] = {}
        if getattr(self.args, "language_code", None):
            requested_language = self.args.language_code
            input_text_synthesis["language_code"] = requested_language
            overrides.append("language_code")
        if getattr(self.args, "voice", None):
            requested_voice = self.args.voice
            input_text_synthesis["voice_name"] = requested_voice
            overrides.append("voice_name")
        if input_text_synthesis:
            session_payload["input_text_synthesis"] = input_text_synthesis

        # output_audio_params: sample_rate_hz + audio_format
        output_audio_params: Dict[str, Any] = {}
        if getattr(self.args, "sample_rate_hz", None):
            output_audio_params["sample_rate_hz"] = self.args.sample_rate_hz
            overrides.append("sample_rate_hz")
        if getattr(self.args, "encoding", None):
            output_audio_params["audio_format"] = self.args.encoding
            overrides.append("audio_format")
        if output_audio_params:
            session_payload["output_audio_params"] = output_audio_params

        if getattr(self.args, "custom_dictionary", None):
            session_payload["custom_dictionary"] = self.args.custom_dictionary
            overrides.append("custom_dictionary")

        # zero_shot_config: audio bytes + transcript + quality
        if getattr(self.args, "zero_shot_audio_prompt_file", None):
            zero_shot_config: Dict[str, Any] = {}
            try:
                with open(self.args.zero_shot_audio_prompt_file, "rb") as f:
                    audio_data = f.read()
                base64_audio_data = base64.b64encode(audio_data).decode("utf-8")
                zero_shot_config["audio_prompt_bytes"] = base64_audio_data
                logger.info("Zero-shot audio prompt bytes: %s", len(base64_audio_data))
                overrides.append("zero_shot_audio_prompt_file")
            except Exception as e:
                logger.warning("Failed to load zero-shot audio prompt: %s", e)

            if getattr(self.args, "zero_shot_audio_prompt_transcript", None):
                zero_shot_config["audio_prompt_transcript"] = self.args.zero_shot_audio_prompt_transcript
                logger.info("Zero-shot audio prompt transcript: %s", self.args.zero_shot_audio_prompt_transcript)
                overrides.append("zero_shot_transcript")

            if getattr(self.args, "zero_shot_prompt_quality", None):
                zero_shot_config["prompt_quality"] = self.args.zero_shot_prompt_quality
                logger.info("Zero-shot quality: %s", self.args.zero_shot_prompt_quality)
                overrides.append("zero_shot_prompt_quality")

            if zero_shot_config:
                session_payload["zero_shot_config"] = zero_shot_config

        if getattr(self.args, "custom_configuration", None):
            custom_config = self._parse_custom_configuration(self.args.custom_configuration)
            if custom_config:
                session_payload["custom_configuration"] = custom_config
                overrides.append("custom_configuration")

        logger.info("Overriding session parameters: %s", overrides)
        if requested_voice:
            logger.info("Requested voice_name=%r", requested_voice)

        update_request = {
            "event_id": f"event_{uuid.uuid4()}",
            "type": "synthesize_session.update",
            "session": session_payload,
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
                acked = self.session_config.get("input_text_synthesis", {}) if isinstance(self.session_config, dict) else {}
                acked_voice = acked.get("voice_name")
                acked_language = acked.get("language_code")
                if requested_voice and acked_voice and acked_voice != requested_voice:
                    logger.warning(
                        "Server applied voice_name=%r, but --voice requested %r. "
                        "Synthesis will use the server-applied voice.",
                        acked_voice, requested_voice,
                    )
                elif requested_voice:
                    logger.info("Server confirmed voice_name=%r", acked_voice)
                if requested_language and acked_language and acked_language != requested_language:
                    logger.warning(
                        "Server applied language_code=%r, but --language-code requested %r.",
                        acked_language, requested_language,
                    )
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
