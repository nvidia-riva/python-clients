#!/usr/bin/env python3

import argparse
import asyncio
import base64
import json
import logging
import queue
import time
import wave
from pathlib import Path

import numpy as np
import pyaudio
import requests
import websockets
from websockets.exceptions import WebSocketException

import riva

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class RealtimeASRClient:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.websocket = None
        self.session_config = None
        self.text_done = False
        self.max_chunk_commit = 4

        # Input audio playback
        self.input_audio_queue = queue.Queue()
        self.input_playback_thread = None
        self.is_input_playing = False
        self.input_buffer_size = 1024  # Buffer size for input audio playback

        self.collected_text = []

    async def connect(self):
        try:
            # First make POST request to initialize session
            headers = {
                "Content-Type": "application/json"
            }
            response = requests.post(
                f"http://{self.args.server}/v1/realtime/transcription_sessions",
                headers=headers,
                json={}
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to initialize session. Status: {response.status_code}, Error: {response.text}")
                
            session_data = response.json()
            logger.info(f"Session initialized: {session_data}")
            self.session_config = session_data
            
            # Then connect to WebSocket
            ws_url = f"ws://{self.args.server}{self.args.endpoint}?{self.args.query_params}"
            logger.info(f"Connecting to WebSocket: {ws_url}")
            
            self.websocket = await websockets.connect(ws_url)
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

    async def _update_session(self):
        logger.info("Updating session...")
        
        # Create a copy of the session config
        session_config = self.session_config.copy()
        
        self.model = "parakeet-1.1b-en-US-asr-streaming-silero-vad-asr-bls-ensemble"
        session_config["input_audio_transcription"] = {
            "language" : "en-US",
            "model": self.model,
            "prompt": ""
        }
        session_config["input_audio_params"] = {
            "sample_rate_hz": self.args.sample_rate_hz,
            "num_channels": self.args.num_channels
        }
        session_config["recognition_config"] = {
            "max_alternatives": self.args.max_alternatives,
            "enable_automatic_punctuation": self.args.automatic_punctuation,
            "enable_word_time_offsets": self.args.word_time_offsets,
            "enable_profanity_filter": self.args.profanity_filter,
            "enable_verbatim_transcripts": self.args.no_verbatim_transcripts
        }
        
        if self.args.speaker_diarization:
            session_config["speaker_diarization"] = {
                "enable_speaker_diarization": True,
                "max_speaker_count": self.args.diarization_max_speakers
            }
        
        if self.args.boosted_lm_words:
            if len(self.args.boosted_lm_words):
                word_boosting_list = [
                    {
                        "phrases" : self.args.boosted_lm_words,
                        "boost": self.args.boosted_lm_score
                    }
                ]
                session_config["word_boosting"] = {
                    "enable_word_boosting": True,
                    "word_boosting_list": word_boosting_list
                }
        
        if self.args.start_history > 0 or self.args.start_threshold > 0 or self.args.stop_history > 0 or self.args.stop_history_eou > 0 or self.args.stop_threshold > 0 or self.args.stop_threshold_eou > 0:
            self.args.endpointing_config.start_history = self.args.start_history
            self.args.endpointing_config.start_threshold = self.args.start_threshold
            self.args.endpointing_config.stop_history = self.args.stop_history
            self.args.endpointing_config.stop_history_eou = self.args.stop_history_eou
            self.args.endpointing_config.stop_threshold = self.args.stop_threshold
            self.args.endpointing_config.stop_threshold_eou = self.args.stop_threshold_eou
            session_config["endpointing_config"] = {
                "start_history": self.args.start_history,
                "start_threshold": self.args.start_threshold,
                "stop_history": self.args.stop_history,
                "stop_threshold": self.args.stop_threshold,
                "stop_history_eou": self.args.stop_history_eou,
                "stop_threshold_eou": self.args.stop_threshold_eou
            }
        
        # Now client sends request to update session
        update_session_request = {
            "type": "transcription_session.update",
            "session": session_config
        }
        await self._send_message(
            update_session_request
        )
        
        # Handle response: "transcription_session.updated"
        response = await self.websocket.recv()
        response_data = json.loads(response)
        logger.info("Session updated: %s", response_data)
        
        is_updated = False
        event_type = response_data.get("type", "")
        if event_type == "transcription_session.updated":
            is_updated = True
            logger.info("Transcription session updated successfully")
            # Print the structure for debugging
            logger.debug("Response structure: %s", list(response_data.keys()))
        else:
            logger.warning(f"Unexpected response type: {event_type}")
            logger.debug("Full response: %s", response_data)
            
        if is_updated:
            self.session_config = response_data["session"]
        
        return is_updated
                
        
    async def _initialize_session(self):
        try:
            # Handle first response: "conversation.created"
            response = await self.websocket.recv()
            response_data = json.loads(response)
            logger.info("Session created: %s", response_data)
            
            event_type = response_data.get("type", "")
            if event_type == "conversation.created":
                logger.info("Conversation created successfully")
                # Print the structure for debugging
                logger.debug("Response structure: %s", list(response_data.keys()))
            else:
                logger.warning(f"Unexpected first response type: {event_type}")
                logger.debug("Full response: %s", response_data)

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

    async def _send_message(self, message):
        await self.websocket.send(json.dumps(message))

    async def send_audio_chunks(self, audio_chunks):
        logger.info("Sending audio chunks...")
        current_chunk_count = 0
        
        for chunk in audio_chunks:
            if self.text_done:
                break

            chunk_base64 = base64.b64encode(chunk).decode("utf-8")
            await self._send_message(
                {
                    "type": "input_audio_buffer.append",
                    "audio": chunk_base64,
                }
            )
            current_chunk_count += 1
            await asyncio.sleep(0.1)
            
            if current_chunk_count == self.max_chunk_commit:
                await self._send_message(
                    {
                        "type": "input_audio_buffer.commit",
                    }
                )
                print(f"Committed chunks")
                current_chunk_count = 0

        logger.info("All chunks sent")

    async def receive_responses(self):
        logger.info("Listening for responses...")

        self.text_done = False

        while not self.text_done:
            try:
                try:
                    response = await asyncio.wait_for(self.websocket.recv(), 10.0)
                except asyncio.TimeoutError:
                    continue
                
                event = json.loads(response)
                #print(f"event: {event}")
                event_type = event.get("type", "")

                if event_type == "conversation.item.input_audio_transcription.delta":
                    delta = event.get("delta", "")
                    logger.info("Transcript: %s", delta)
                    self.collected_text.append(delta)
                elif "error" in event_type.lower():
                    logger.error(f"Error: {event.get('error', {}).get('message', 'Unknown error')}")
                    self.text_done = True
                    break

            except (asyncio.TimeoutError, Exception) as e:
                logger.error(f"Error: {e}")
                break

    def save_responses(self, output_text_file):
        if self.collected_text:
            try:
                with open(output_text_file, "w") as f:
                    f.write("".join(self.collected_text))
            except Exception as e:
                logger.error(f"Error saving text: {e}")

    async def disconnect(self):
        if self.websocket:
            await self.websocket.close()

