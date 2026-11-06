# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import grpc
import pytest

from riva.client.retry import (
    CLIENT_AUTO_RECOVER,
    CLIENT_LOOKBACK_SECONDS,
    CLIENT_MAX_RETRIES,
    RETRYABLE_GRPC_CODES,
    exponential_backoff,
    is_retryable_grpc_error,
    split_recovery_configuration,
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


class TestRecoveryConfiguration:
    def test_client_options_are_not_forwarded_to_riva(self):
        server_configuration, enabled, max_retries, lookback_seconds = split_recovery_configuration({
            "exaggeration_factor": "1.5",
            CLIENT_AUTO_RECOVER: "true",
            CLIENT_MAX_RETRIES: "4",
            CLIENT_LOOKBACK_SECONDS: "3.5",
        })

        assert server_configuration == {"exaggeration_factor": "1.5"}
        assert enabled is True
        assert max_retries == 4
        assert lookback_seconds == 3.5
