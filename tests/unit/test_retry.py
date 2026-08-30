# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import grpc
import pytest

from riva.client.retry import (
    RETRYABLE_GRPC_CODES,
    exponential_backoff,
    is_retryable_grpc_error,
)
from riva.client.tts import ResilientStreamingTTS


class FakeRpcError(grpc.RpcError):
    def __init__(self, code):
        self._code = code

    def code(self):
        return self._code

    def details(self):
        return "fake error"


class TestIsRetryableGrpcError:
    def test_retryable_codes(self):
        for code in RETRYABLE_GRPC_CODES:
            exc = FakeRpcError(code)
            assert is_retryable_grpc_error(exc) is True

    def test_non_retryable_code(self):
        exc = FakeRpcError(grpc.StatusCode.INVALID_ARGUMENT)
        assert is_retryable_grpc_error(exc) is False

    def test_no_code_method(self):
        exc = Exception("plain exception")
        assert is_retryable_grpc_error(exc) is False


class TestExponentialBackoff:
    def test_no_jitter_growth(self):
        assert exponential_backoff(0, base_delay=1.0, jitter=False) == 1.0
        assert exponential_backoff(1, base_delay=1.0, jitter=False) == 2.0
        assert exponential_backoff(2, base_delay=1.0, jitter=False) == 4.0

    def test_max_delay_cap(self):
        assert exponential_backoff(10, base_delay=1.0, max_delay=8.0, jitter=False) == 8.0

    def test_jitter_reduces_delay(self):
        for _ in range(20):
            d = exponential_backoff(2, base_delay=1.0, jitter=True)
            assert 0.0 <= d < 4.0


class TestResilientStreamingTTS:
    def test_does_not_yield_partial_audio_from_a_failed_segment(self, monkeypatch):
        class Service:
            def __init__(self):
                self.calls = 0

            def synthesize_online(self, **_kwargs):
                self.calls += 1
                if self.calls == 1:
                    def failed_stream():
                        yield "partial-audio"
                        raise FakeRpcError(grpc.StatusCode.UNAVAILABLE)
                    return failed_stream()

                return iter(["complete-audio"])

        monkeypatch.setattr("riva.client.tts.time.sleep", lambda _delay: None)
        service = Service()
        client = ResilientStreamingTTS(service, max_retries=1, base_delay=0)

        assert list(client.synthesize_stream("hello")) == ["complete-audio"]
        assert service.calls == 2
