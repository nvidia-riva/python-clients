#!/usr/bin/env python3

import asyncio
import base64
import json
import logging
import queue
import time

import librosa
import numpy as np
import pyaudio
import websockets
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class RealtimeASRClient:
    def __init__(self, server_url: str, endpoint: str, query_params: str, input_sample_rate: int, input_chunk_size_samples: int):
        self.server_url = server_url
        self.endpoint = endpoint
        self.query_params = query_params
        self.input_sample_rate = input_sample_rate
        self.input_chunk_size_samples = input_chunk_size_samples
        self.websocket = None

        # Input audio playback
        self.input_audio_queue = queue.Queue()
        self.input_playback_thread = None
        self.is_input_playing = False
        self.input_buffer_size = 1024  # Buffer size for input audio playback

        self.collected_text = []

    async def connect(self):
        url = f"{self.server_url}{self.endpoint}?{self.query_params}"

        self.websocket = await websockets.connect(
            url,
        )

        await self._initialize_session()

    async def _initialize_session(self):
        response = await self.websocket.recv()
        response_data = json.loads(response)
        logger.info("Session created: %s", response_data)

        response_data.pop("event_id")
        response_data["session_config"].pop("id")

        response_data["type"] = "transcription_session.update"

        await self.websocket.send(json.dumps(response_data))
        response = await self.websocket.recv()
        response_data = json.loads(response)

        logger.info("Session updated: %s", response_data)

    async def _send_message(self, message):
        await self.websocket.send(json.dumps(message))

    def get_audio_chunks(self, audio_file):
        logger.info(f"Loading audio: {audio_file}")
        audio_signal, sr = librosa.load(audio_file, sr=self.input_sample_rate)

        if len(audio_signal.shape) > 1:
            audio_signal = np.mean(audio_signal, axis=1)

        chunks = []
        for i in range(0, len(audio_signal), self.input_chunk_size_samples):
            chunk = audio_signal[i : i + self.input_chunk_size_samples]

            if len(chunk) < self.input_chunk_size_samples:
                chunk = np.pad(chunk, (0, self.input_chunk_size_samples - len(chunk)))

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
            # Handle pre-recorded chunks from file
            for _, chunk in tqdm(enumerate(audio_chunks)):
                chunk_base64 = base64.b64encode(chunk).decode("utf-8")

                await self._send_message(
                    {
                        "type": "input_audio_buffer.append",
                        "audio": chunk_base64,
                    }
                )
                await asyncio.sleep(0.1)
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
                event_type = event.get("type", "")

                if event_type == "conversation.item.input_audio_transcription.delta":
                    logger.info("Transcript: %s", event.get("delta"))
                    self.collected_text.append(event.get("delta"))
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

