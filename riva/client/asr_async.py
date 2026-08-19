# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

"""Async ASR client using grpc.aio.

This module provides async/await support for Riva ASR streaming,
enabling efficient high-concurrency scenarios without thread overhead.

Example:
    async with AsyncAuth(uri="localhost:50051") as auth:
        service = ASRServiceAsync(auth)
        async for response in service.streaming_recognize(audio_gen, config):
            print(response.results)
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, Sequence

import grpc
import grpc.aio

from riva.client.proto import riva_asr_pb2 as rasr
from riva.client.proto import riva_asr_pb2_grpc as rasr_srv

__all__ = ["AsyncAuth", "ASRServiceAsync"]


class AsyncAuth:
    """Async-compatible authentication and channel management.

    Provides lazy channel creation with thread-safe initialization.
    Supports both insecure and SSL connections.

    Args:
        uri: Riva server address (host:port)
        use_ssl: Enable SSL/TLS
        ssl_root_cert: Path to root CA certificate (optional)
        ssl_client_cert: Path to client certificate for mTLS (optional)
        ssl_client_key: Path to client private key for mTLS (optional)
        metadata: List of (key, value) tuples for request metadata
        options: Additional gRPC channel options

    Example:
        # Simple insecure connection
        auth = AsyncAuth(uri="localhost:50051")

        # SSL with custom cert
        auth = AsyncAuth(uri="riva.example.com:443", use_ssl=True)

        # With API key metadata
        auth = AsyncAuth(
            uri="riva.example.com:443",
            use_ssl=True,
            metadata=[("x-api-key", "your-key")]
        )

        # As context manager (recommended)
        async with AsyncAuth(uri="localhost:50051") as auth:
            service = ASRServiceAsync(auth)
            # use service...
    """

    # Default channel options for real-time streaming
    DEFAULT_OPTIONS: Sequence[tuple[str, int | bool]] = (
        ("grpc.max_send_message_length", 50 * 1024 * 1024),     # 50MB
        ("grpc.max_receive_message_length", 50 * 1024 * 1024),  # 50MB
        ("grpc.keepalive_time_ms", 10_000),                      # 10 sec
        ("grpc.keepalive_timeout_ms", 5_000),                    # 5 sec
        ("grpc.keepalive_permit_without_calls", True),
        ("grpc.http2.min_ping_interval_without_data_ms", 5_000),
    )

    def __init__(
        self,
        uri: str,
        use_ssl: bool = False,
        ssl_root_cert: str | None = None,
        ssl_client_cert: str | None = None,
        ssl_client_key: str | None = None,
        metadata: Sequence[tuple[str, str]] | None = None,
        options: Sequence[tuple[str, int | bool | str]] | None = None,
    ) -> None:
        self.uri = uri
        self.use_ssl = use_ssl
        self.ssl_root_cert = ssl_root_cert
        self.ssl_client_cert = ssl_client_cert
        self.ssl_client_key = ssl_client_key
        self.metadata = list(metadata) if metadata else []
        self._options = list(options) if options else list(self.DEFAULT_OPTIONS)

        self._channel: grpc.aio.Channel | None = None
        self._lock = asyncio.Lock()

    async def get_channel(self) -> grpc.aio.Channel:
        """Get or create the async gRPC channel.

        Thread-safe: uses asyncio.Lock to ensure single channel creation
        even under concurrent access. Uses double-checked locking for
        fast-path optimization when channel already exists.

        Returns:
            The async gRPC channel
        """
        # Fast path: channel already exists
        if self._channel is not None:
            return self._channel
        # Slow path: acquire lock and create channel
        async with self._lock:
            if self._channel is None:
                self._channel = await self._create_channel()
            return self._channel

    async def _create_channel(self) -> grpc.aio.Channel:
        """Create the appropriate channel type based on SSL settings."""
        if self.use_ssl:
            credentials = await self._create_ssl_credentials()
            return grpc.aio.secure_channel(
                self.uri,
                credentials,
                options=self._options,
            )
        else:
            return grpc.aio.insecure_channel(
                self.uri,
                options=self._options,
            )

    async def _create_ssl_credentials(self) -> grpc.ChannelCredentials:
        """Create SSL credentials from certificate files.

        Uses asyncio.to_thread() for non-blocking file I/O.
        """

        def _read_file(path: str) -> bytes:
            with open(path, "rb") as f:
                return f.read()

        root_cert = None
        client_cert = None
        client_key = None

        if self.ssl_root_cert:
            root_cert = await asyncio.to_thread(_read_file, self.ssl_root_cert)

        if self.ssl_client_cert:
            client_cert = await asyncio.to_thread(_read_file, self.ssl_client_cert)

        if self.ssl_client_key:
            client_key = await asyncio.to_thread(_read_file, self.ssl_client_key)

        return grpc.ssl_channel_credentials(
            root_certificates=root_cert,
            private_key=client_key,
            certificate_chain=client_cert,
        )

    def get_auth_metadata(self) -> list[tuple[str, str]]:
        """Get metadata to include with RPC calls.

        Returns:
            List of (key, value) metadata tuples
        """
        return self.metadata

    async def close(self) -> None:
        """Close the channel and release resources."""
        async with self._lock:
            if self._channel is not None:
                await self._channel.close()
                self._channel = None

    async def __aenter__(self) -> "AsyncAuth":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - ensures cleanup."""
        await self.close()


class ASRServiceAsync:
    """Async ASR service using grpc.aio.

    Provides async streaming and batch recognition methods that can handle
    many concurrent streams without thread overhead.

    Args:
        auth: AsyncAuth instance for channel management

    Example:
        auth = AsyncAuth(uri="localhost:50051")
        service = ASRServiceAsync(auth)

        # Streaming recognition
        async def audio_generator():
            while audio_available:
                yield audio_chunk

        async for response in service.streaming_recognize(
            audio_generator(),
            streaming_config
        ):
            for result in response.results:
                print(result.alternatives[0].transcript)

        await auth.close()
    """

    def __init__(self, auth: AsyncAuth) -> None:
        self.auth = auth
        self._stub: "rasr_srv.RivaSpeechRecognitionStub | None" = None
        self._stub_lock = asyncio.Lock()
        # Cache metadata reference to avoid repeated method calls
        self._metadata = auth.get_auth_metadata() or None

    async def _get_stub(self) -> "rasr_srv.RivaSpeechRecognitionStub":
        """Get or create the gRPC stub.

        Thread-safe stub creation with double-checked locking for
        fast-path optimization when stub already exists.
        """
        # Fast path: stub already exists
        if self._stub is not None:
            return self._stub
        # Slow path: acquire lock and create stub
        async with self._stub_lock:
            if self._stub is None:
                channel = await self.auth.get_channel()
                self._stub = rasr_srv.RivaSpeechRecognitionStub(channel)
            return self._stub

    async def streaming_recognize(
        self,
        audio_chunks: AsyncIterator[bytes],
        streaming_config: "rasr.StreamingRecognitionConfig",
    ) -> AsyncIterator["rasr.StreamingRecognizeResponse"]:
        """Perform async streaming speech recognition.

        This is the primary method for real-time speech recognition.
        Audio is streamed to the server and partial/final results are
        yielded as they become available.

        Args:
            audio_chunks: Async iterator yielding raw audio bytes
                (LINEAR_PCM format recommended, 16-bit, mono)
            streaming_config: Configuration including sample rate,
                language, and interim_results setting

        Yields:
            StreamingRecognizeResponse objects containing transcription
            results. Check result.is_final to distinguish partial from
            final results.

        Raises:
            grpc.aio.AioRpcError: On gRPC communication errors

        Example:
            config = StreamingRecognitionConfig(
                config=RecognitionConfig(
                    encoding=AudioEncoding.LINEAR_PCM,
                    sample_rate_hertz=16000,
                    language_code="en-US",
                ),
                interim_results=True,
            )

            async for response in service.streaming_recognize(
                audio_generator(), config
            ):
                for result in response.results:
                    transcript = result.alternatives[0].transcript
                    if result.is_final:
                        print(f"Final: {transcript}")
                    else:
                        print(f"Partial: {transcript}")
        """
        stub = await self._get_stub()
        metadata = self._metadata

        async def request_generator() -> AsyncIterator[rasr.StreamingRecognizeRequest]:
            # First request: config only (no audio)
            yield rasr.StreamingRecognizeRequest(streaming_config=streaming_config)
            # Subsequent requests: audio only
            async for chunk in audio_chunks:
                yield rasr.StreamingRecognizeRequest(audio_content=chunk)

        call = stub.StreamingRecognize(
            request_generator(),
            metadata=metadata,
        )

        async for response in call:
            yield response

    async def recognize(
        self,
        audio_bytes: bytes,
        config: "rasr.RecognitionConfig",
    ) -> "rasr.RecognizeResponse":
        """Perform async batch (offline) speech recognition.

        Use this for complete audio files rather than streaming.

        Args:
            audio_bytes: Complete audio data
            config: Recognition configuration

        Returns:
            RecognizeResponse with transcription results

        Raises:
            grpc.aio.AioRpcError: On gRPC communication errors
        """
        stub = await self._get_stub()
        metadata = self._metadata

        request = rasr.RecognizeRequest(config=config, audio=audio_bytes)
        return await stub.Recognize(request, metadata=metadata)

    async def get_config(self) -> "rasr.RivaSpeechRecognitionConfigResponse":
        """Get the server's speech recognition configuration.

        Returns:
            Configuration response with available models and settings
        """
        stub = await self._get_stub()
        metadata = self._metadata

        request = rasr.RivaSpeechRecognitionConfigRequest()
        return await stub.GetRivaSpeechRecognitionConfig(request, metadata=metadata)
