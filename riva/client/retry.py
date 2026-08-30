# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

"""Shared retry utilities for resilient streaming ASR and TTS clients.

This module provides constants and helpers for handling transient gRPC
failures with exponential backoff. It is designed to be used by both
:mod:`riva.client.asr` and :mod:`riva.client.tts`.
"""

import logging
import random
import grpc

LOGGER = logging.getLogger(__name__)

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
