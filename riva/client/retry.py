# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

"""Shared retry utilities for resilient streaming ASR and TTS clients.

This module provides constants and helpers for handling transient gRPC
failures with exponential backoff. It is designed to be used by both
:mod:`riva.client.asr` and :mod:`riva.client.tts`.
"""

import random
from typing import Dict, Mapping, Tuple

import grpc

CLIENT_AUTO_RECOVER = "client_auto_recover"
CLIENT_MAX_RETRIES = "client_max_retries"
CLIENT_LOOKBACK_SECONDS = "client_lookback_seconds"
CLIENT_RECOVERY_KEYS = frozenset({
    CLIENT_AUTO_RECOVER,
    CLIENT_MAX_RETRIES,
    CLIENT_LOOKBACK_SECONDS,
})

# gRPC status codes that are generally considered transient and safe to retry.
RETRYABLE_GRPC_CODES = frozenset({
    grpc.StatusCode.UNAVAILABLE,
    grpc.StatusCode.DEADLINE_EXCEEDED,
    grpc.StatusCode.INTERNAL,
    grpc.StatusCode.RESOURCE_EXHAUSTED,
    grpc.StatusCode.ABORTED,
})

# gRPC status codes that should NEVER be retried (client-side errors).
NON_RETRYABLE_GRPC_CODES = frozenset({
    grpc.StatusCode.INVALID_ARGUMENT,
    grpc.StatusCode.PERMISSION_DENIED,
    grpc.StatusCode.UNAUTHENTICATED,
    grpc.StatusCode.NOT_FOUND,
    grpc.StatusCode.ALREADY_EXISTS,
    grpc.StatusCode.FAILED_PRECONDITION,
    grpc.StatusCode.OUT_OF_RANGE,
    grpc.StatusCode.UNIMPLEMENTED,
})

def is_retryable_grpc_error(exc: grpc.RpcError) -> bool:
    """Return ``True`` if *exc* is a transient gRPC error that is safe to retry.

    Args:
        exc: The exception raised by a gRPC call.

    Returns:
        ``True`` if the error code is in :data:`RETRYABLE_GRPC_CODES`.
    """
    code = exc.code() if hasattr(exc, "code") else None
    if code is None:
        return False
    return code in RETRYABLE_GRPC_CODES


def exponential_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
) -> float:
    """Compute a sleep duration for the *attempt*-th retry.

    Uses capped exponential backoff with optional full jitter to avoid
    thundering-herd behaviour when many clients reconnect simultaneously.

    Args:
        attempt: Zero-based retry attempt number.
        base_delay: Initial delay in seconds.
        max_delay: Upper bound for the delay in seconds.
        jitter: If ``True``, multiply the delay by a random factor in ``[0, 1)``.

    Returns:
        The number of seconds to sleep before the next attempt.
    """
    delay = min(base_delay * (2 ** attempt), max_delay)
    if jitter:
        delay = delay * random.random()
    return delay


def split_recovery_configuration(
    custom_configuration: Mapping[str, str],
) -> Tuple[Dict[str, str], bool, int, float]:
    """Separate client-only streaming recovery options from server options.

    The reserved ``client_*`` keys control retry behaviour in the Python
    client and are intentionally not forwarded to Riva. All other key/value
    pairs are returned unchanged for the server.
    """
    server_configuration = {
        key: value for key, value in custom_configuration.items() if key not in CLIENT_RECOVERY_KEYS
    }
    enabled = str(custom_configuration.get(CLIENT_AUTO_RECOVER, "false")).lower() == "true"
    max_retries = int(custom_configuration.get(CLIENT_MAX_RETRIES, "3"))
    lookback_seconds = float(custom_configuration.get(CLIENT_LOOKBACK_SECONDS, "2.0"))
    if max_retries < 0:
        raise ValueError(f"{CLIENT_MAX_RETRIES} must be non-negative")
    if lookback_seconds <= 0:
        raise ValueError(f"{CLIENT_LOOKBACK_SECONDS} must be greater than zero")
    return server_configuration, enabled, max_retries, lookback_seconds
