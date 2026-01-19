# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

from typing import List, Tuple
from unittest.mock import AsyncMock, Mock, MagicMock


def set_auth_mock() -> Tuple[Mock, str]:
    """Create mock Auth for synchronous testing."""
    auth = Mock()
    return_value_of_get_auth_metadata = 'return_value_of_get_auth_metadata'
    auth.get_auth_metadata = Mock(return_value=return_value_of_get_auth_metadata)
    return auth, return_value_of_get_auth_metadata


def set_async_auth_mock() -> Tuple[AsyncMock, List[Tuple[str, str]]]:
    """Create mock AsyncAuth for async testing.

    Returns:
        Tuple of (auth mock, metadata list)
    """
    auth = AsyncMock()
    metadata = [("x-api-key", "test")]
    auth.get_auth_metadata.return_value = metadata
    auth.get_channel = AsyncMock(return_value=MagicMock())
    auth._channel = MagicMock()
    return auth, metadata


def create_mock_streaming_response(transcript: str, is_final: bool) -> MagicMock:
    """Create a mock StreamingRecognizeResponse.

    Args:
        transcript: The transcript text
        is_final: Whether this is a final result

    Returns:
        MagicMock configured like StreamingRecognizeResponse
    """
    response = MagicMock()

    # Create result structure
    result = MagicMock()
    result.is_final = is_final

    # Create alternative with transcript
    alternative = MagicMock()
    alternative.transcript = transcript
    result.alternatives = [alternative]

    response.results = [result]
    return response


def create_mock_recognize_response(transcript: str) -> MagicMock:
    """Create a mock RecognizeResponse for batch recognition.

    Args:
        transcript: The transcript text

    Returns:
        MagicMock configured like RecognizeResponse
    """
    response = MagicMock()

    result = MagicMock()
    alternative = MagicMock()
    alternative.transcript = transcript
    result.alternatives = [alternative]

    response.results = [result]
    return response
