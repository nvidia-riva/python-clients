# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import time
from unittest.mock import Mock

import grpc
import pytest

from riva.client.retry import (
    RETRYABLE_GRPC_CODES,
    exponential_backoff,
    is_retryable_grpc_error,
    retry_streaming,
)


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


class TestRetryStreamingDecorator:
    def test_success_no_retry(self):
        @retry_streaming(max_retries=2)
        def gen():
            yield 1
            yield 2

        assert list(gen()) == [1, 2]

    def test_retries_then_succeeds(self):
        call_count = 0

        @retry_streaming(max_retries=2, base_delay=0.01)
        def gen():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise FakeRpcError(grpc.StatusCode.UNAVAILABLE)
            yield "ok"

        assert list(gen()) == ["ok"]
        assert call_count == 2

    def test_exhausts_retries(self):
        @retry_streaming(max_retries=1, base_delay=0.01)
        def gen():
            raise FakeRpcError(grpc.StatusCode.UNAVAILABLE)
            yield  # make it a generator

        with pytest.raises(grpc.RpcError):
            list(gen())

    def test_non_retryable_raises_immediately(self):
        @retry_streaming(max_retries=3)
        def gen():
            raise FakeRpcError(grpc.StatusCode.INVALID_ARGUMENT)
            yield

        with pytest.raises(grpc.RpcError):
            list(gen())

    def test_on_retry_callback(self):
        callback_log = []

        def on_retry(exc, attempt, delay):
            callback_log.append((exc.code(), attempt, delay))

        @retry_streaming(max_retries=1, base_delay=0.01, on_retry=on_retry)
        def gen():
            raise FakeRpcError(grpc.StatusCode.UNAVAILABLE)
            yield

        with pytest.raises(grpc.RpcError):
            list(gen())

        assert len(callback_log) == 1
        assert callback_log[0][0] == grpc.StatusCode.UNAVAILABLE
        assert callback_log[0][1] == 1
