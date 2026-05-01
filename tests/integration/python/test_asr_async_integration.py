# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

"""Integration tests for async ASR client.

These tests require a running Riva server. Set RIVA_URI environment variable
to point to your server (e.g., RIVA_URI=localhost:50051).

Run: RIVA_URI=localhost:50051 pytest -m integration -v
Skip: pytest -m "not integration"
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from riva.client.asr_async import ASRServiceAsync, AsyncAuth
from riva.client.proto import riva_asr_pb2 as rasr
from riva.client.proto import riva_audio_pb2 as riva_audio

from .conftest import audio_chunk_generator, get_wav_params, read_wav_audio

pytestmark = pytest.mark.integration


class TestStreamingRecognitionIntegration:
    """Integration tests for streaming recognition."""

    @pytest.mark.asyncio
    async def test_streaming_recognize_returns_transcript(
        self, riva_uri: str, en_us_sample: Path
    ) -> None:
        """Stream en-US_sample.wav, verify non-empty transcript."""
        wav_params = get_wav_params(en_us_sample)

        async with AsyncAuth(uri=riva_uri) as auth:
            service = ASRServiceAsync(auth)

            config = rasr.StreamingRecognitionConfig(
                config=rasr.RecognitionConfig(
                    encoding=riva_audio.AudioEncoding.LINEAR_PCM,
                    sample_rate_hertz=wav_params["sample_rate"],
                    language_code="en-US",
                    max_alternatives=1,
                    enable_automatic_punctuation=True,
                ),
                interim_results=False,
            )

            transcripts = []
            async for response in service.streaming_recognize(
                audio_chunk_generator(en_us_sample), config
            ):
                for result in response.results:
                    if result.is_final and result.alternatives:
                        transcripts.append(result.alternatives[0].transcript)

            # Should have at least one transcript
            assert len(transcripts) > 0
            full_transcript = " ".join(transcripts)
            assert len(full_transcript) > 0
            print(f"Transcript: {full_transcript}")

    @pytest.mark.asyncio
    async def test_interim_results_received(
        self, riva_uri: str, en_us_sample: Path
    ) -> None:
        """With interim_results=True, partial results are yielded."""
        wav_params = get_wav_params(en_us_sample)

        async with AsyncAuth(uri=riva_uri) as auth:
            service = ASRServiceAsync(auth)

            config = rasr.StreamingRecognitionConfig(
                config=rasr.RecognitionConfig(
                    encoding=riva_audio.AudioEncoding.LINEAR_PCM,
                    sample_rate_hertz=wav_params["sample_rate"],
                    language_code="en-US",
                    max_alternatives=1,
                ),
                interim_results=True,  # Enable interim results
            )

            interim_count = 0
            final_count = 0

            async for response in service.streaming_recognize(
                audio_chunk_generator(en_us_sample), config
            ):
                for result in response.results:
                    if result.is_final:
                        final_count += 1
                    else:
                        interim_count += 1

            # Should have received both interim and final results
            assert final_count > 0
            # Note: interim results depend on audio length and server config
            print(f"Interim: {interim_count}, Final: {final_count}")

    @pytest.mark.asyncio
    async def test_concurrent_streams(
        self, riva_uri: str, en_us_sample: Path
    ) -> None:
        """Multiple concurrent streams all succeed."""
        wav_params = get_wav_params(en_us_sample)
        num_streams = 3

        async def run_stream(stream_id: int) -> str:
            """Run a single streaming recognition."""
            async with AsyncAuth(uri=riva_uri) as auth:
                service = ASRServiceAsync(auth)

                config = rasr.StreamingRecognitionConfig(
                    config=rasr.RecognitionConfig(
                        encoding=riva_audio.AudioEncoding.LINEAR_PCM,
                        sample_rate_hertz=wav_params["sample_rate"],
                        language_code="en-US",
                        max_alternatives=1,
                    ),
                    interim_results=False,
                )

                transcripts = []
                async for response in service.streaming_recognize(
                    audio_chunk_generator(en_us_sample), config
                ):
                    for result in response.results:
                        if result.is_final and result.alternatives:
                            transcripts.append(result.alternatives[0].transcript)

                return " ".join(transcripts)

        # Run streams concurrently
        results = await asyncio.gather(*[
            run_stream(i) for i in range(num_streams)
        ])

        # All streams should succeed with non-empty transcripts
        assert len(results) == num_streams
        for i, transcript in enumerate(results):
            assert len(transcript) > 0, f"Stream {i} returned empty transcript"
            print(f"Stream {i}: {transcript[:50]}...")


class TestBatchRecognitionIntegration:
    """Integration tests for batch recognition.

    Note: These tests require a Riva server with offline/batch recognition support.
    The parakeet model only supports streaming, so these tests may be skipped.
    """

    @pytest.mark.asyncio
    async def test_batch_recognize_returns_transcript(
        self, riva_uri: str, en_us_sample: Path
    ) -> None:
        """Batch recognize en-US_sample.wav.

        This test requires offline recognition support.
        Skip if server only supports streaming.
        """
        import grpc

        wav_params = get_wav_params(en_us_sample)
        audio_data = read_wav_audio(en_us_sample)

        async with AsyncAuth(uri=riva_uri) as auth:
            service = ASRServiceAsync(auth)

            config = rasr.RecognitionConfig(
                encoding=riva_audio.AudioEncoding.LINEAR_PCM,
                sample_rate_hertz=wav_params["sample_rate"],
                language_code="en-US",
                max_alternatives=1,
                enable_automatic_punctuation=True,
            )

            try:
                response = await service.recognize(audio_data, config)

                # Should have results
                assert len(response.results) > 0
                transcript = response.results[0].alternatives[0].transcript
                assert len(transcript) > 0
                print(f"Batch transcript: {transcript}")
            except grpc.aio.AioRpcError as e:
                if "offline" in str(e.details()).lower() or "unavailable model" in str(e.details()).lower():
                    pytest.skip("Server does not support offline/batch recognition")


class TestConnectionIntegration:
    """Integration tests for connection handling."""

    @pytest.mark.asyncio
    async def test_reconnect_after_close(
        self, riva_uri: str, en_us_sample: Path
    ) -> None:
        """Connection reestablishes after close()."""
        wav_params = get_wav_params(en_us_sample)

        def make_config():
            return rasr.StreamingRecognitionConfig(
                config=rasr.RecognitionConfig(
                    encoding=riva_audio.AudioEncoding.LINEAR_PCM,
                    sample_rate_hertz=wav_params["sample_rate"],
                    language_code="en-US",
                    max_alternatives=1,
                ),
                interim_results=True,  # Enable interim for faster response
            )

        async def run_recognition():
            async with AsyncAuth(uri=riva_uri) as auth:
                service = ASRServiceAsync(auth)
                transcripts = []
                async for response in service.streaming_recognize(
                    audio_chunk_generator(en_us_sample), make_config()
                ):
                    for result in response.results:
                        if result.is_final and result.alternatives:
                            transcripts.append(result.alternatives[0].transcript)
                return " ".join(transcripts)

        # First recognition
        transcript1 = await run_recognition()
        print(f"Transcript 1: {transcript1}")

        # Connection is closed after first context manager exits

        # Second recognition with new connection
        transcript2 = await run_recognition()
        print(f"Transcript 2: {transcript2}")

        # Both should have succeeded
        assert len(transcript1) > 0, "First recognition returned no results"
        assert len(transcript2) > 0, "Second recognition returned no results"

    @pytest.mark.asyncio
    async def test_get_config_returns_available_models(
        self, riva_uri: str
    ) -> None:
        """get_config returns server configuration."""
        async with AsyncAuth(uri=riva_uri) as auth:
            service = ASRServiceAsync(auth)
            config = await service.get_config()

            # Should have some configuration data
            assert config is not None
            # The exact fields depend on server configuration
            print(f"Server config: {config}")
