# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

"""Integration test fixtures."""

import os
import wave
from pathlib import Path
from typing import AsyncIterator

import pytest

# Audio sample directory
AUDIO_DIR = Path(__file__).parent.parent.parent.parent / "data" / "examples"


@pytest.fixture
def riva_uri() -> str:
    """Get Riva server URI from environment."""
    uri = os.getenv("RIVA_URI")
    if not uri:
        pytest.skip("RIVA_URI environment variable not set")
    return uri


@pytest.fixture
def en_us_sample() -> Path:
    """Path to en-US sample audio file."""
    path = AUDIO_DIR / "en-US_sample.wav"
    if not path.exists():
        pytest.skip(f"Audio sample not found: {path}")
    return path


@pytest.fixture
def de_de_sample() -> Path:
    """Path to de-DE sample audio file."""
    path = AUDIO_DIR / "de-DE_sample.wav"
    if not path.exists():
        pytest.skip(f"Audio sample not found: {path}")
    return path


def get_wav_params(wav_path: Path) -> dict:
    """Get WAV file parameters."""
    with wave.open(str(wav_path), "rb") as wf:
        return {
            "sample_rate": wf.getframerate(),
            "sample_width": wf.getsampwidth(),
            "channels": wf.getnchannels(),
            "n_frames": wf.getnframes(),
        }


async def audio_chunk_generator(
    wav_path: Path, chunk_frames: int = 1600
) -> AsyncIterator[bytes]:
    """Yield audio chunks from WAV file.

    Args:
        wav_path: Path to WAV file
        chunk_frames: Number of frames per chunk (default 1600 = 100ms at 16kHz)

    Yields:
        Audio data chunks
    """
    with wave.open(str(wav_path), "rb") as wf:
        while True:
            data = wf.readframes(chunk_frames)
            if not data:
                break
            yield data


def read_wav_audio(wav_path: Path) -> bytes:
    """Read entire audio content from WAV file."""
    with wave.open(str(wav_path), "rb") as wf:
        return wf.readframes(wf.getnframes())
