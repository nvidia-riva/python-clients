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
        
        # Transcription results
        self.delta_transcripts: List[str] = []
        self.interim_final_transcripts: List[str] = []
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
            logger.error(f"HTTP request failed: {e}")
            raise
        except WebSocketException as e:
            logger.error(f"WebSocket connection failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during connection: {e}")
            raise

    async def _initialize_http_session(self) -> Dict[str, Any]:
        """Initialize session via HTTP POST request."""
        headers = {"Content-Type": "application/json"}
        response = requests.post(
            f"http://{self.args.server}/v1/realtime/transcription_sessions",
            headers=headers,
            json={}
        )
        
        if response.status_code != 200:
            raise Exception(
                f"Failed to initialize session. Status: {response.status_code}, "
                f"Error: {response.text}"
            )
            
        session_data = response.json()
        logger.info(f"Session initialized: {session_data}")
        return session_data

    async def _connect_websocket(self):
        """Connect to WebSocket endpoint."""
        ws_url = f"ws://{self.args.server}{self.args.endpoint}?{self.args.query_params}"
        logger.info(f"Connecting to WebSocket: {ws_url}")
        self.websocket = await websockets.connect(ws_url)

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
                logger.debug("Response structure: %s", list(response_data.keys()))
            else:
                logger.warning(f"Unexpected first response type: {event_type}")
                logger.debug("Full response: %s", response_data)

            # Update session configuration
            self.is_config_updated = await self._update_session()
            if not self.is_config_updated:
                logger.error("Failed to update session")
                raise Exception("Failed to update session")
                
            logger.info("Session initialization complete")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise
        except KeyError as e:
            logger.error(f"Missing expected key in response: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during session initialization: {e}")
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
            logger.debug(f"Updated {section}.{key} = {value}")
        else:
            config[key] = value
            logger.debug(f"Updated {key} = {value}")

    async def _update_session(self) -> bool:
        """Update session configuration by selectively overriding server defaults.
        
        Returns:
            True if session was updated successfully, False otherwise
        """
        logger.info("Updating session configuration...")
        logger.info(f"Server default config: {self.session_config}")
        
        # Create a copy of the session config from server defaults
        session_config = self.session_config.copy()
        
        # Track what we're overriding
        overrides = []
        
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
            logger.info(f"Overriding server defaults for: {', '.join(overrides)}")
        else:
            logger.info("Using server default configuration (no overrides)")
        
        logger.info(f"Final session config: {session_config}")
        
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
        logger.info("Session updated: %s", response_data)
        
        event_type = response_data.get("type", "")
        if event_type == "transcription_session.updated":
            logger.info("Transcription session updated successfully")
            logger.debug("Response structure: %s", list(response_data.keys()))
            self.session_config = response_data["session"]
            return True
        else:
            logger.warning(f"Unexpected response type: {event_type}")
            logger.debug("Full response: %s", response_data)
            return False

    async def _send_message(self, message: Dict[str, Any]):
        """Send a JSON message to the WebSocket server."""
        await self.websocket.send(json.dumps(message))

    async def send_audio_chunks(self, audio_chunks):
        """Send audio chunks to the server for transcription."""
        logger.info("Sending audio chunks...")
        
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
        
        logger.info("All chunks sent")
        
        # Tell the server that we are done sending chunks
        await self._send_message({
            "type": "input_audio_buffer.done",
        })

    async def receive_responses(self):
        """Receive and process transcription responses from the server."""
        logger.info("Listening for responses...")
        received_final_response = False
        
        while not received_final_response:
            try:
                response = await asyncio.wait_for(self.websocket.recv(), 10.0)
                event = json.loads(response)
                event_type = event.get("type", "")

                if event_type == "conversation.item.input_audio_transcription.delta":
                    delta = event.get("delta", "")
                    logger.info("Transcript: %s", delta)
                    self.delta_transcripts.append(delta)
                    
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    is_last_result = event.get("is_last_result", False)
                    interim_final_transcript = event.get("transcript", "")
                    self.interim_final_transcripts.append(interim_final_transcript)
                    self.final_transcript = interim_final_transcript
                    
                    if is_last_result:
                        logger.info("Final Transcript: %s", self.final_transcript)
                        logger.info("Transcription completed")
                        received_final_response = True
                        break
                    else:
                        logger.info("Interim Transcript: %s", interim_final_transcript)
                    
                    logger.info("Words Info: %s", event.get("words_info", ""))
                    
                elif "error" in event_type.lower():
                    logger.error(
                        f"Error: {event.get('error', {}).get('message', 'Unknown error')}"
                    )
                    received_final_response = True
                    break

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error: {e}")
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
                logger.error(f"Error saving text: {e}")

    async def disconnect(self):
        """Close the WebSocket connection."""
        if self.websocket:
            await self.websocket.close()

