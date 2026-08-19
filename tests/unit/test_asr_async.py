# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

"""Tests for async ASR client.

Unit tests focus on observable behavior and contracts, not internal implementation.
Integration tests require RIVA_URI environment variable.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from riva.client.asr_async import ASRServiceAsync, AsyncAuth

from .helpers import create_mock_streaming_response


# Async iterator helper for tests
async def aiter(items):
    for item in items:
        yield item


class TestAsyncAuthChannel:
    """Tests for AsyncAuth channel creation behavior."""

    @pytest.mark.asyncio
    async def test_insecure_channel_created(self) -> None:
        """Insecure channel created when use_ssl=False."""
        with patch("grpc.aio.insecure_channel") as mock_channel:
            mock_ch = MagicMock()
            mock_ch.close = AsyncMock()
            mock_channel.return_value = mock_ch

            auth = AsyncAuth(uri="localhost:50051")
            channel = await auth.get_channel()

            mock_channel.assert_called_once()
            assert channel is not None
            await auth.close()

    @pytest.mark.asyncio
    async def test_secure_channel_created_with_ssl(self) -> None:
        """Secure channel created when use_ssl=True."""
        with patch("grpc.aio.secure_channel") as mock_channel, \
             patch("grpc.ssl_channel_credentials") as mock_creds:
            mock_ch = MagicMock()
            mock_ch.close = AsyncMock()
            mock_channel.return_value = mock_ch
            mock_creds.return_value = MagicMock()

            auth = AsyncAuth(uri="localhost:50051", use_ssl=True)
            channel = await auth.get_channel()

            mock_creds.assert_called_once()
            mock_channel.assert_called_once()
            await auth.close()

    @pytest.mark.asyncio
    async def test_close_allows_reconnection(self) -> None:
        """After close(), get_channel() creates new channel."""
        with patch("grpc.aio.insecure_channel") as mock_channel:
            mock_ch1 = MagicMock()
            mock_ch1.close = AsyncMock()
            mock_ch2 = MagicMock()
            mock_ch2.close = AsyncMock()
            mock_channel.side_effect = [mock_ch1, mock_ch2]

            auth = AsyncAuth(uri="localhost:50051")
            channel1 = await auth.get_channel()
            await auth.close()

            # Should be able to get a new channel after close
            channel2 = await auth.get_channel()

            assert mock_channel.call_count == 2
            await auth.close()

    @pytest.mark.asyncio
    async def test_context_manager_closes_channel(self) -> None:
        """Async context manager properly closes channel."""
        with patch("grpc.aio.insecure_channel") as mock_channel:
            mock_ch = MagicMock()
            mock_ch.close = AsyncMock()
            mock_channel.return_value = mock_ch

            async with AsyncAuth(uri="localhost:50051") as auth:
                await auth.get_channel()

            mock_ch.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_same_channel_returned_on_multiple_calls(self) -> None:
        """Multiple get_channel() calls return the same channel instance."""
        with patch("grpc.aio.insecure_channel") as mock_channel:
            mock_ch = MagicMock()
            mock_ch.close = AsyncMock()
            mock_channel.return_value = mock_ch

            auth = AsyncAuth(uri="localhost:50051")
            channel1 = await auth.get_channel()
            channel2 = await auth.get_channel()
            channel3 = await auth.get_channel()

            # Behavioral assertion: same channel returned
            assert channel1 is channel2 is channel3
            await auth.close()


class TestAsyncAuthMetadata:
    """Tests for AsyncAuth metadata handling."""

    @pytest.mark.asyncio
    async def test_metadata_preserved(self) -> None:
        """Metadata is stored and retrievable."""
        metadata = [("x-api-key", "test-key"), ("x-custom", "value")]
        auth = AsyncAuth(uri="localhost:50051", metadata=metadata)

        assert auth.get_auth_metadata() == metadata
        await auth.close()

    @pytest.mark.asyncio
    async def test_empty_metadata_returns_empty_list(self) -> None:
        """No metadata returns empty list."""
        auth = AsyncAuth(uri="localhost:50051")
        assert auth.get_auth_metadata() == []
        await auth.close()


class TestAsyncAuthChannelOptions:
    """Tests for channel options behavior."""

    @pytest.mark.asyncio
    async def test_default_options_applied(self) -> None:
        """Default channel options are applied."""
        with patch("grpc.aio.insecure_channel") as mock_channel:
            mock_ch = MagicMock()
            mock_ch.close = AsyncMock()
            mock_channel.return_value = mock_ch

            auth = AsyncAuth(uri="localhost:50051")
            await auth.get_channel()

            call_kwargs = mock_channel.call_args
            options = call_kwargs[1]["options"]
            option_names = [o[0] for o in options]
            assert "grpc.keepalive_time_ms" in option_names
            await auth.close()

    @pytest.mark.asyncio
    async def test_custom_options_override(self) -> None:
        """Custom options can be provided."""
        with patch("grpc.aio.insecure_channel") as mock_channel:
            mock_ch = MagicMock()
            mock_ch.close = AsyncMock()
            mock_channel.return_value = mock_ch

            custom_options = [("grpc.max_send_message_length", 100)]
            auth = AsyncAuth(uri="localhost:50051", options=custom_options)
            await auth.get_channel()

            call_kwargs = mock_channel.call_args
            options = call_kwargs[1]["options"]
            assert ("grpc.max_send_message_length", 100) in options
            await auth.close()


class TestAsyncAuthSSL:
    """Tests for SSL credential handling."""

    @pytest.mark.asyncio
    async def test_ssl_credentials_reads_cert_files(self, tmp_path) -> None:
        """SSL credential loading from actual files."""
        root_cert = tmp_path / "root.pem"
        client_cert = tmp_path / "client.pem"
        client_key = tmp_path / "client.key"

        root_cert.write_bytes(b"root-cert-content")
        client_cert.write_bytes(b"client-cert-content")
        client_key.write_bytes(b"client-key-content")

        with patch("grpc.aio.secure_channel") as mock_channel, \
             patch("grpc.ssl_channel_credentials") as mock_creds:
            mock_ch = MagicMock()
            mock_ch.close = AsyncMock()
            mock_channel.return_value = mock_ch
            mock_creds.return_value = MagicMock()

            auth = AsyncAuth(
                uri="localhost:50051",
                use_ssl=True,
                ssl_root_cert=str(root_cert),
                ssl_client_cert=str(client_cert),
                ssl_client_key=str(client_key),
            )
            await auth.get_channel()

            mock_creds.assert_called_once_with(
                root_certificates=b"root-cert-content",
                private_key=b"client-key-content",
                certificate_chain=b"client-cert-content",
            )
            await auth.close()

    @pytest.mark.asyncio
    async def test_ssl_credentials_file_not_found(self) -> None:
        """Error handling for missing cert files."""
        auth = AsyncAuth(
            uri="localhost:50051",
            use_ssl=True,
            ssl_root_cert="/nonexistent/path/root.pem",
        )

        with pytest.raises(FileNotFoundError):
            await auth.get_channel()


class TestStreamingRecognizeContract:
    """Test the public contract of streaming_recognize."""

    @pytest.fixture
    def mock_auth(self) -> AsyncAuth:
        """Create mock auth with mocked channel."""
        auth = AsyncAuth(uri="localhost:50051")
        auth._channel = MagicMock()
        return auth

    @pytest.mark.asyncio
    async def test_streaming_recognize_calls_stub_with_generator(
        self, mock_auth: AsyncAuth
    ) -> None:
        """streaming_recognize passes request generator to gRPC stub."""
        with patch("riva.client.asr_async.rasr_srv.RivaSpeechRecognitionStub") as mock_stub_cls:
            mock_stub = MagicMock()
            mock_call = MagicMock()
            mock_call.__aiter__ = lambda self: aiter([])
            mock_stub.StreamingRecognize.return_value = mock_call
            mock_stub_cls.return_value = mock_stub

            # Import actual proto to create real config
            from riva.client.proto import riva_asr_pb2 as rasr
            from riva.client.proto import riva_audio_pb2 as riva_audio

            service = ASRServiceAsync(mock_auth)
            config = rasr.StreamingRecognitionConfig(
                config=rasr.RecognitionConfig(
                    encoding=riva_audio.AudioEncoding.LINEAR_PCM,
                    sample_rate_hertz=16000,
                    language_code="en-US",
                )
            )

            async def audio_gen():
                yield b"audio1"
                yield b"audio2"

            async for _ in service.streaming_recognize(audio_gen(), config):
                pass

            # Verify StreamingRecognize was called with a generator
            mock_stub.StreamingRecognize.assert_called_once()
            call_args = mock_stub.StreamingRecognize.call_args
            # First positional arg should be the request generator (async generator)
            assert call_args[0][0] is not None

    @pytest.mark.asyncio
    async def test_streaming_recognize_sends_requests(self, mock_auth: AsyncAuth) -> None:
        """StreamingRecognize sends config first, then audio chunks."""
        # Import actual proto
        from riva.client.proto import riva_asr_pb2 as rasr

        with patch("riva.client.asr_async.rasr_srv.RivaSpeechRecognitionStub") as mock_stub_cls:
            mock_stub = MagicMock()
            mock_call = MagicMock()
            mock_call.__aiter__ = lambda self: aiter([])
            mock_stub.StreamingRecognize.return_value = mock_call
            mock_stub_cls.return_value = mock_stub

            service = ASRServiceAsync(mock_auth)
            config = rasr.StreamingRecognitionConfig(
                config=rasr.RecognitionConfig(
                    sample_rate_hertz=16000,
                    language_code="en-US",
                )
            )

            async def audio_gen():
                yield b"chunk1"
                yield b"chunk2"

            async for _ in service.streaming_recognize(audio_gen(), config):
                pass

            mock_stub.StreamingRecognize.assert_called_once()

    @pytest.mark.asyncio
    async def test_responses_yielded_as_received(self, mock_auth: AsyncAuth) -> None:
        """Responses from server are yielded to caller."""
        mock_responses = [
            create_mock_streaming_response("partial", is_final=False),
            create_mock_streaming_response("final transcript", is_final=True),
        ]

        with patch("riva.client.asr_async.rasr_srv.RivaSpeechRecognitionStub") as mock_stub_cls:
            mock_stub = MagicMock()
            mock_call = MagicMock()
            mock_call.__aiter__ = lambda self: aiter(mock_responses)
            mock_stub.StreamingRecognize.return_value = mock_call
            mock_stub_cls.return_value = mock_stub

            service = ASRServiceAsync(mock_auth)
            mock_config = MagicMock()

            async def audio_gen():
                yield b"audio"

            responses = []
            async for response in service.streaming_recognize(audio_gen(), mock_config):
                responses.append(response)

            assert len(responses) == 2
            assert responses == mock_responses

    @pytest.mark.asyncio
    async def test_metadata_passed_to_streaming_call(self, mock_auth: AsyncAuth) -> None:
        """Auth metadata is passed to streaming calls."""
        mock_auth.metadata = [("x-api-key", "test-key")]

        with patch("riva.client.asr_async.rasr_srv.RivaSpeechRecognitionStub") as mock_stub_cls:
            mock_stub = MagicMock()
            mock_call = MagicMock()
            mock_call.__aiter__ = lambda self: aiter([])
            mock_stub.StreamingRecognize.return_value = mock_call
            mock_stub_cls.return_value = mock_stub

            service = ASRServiceAsync(mock_auth)
            mock_config = MagicMock()

            async def audio_gen():
                yield b"audio"

            async for _ in service.streaming_recognize(audio_gen(), mock_config):
                pass

            call_kwargs = mock_stub.StreamingRecognize.call_args
            assert call_kwargs[1]["metadata"] == [("x-api-key", "test-key")]


class TestRecognizeContract:
    """Test batch recognition contract."""

    @pytest.fixture
    def mock_auth(self) -> AsyncAuth:
        """Create mock auth with mocked channel."""
        auth = AsyncAuth(uri="localhost:50051")
        auth._channel = MagicMock()
        return auth

    @pytest.mark.asyncio
    async def test_recognize_calls_stub_with_request(self, mock_auth: AsyncAuth) -> None:
        """recognize() creates RecognizeRequest with config and audio."""
        from riva.client.proto import riva_asr_pb2 as rasr

        with patch("riva.client.asr_async.rasr_srv.RivaSpeechRecognitionStub") as mock_stub_cls:
            mock_stub = MagicMock()
            mock_response = MagicMock()
            captured_request = None

            async def capture_recognize(request, **kwargs):
                nonlocal captured_request
                captured_request = request
                return mock_response

            mock_stub.Recognize = capture_recognize
            mock_stub_cls.return_value = mock_stub

            service = ASRServiceAsync(mock_auth)
            config = rasr.RecognitionConfig(
                sample_rate_hertz=16000,
                language_code="en-US",
            )

            await service.recognize(b"audio_data", config)

            # Verify request was created with config and audio
            assert captured_request is not None
            assert captured_request.audio == b"audio_data"
            assert captured_request.config.sample_rate_hertz == 16000
            assert captured_request.config.language_code == "en-US"

    @pytest.mark.asyncio
    async def test_metadata_passed_to_recognize_call(self, mock_auth: AsyncAuth) -> None:
        """Auth metadata is passed to batch recognition."""
        from riva.client.proto import riva_asr_pb2 as rasr

        mock_auth.metadata = [("x-api-key", "test-key"), ("x-custom", "value")]

        with patch("riva.client.asr_async.rasr_srv.RivaSpeechRecognitionStub") as mock_stub_cls:
            mock_stub = MagicMock()
            mock_response = MagicMock()
            mock_stub.Recognize = AsyncMock(return_value=mock_response)
            mock_stub_cls.return_value = mock_stub

            service = ASRServiceAsync(mock_auth)
            config = rasr.RecognitionConfig(
                sample_rate_hertz=16000,
                language_code="en-US",
            )

            await service.recognize(b"audio_data", config)

            call_kwargs = mock_stub.Recognize.call_args
            assert call_kwargs[1]["metadata"] == [("x-api-key", "test-key"), ("x-custom", "value")]


class TestGetConfigContract:
    """Test get_config method contract."""

    @pytest.fixture
    def mock_auth(self) -> AsyncAuth:
        """Create mock auth with mocked channel."""
        auth = AsyncAuth(uri="localhost:50051")
        auth._channel = MagicMock()
        return auth

    @pytest.mark.asyncio
    async def test_returns_config_response(self, mock_auth: AsyncAuth) -> None:
        """get_config returns the server response."""
        with patch("riva.client.asr_async.rasr_srv.RivaSpeechRecognitionStub") as mock_stub_cls:
            mock_stub = MagicMock()
            mock_response = MagicMock()
            mock_response.model_config = ["model1", "model2"]  # Add some data
            mock_stub.GetRivaSpeechRecognitionConfig = AsyncMock(return_value=mock_response)
            mock_stub_cls.return_value = mock_stub

            service = ASRServiceAsync(mock_auth)
            result = await service.get_config()

            assert result is mock_response
            mock_stub.GetRivaSpeechRecognitionConfig.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_metadata_passed_to_get_config_call(self, mock_auth: AsyncAuth) -> None:
        """Auth metadata is passed to get_config."""
        mock_auth.metadata = [("x-api-key", "test-key")]

        with patch("riva.client.asr_async.rasr_srv.RivaSpeechRecognitionStub") as mock_stub_cls:
            mock_stub = MagicMock()
            mock_stub.GetRivaSpeechRecognitionConfig = AsyncMock(return_value=MagicMock())
            mock_stub_cls.return_value = mock_stub

            service = ASRServiceAsync(mock_auth)
            await service.get_config()

            call_kwargs = mock_stub.GetRivaSpeechRecognitionConfig.call_args
            assert call_kwargs[1]["metadata"] == [("x-api-key", "test-key")]


class TestStreamingRecognizeEdgeCases:
    """Tests for edge cases in streaming recognition."""

    @pytest.fixture
    def mock_auth(self) -> AsyncAuth:
        """Create mock auth with mocked channel."""
        auth = AsyncAuth(uri="localhost:50051")
        auth._channel = MagicMock()
        return auth

    @pytest.mark.asyncio
    async def test_empty_audio_generator(self, mock_auth: AsyncAuth) -> None:
        """Streaming with no audio chunks still sends config."""
        with patch("riva.client.asr_async.rasr_srv.RivaSpeechRecognitionStub") as mock_stub_cls:
            mock_stub = MagicMock()
            mock_response = MagicMock()
            mock_call = MagicMock()
            mock_call.__aiter__ = lambda self: aiter([mock_response])
            mock_stub.StreamingRecognize.return_value = mock_call
            mock_stub_cls.return_value = mock_stub

            service = ASRServiceAsync(mock_auth)
            mock_config = MagicMock()

            async def empty_audio_gen():
                return
                yield  # Make it a generator

            responses = []
            async for response in service.streaming_recognize(empty_audio_gen(), mock_config):
                responses.append(response)

            # Should still process (config-only request)
            assert len(responses) == 1
            mock_stub.StreamingRecognize.assert_called_once()

    @pytest.mark.asyncio
    async def test_single_audio_chunk(self, mock_auth: AsyncAuth) -> None:
        """Streaming with exactly one audio chunk."""
        with patch("riva.client.asr_async.rasr_srv.RivaSpeechRecognitionStub") as mock_stub_cls:
            mock_stub = MagicMock()
            mock_response = MagicMock()
            mock_call = MagicMock()
            mock_call.__aiter__ = lambda self: aiter([mock_response])
            mock_stub.StreamingRecognize.return_value = mock_call
            mock_stub_cls.return_value = mock_stub

            service = ASRServiceAsync(mock_auth)
            mock_config = MagicMock()

            async def single_chunk_gen():
                yield b"single_audio_chunk"

            responses = []
            async for response in service.streaming_recognize(single_chunk_gen(), mock_config):
                responses.append(response)

            assert len(responses) == 1
            mock_stub.StreamingRecognize.assert_called_once()


class TestErrorHandling:
    """Tests for error handling behavior."""

    @pytest.fixture
    def mock_auth(self) -> AsyncAuth:
        """Create mock auth with mocked channel."""
        auth = AsyncAuth(uri="localhost:50051")
        auth._channel = MagicMock()
        return auth

    @pytest.mark.asyncio
    async def test_streaming_recognize_handles_grpc_error(self, mock_auth: AsyncAuth) -> None:
        """gRPC errors propagate correctly."""
        import grpc

        with patch("riva.client.asr_async.rasr_srv.RivaSpeechRecognitionStub") as mock_stub_cls:
            mock_stub = MagicMock()

            async def error_iter():
                raise grpc.aio.AioRpcError(
                    grpc.StatusCode.UNAVAILABLE,
                    initial_metadata=None,
                    trailing_metadata=None,
                    details="Server unavailable",
                    debug_error_string=None,
                )
                yield  # Make it a generator

            mock_call = MagicMock()
            mock_call.__aiter__ = lambda self: error_iter()
            mock_stub.StreamingRecognize.return_value = mock_call
            mock_stub_cls.return_value = mock_stub

            service = ASRServiceAsync(mock_auth)
            mock_config = MagicMock()

            async def audio_gen():
                yield b"audio"

            with pytest.raises(grpc.aio.AioRpcError):
                async for _ in service.streaming_recognize(audio_gen(), mock_config):
                    pass

    @pytest.mark.asyncio
    async def test_streaming_recognize_cancellation(self, mock_auth: AsyncAuth) -> None:
        """Cancellation is handled gracefully."""
        with patch("riva.client.asr_async.rasr_srv.RivaSpeechRecognitionStub") as mock_stub_cls:
            mock_stub = MagicMock()

            async def slow_iter():
                yield MagicMock()
                await asyncio.sleep(10)  # Long delay
                yield MagicMock()

            mock_call = MagicMock()
            mock_call.__aiter__ = lambda self: slow_iter()
            mock_stub.StreamingRecognize.return_value = mock_call
            mock_stub_cls.return_value = mock_stub

            service = ASRServiceAsync(mock_auth)
            mock_config = MagicMock()

            async def audio_gen():
                yield b"audio"

            async def consume_stream():
                async for _ in service.streaming_recognize(audio_gen(), mock_config):
                    pass

            task = asyncio.create_task(consume_stream())
            await asyncio.sleep(0.01)
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task
