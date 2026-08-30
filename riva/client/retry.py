# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

"""Shared retry utilities for resilient streaming ASR and TTS clients.

This module provides constants, helpers, and decorators for handling transient
gRPC failures with exponential backoff. It is designed to be used by both
:mod:`riva.client.asr` and :mod:`riva.client.tts`.
"""

import functools
import logging
import random
import time
from typing import Any, Callable, Optional, Tuple, TypeVar

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

F = TypeVar("F", bound=Callable[..., Any])


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


def retry_streaming(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    on_retry: Optional[Callable[[grpc.RpcError, int, float], None]] = None,
) -> Callable[[F], F]:
    """Decorator that retries a streaming gRPC call on transient failures.

    The decorated function must be a generator (i.e. use ``yield``). When a
    :class:`grpc.RpcError` with a retryable code is raised, the generator is
    closed and the function is re-invoked up to *max_retries* times.

    Args:
        max_retries: Maximum number of retry attempts after the initial failure.
        base_delay: Initial backoff delay in seconds.
        max_delay: Maximum backoff delay in seconds.
        on_retry: Optional callback ``fn(exc, attempt, delay)`` invoked before
            each retry sleep.

    Returns:
        A decorator that wraps generator functions with retry logic.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[grpc.RpcError] = None
            for attempt in range(max_retries + 1):
                try:
                    yield from func(*args, **kwargs)
                    return
                except grpc.RpcError as exc:
                    last_exception = exc
                    if not is_retryable_grpc_error(exc):
                        LOGGER.warning(
                            "Non-retryable gRPC error %s: %s",
                            exc.code() if hasattr(exc, "code") else "UNKNOWN",
                            exc.details() if hasattr(exc, "details") else str(exc),
                        )
                        raise
                    if attempt >= max_retries:
                        LOGGER.error(
                            "Max retries (%d) exceeded for %s. Last error: %s",
                            max_retries,
                            func.__name__,
                            exc.details() if hasattr(exc, "details") else str(exc),
                        )
                        raise
                    delay = exponential_backoff(attempt, base_delay, max_delay)
                    LOGGER.info(
                        "Retryable gRPC error %s on attempt %d/%d for %s. "
                        "Sleeping %.2f s before retry.",
                        exc.code(),
                        attempt + 1,
                        max_retries + 1,
                        func.__name__,
                        delay,
                    )
                    if on_retry is not None:
                        on_retry(exc, attempt + 1, delay)
                    time.sleep(delay)
            # Should never reach here, but satisfy type checker.
            if last_exception is not None:
                raise last_exception
        return wrapper  # type: ignore[return-value]
    return decorator
