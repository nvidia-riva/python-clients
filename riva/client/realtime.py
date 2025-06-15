#!/usr/bin/env python3

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

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class RealtimeASRClient:
    def __init__(self, server: str, endpoint: str, query_params: str, input_sample_rate: int, input_chunk_size_samples: int, speaker_diarization: bool = False, diarization_max_speakers: int = 2):
        self.server = server
        self.endpoint = endpoint
        self.query_params = query_params
        self.input_sample_rate = input_sample_rate
        self.input_chunk_size_samples = input_chunk_size_samples
        self.speaker_diarization = speaker_diarization
        self.diarization_max_speakers = diarization_max_speakers
        self.websocket = None
        self.session_config = None

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
                "Authorization": f"Bearer {self.query_params}",
                "Content-Type": "application/json"
            }
            response = requests.post(
                f"http://{self.server}/v1/realtime/transcription_sessions",
                headers=headers,
                json={}
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to initialize session. Status: {response.status_code}, Error: {response.text}")
                
            session_data = response.json()
            logger.info(f"Session initialized: {session_data}")
            self.session_config = session_data
            
            # Then connect to WebSocket
            ws_url = f"ws://{self.server}{self.endpoint}?{self.query_params}"
            logger.info(f"Connecting to WebSocket: {ws_url}")
            
            self.websocket = await websockets.connect(
                ws_url,
                extra_headers=headers  # Add authorization headers to WebSocket connection
            )
            
            await self._initialize_session()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request failed: {e}")
            raise
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket connection failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during connection: {e}")
            raise

    async def _update_session(self):
        logger.info("Updating session...")
        
        # Create a copy of the session config
        session_config = self.session_config.copy()
        
        # First check here, what we need to update?
        # Speaker diarization:
        if self.speaker_diarization:
            session_config["speaker_diarization"] = {
                "type": "speaker_diarization",
                "enable_speaker_diarization": True,
                "max_speaker_count": self.diarization_max_speakers
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

            # Update session if needed
            if self.speaker_diarization:
                is_updated = await self._update_session()
                if not is_updated:
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

    def get_audio_chunks(self, audio_file):
        """
        Load audio from WAV file and convert to chunks.
        
        This method uses Python's built-in wave module instead of librosa,
        making it lightweight with no external dependencies.
        
        Note: Only supports WAV files. For other formats, use librosa version.
        """
        logger.info(f"Loading audio: {audio_file}")
        
        # Get file parameters using wave module
        audio_file = Path(audio_file).expanduser()
        
        try:
            with wave.open(str(audio_file), 'rb') as wf:
                # Validate audio parameters
                sample_rate = wf.getframerate()
                n_channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                n_frames = wf.getnframes()
                
                logger.info(f"Audio info: {sample_rate}Hz, {n_channels} channels, {sample_width} bytes/sample")
                
                # Check if resampling is needed
                if sample_rate != self.input_sample_rate:
                    logger.warning(f"Sample rate mismatch: file={sample_rate}Hz, expected={self.input_sample_rate}Hz")
                    logger.warning("Consider resampling the file or use librosa-based version for automatic resampling")
                
                # Read all audio data
                audio_data = wf.readframes(n_frames)
                
        except wave.Error as e:
            raise ValueError(f"Error reading WAV file {audio_file}: {e}")
        except FileNotFoundError:
            raise FileNotFoundError(f"Audio file not found: {audio_file}")
        
        # Convert bytes to numpy array
        if sample_width == 1:
            # 8-bit unsigned
            audio_signal = np.frombuffer(audio_data, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0
        elif sample_width == 2:
            # 16-bit signed
            audio_signal = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        elif sample_width == 4:
            # 32-bit signed
            audio_signal = np.frombuffer(audio_data, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            raise ValueError(f"Unsupported sample width: {sample_width} bytes")
        
        # Convert stereo to mono if needed
        if n_channels > 1:
            audio_signal = audio_signal.reshape(-1, n_channels)
            audio_signal = np.mean(audio_signal, axis=1)
            logger.info(f"Converted from {n_channels} channels to mono")
        
        # Split into chunks
        chunks = []
        for i in range(0, len(audio_signal), self.input_chunk_size_samples):
            chunk = audio_signal[i : i + self.input_chunk_size_samples]

            # Pad last chunk if needed
            if len(chunk) < self.input_chunk_size_samples:
                chunk = np.pad(chunk, (0, self.input_chunk_size_samples - len(chunk)))

            # Convert to 16-bit integer bytes
            chunk_bytes = (chunk * 32767).astype(np.int16).tobytes()
            chunks.append(chunk_bytes)

        logger.info(f"Created {len(chunks)} chunks")
        return chunks

    def get_mic_chunks(self, duration=None):
        """
        Capture audio from microphone and return chunks.

        Args:
            duration: Recording duration in seconds. If None, record until interrupted.

        Returns:
            Generator yielding audio chunks
        """
        logger.info("Initializing microphone...")

        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.input_sample_rate,
            input=True,
            frames_per_buffer=self.input_chunk_size_samples,
        )

        logger.info("Recording from microphone...")
        self.is_recording = True
        self.mic_input_chunks = []

        start_time = time.time()
        chunk_count = 0

        try:
            while self.is_recording:
                if duration and time.time() - start_time > duration:
                    break

                data = stream.read(self.input_chunk_size_samples, exception_on_overflow=False)
                chunk_count += 1

                self.mic_input_chunks.append(data)

                if chunk_count % 20 == 0:
                    logger.info(f"Recorded {chunk_count} chunks")

                yield data

        except KeyboardInterrupt:
            logger.info("Recording interrupted by user")
        finally:
            self.is_recording = False
            stream.stop_stream()
            stream.close()
            p.terminate()
            logger.info(f"Recording stopped. Total chunks: {chunk_count}")

    async def send_audio_chunks(self, audio_chunks):
        logger.info("Sending audio chunks...")

        if isinstance(audio_chunks, list):
            max_chunk_commit = 4
            current_chunk_count = 0
            # Handle pre-recorded chunks from file
            for chunk in audio_chunks:
                chunk_base64 = base64.b64encode(chunk).decode("utf-8")

                await self._send_message(
                    {
                        "type": "input_audio_buffer.append",
                        "audio": chunk_base64,
                    }
                )
                current_chunk_count += 1
                await asyncio.sleep(0.1)
                
                if current_chunk_count == max_chunk_commit:
                    await self._send_message(
                        {
                            "type": "input_audio_buffer.commit",
                        }
                    )
                    print(f"Committed chunks")
                    current_chunk_count = 0
        else:
            # Handle streaming chunks from microphone
            async for chunk in self._stream_chunks(audio_chunks):
                chunk_base64 = base64.b64encode(chunk).decode("utf-8")

                await self._send_message(
                    {
                        "type": "input_audio_buffer.append",
                        "audio": chunk_base64,
                    }
                )
                await asyncio.sleep(0.1)

        logger.info("All chunks sent")

    async def _stream_chunks(self, chunk_generator):
        """Convert synchronous generator to async generator"""
        for chunk in chunk_generator:
            yield chunk
            await asyncio.sleep(0)

    async def receive_responses(self):
        logger.info("Listening for responses...")

        text_done = False

        while not text_done:
            try:
                try:
                    response = await asyncio.wait_for(self.websocket.recv(), 10.0)
                except asyncio.TimeoutError:
                    continue

                event = json.loads(response)
                print(f"event: {event}")
                event_type = event.get("type", "")

                if event_type == "conversation.item.input_audio_transcription.delta":
                    delta = event.get("delta", "")
                    if self.speaker_diarization and "speaker" in event:
                        speaker = event.get("speaker", "Unknown")
                        logger.info(f"Speaker {speaker}: {delta}")
                        self.collected_text.append(f"[Speaker {speaker}] {delta}")
                    else:
                        logger.info("Transcript: %s", delta)
                        self.collected_text.append(delta)
                elif "error" in event_type.lower():
                    logger.error(f"Error: {event.get('error', {}).get('message', 'Unknown error')}")
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

