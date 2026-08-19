# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

"""Performance benchmarks for async ASR client.

Run with a Riva server:
    RIVA_URI=localhost:50051 pytest tests/benchmarks/ -v -s

Run client overhead tests (no server required):
    pytest tests/benchmarks/ -v -s -k "overhead"
"""

from __future__ import annotations

import asyncio
import os
import time
import wave
from pathlib import Path
from typing import AsyncIterator, List

import pytest

from riva.client.proto import riva_asr_pb2 as rasr
from riva.client.proto import riva_audio_pb2 as riva_audio

# Audio sample directory
AUDIO_DIR = Path(__file__).parent.parent.parent / "data" / "examples"

pytestmark = pytest.mark.benchmark


class TestClientOverhead:
    """Measure client-side overhead without server."""

    def test_protobuf_creation_overhead(self) -> None:
        """Measure time to create StreamingRecognizeRequest messages.

        Target: < 100μs per request creation.
        """
        iterations = 10000
        audio_chunk = b"x" * 3200  # 100ms of 16-bit 16kHz audio

        start = time.perf_counter()
        for _ in range(iterations):
            request = rasr.StreamingRecognizeRequest(audio_content=audio_chunk)
        elapsed = time.perf_counter() - start

        avg_time_us = (elapsed / iterations) * 1_000_000
        print(f"\nProtobuf creation: {avg_time_us:.2f} μs/request")
        print(f"Total time for {iterations} requests: {elapsed * 1000:.2f} ms")

        # Should be under 100μs per request
        assert avg_time_us < 100, f"Protobuf creation too slow: {avg_time_us:.2f} μs"

    def test_config_creation_overhead(self) -> None:
        """Measure time to create recognition config.

        Target: < 200μs per config creation.
        """
        iterations = 5000

        start = time.perf_counter()
        for _ in range(iterations):
            config = rasr.StreamingRecognitionConfig(
                config=rasr.RecognitionConfig(
                    encoding=riva_audio.AudioEncoding.LINEAR_PCM,
                    sample_rate_hertz=16000,
                    language_code="en-US",
                    max_alternatives=1,
                    enable_automatic_punctuation=True,
                ),
                interim_results=True,
            )
        elapsed = time.perf_counter() - start

        avg_time_us = (elapsed / iterations) * 1_000_000
        print(f"\nConfig creation: {avg_time_us:.2f} μs/config")

        assert avg_time_us < 200, f"Config creation too slow: {avg_time_us:.2f} μs"

    @pytest.mark.asyncio
    async def test_async_generator_overhead(self) -> None:
        """Measure overhead of async generator iteration.

        Target: < 50μs per async yield.
        """
        iterations = 10000
        chunk = b"x" * 3200

        async def audio_generator() -> AsyncIterator[bytes]:
            for _ in range(iterations):
                yield chunk

        start = time.perf_counter()
        count = 0
        async for _ in audio_generator():
            count += 1
        elapsed = time.perf_counter() - start

        avg_time_us = (elapsed / count) * 1_000_000
        print(f"\nAsync generator: {avg_time_us:.2f} μs/yield")

        assert avg_time_us < 50, f"Async generator too slow: {avg_time_us:.2f} μs"


@pytest.mark.skipif(
    not os.getenv("RIVA_URI"),
    reason="RIVA_URI not set - skipping server benchmarks"
)
class TestEndToEndLatency:
    """Benchmark end-to-end latency with a running server."""

    @pytest.fixture
    def en_us_sample(self) -> Path:
        """Path to en-US sample audio file."""
        path = AUDIO_DIR / "en-US_sample.wav"
        if not path.exists():
            pytest.skip(f"Audio sample not found: {path}")
        return path

    @pytest.fixture
    def riva_uri(self) -> str:
        """Get Riva server URI from environment."""
        return os.environ["RIVA_URI"]

    @pytest.mark.asyncio
    async def test_time_to_first_result(
        self, riva_uri: str, en_us_sample: Path
    ) -> None:
        """Measure time from first audio chunk to first response."""
        from riva.client.asr_async import ASRServiceAsync, AsyncAuth

        with wave.open(str(en_us_sample), "rb") as wf:
            sample_rate = wf.getframerate()

        async with AsyncAuth(uri=riva_uri) as auth:
            service = ASRServiceAsync(auth)

            config = rasr.StreamingRecognitionConfig(
                config=rasr.RecognitionConfig(
                    encoding=riva_audio.AudioEncoding.LINEAR_PCM,
                    sample_rate_hertz=sample_rate,
                    language_code="en-US",
                    max_alternatives=1,
                ),
                interim_results=True,
            )

            async def timed_audio_generator() -> AsyncIterator[bytes]:
                with wave.open(str(en_us_sample), "rb") as wf:
                    while True:
                        data = wf.readframes(1600)  # 100ms chunks
                        if not data:
                            break
                        yield data

            # Measure time to first response
            start = time.perf_counter()
            first_response_time = None

            async for response in service.streaming_recognize(
                timed_audio_generator(), config
            ):
                if first_response_time is None:
                    first_response_time = time.perf_counter() - start
                # Continue to consume all responses

            print(f"\nTime to first response: {first_response_time * 1000:.2f} ms")

    @pytest.mark.asyncio
    async def test_concurrent_stream_throughput(
        self, riva_uri: str, en_us_sample: Path
    ) -> None:
        """Compare 4 concurrent streams vs 4 sequential streams."""
        from riva.client.asr_async import ASRServiceAsync, AsyncAuth

        with wave.open(str(en_us_sample), "rb") as wf:
            sample_rate = wf.getframerate()

        async def run_single_stream() -> float:
            """Run one stream and return duration."""
            async with AsyncAuth(uri=riva_uri) as auth:
                service = ASRServiceAsync(auth)

                config = rasr.StreamingRecognitionConfig(
                    config=rasr.RecognitionConfig(
                        encoding=riva_audio.AudioEncoding.LINEAR_PCM,
                        sample_rate_hertz=sample_rate,
                        language_code="en-US",
                    ),
                    interim_results=False,
                )

                async def audio_gen() -> AsyncIterator[bytes]:
                    with wave.open(str(en_us_sample), "rb") as wf:
                        while True:
                            data = wf.readframes(1600)
                            if not data:
                                break
                            yield data

                start = time.perf_counter()
                async for _ in service.streaming_recognize(audio_gen(), config):
                    pass
                return time.perf_counter() - start

        num_streams = 4

        # Sequential execution
        seq_start = time.perf_counter()
        for _ in range(num_streams):
            await run_single_stream()
        sequential_time = time.perf_counter() - seq_start

        # Concurrent execution
        conc_start = time.perf_counter()
        await asyncio.gather(*[run_single_stream() for _ in range(num_streams)])
        concurrent_time = time.perf_counter() - conc_start

        speedup = sequential_time / concurrent_time
        print(f"\n{num_streams} sequential streams: {sequential_time * 1000:.2f} ms")
        print(f"{num_streams} concurrent streams: {concurrent_time * 1000:.2f} ms")
        print(f"Speedup: {speedup:.2f}x")

        # Concurrent should be faster (expect at least 1.5x speedup)
        assert speedup > 1.5, f"Concurrent speedup too low: {speedup:.2f}x"


@pytest.mark.skipif(
    not os.getenv("RIVA_URI"),
    reason="RIVA_URI not set - skipping server benchmarks"
)
class TestMemoryUsage:
    """Benchmark memory usage patterns."""

    @pytest.fixture
    def en_us_sample(self) -> Path:
        """Path to en-US sample audio file."""
        path = AUDIO_DIR / "en-US_sample.wav"
        if not path.exists():
            pytest.skip(f"Audio sample not found: {path}")
        return path

    @pytest.fixture
    def riva_uri(self) -> str:
        """Get Riva server URI from environment."""
        return os.environ["RIVA_URI"]

    @pytest.mark.asyncio
    async def test_many_short_streams_no_leak(
        self, riva_uri: str, en_us_sample: Path
    ) -> None:
        """Run many short streams to check for resource leaks."""
        import gc

        from riva.client.asr_async import ASRServiceAsync, AsyncAuth

        with wave.open(str(en_us_sample), "rb") as wf:
            sample_rate = wf.getframerate()
            # Read just first 0.5 seconds
            short_audio = wf.readframes(sample_rate // 2)

        num_streams = 20

        async def run_short_stream() -> None:
            async with AsyncAuth(uri=riva_uri) as auth:
                service = ASRServiceAsync(auth)

                config = rasr.StreamingRecognitionConfig(
                    config=rasr.RecognitionConfig(
                        encoding=riva_audio.AudioEncoding.LINEAR_PCM,
                        sample_rate_hertz=sample_rate,
                        language_code="en-US",
                    ),
                    interim_results=False,
                )

                async def audio_gen() -> AsyncIterator[bytes]:
                    # Single chunk
                    yield short_audio

                async for _ in service.streaming_recognize(audio_gen(), config):
                    pass

        # Run many streams
        for i in range(num_streams):
            await run_short_stream()
            if i % 5 == 0:
                gc.collect()

        # Force GC
        gc.collect()
        print(f"\nCompleted {num_streams} short streams")
