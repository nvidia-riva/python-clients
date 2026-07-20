# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
import asyncio
import base64
import json
from unittest.mock import AsyncMock

from riva.client.realtime import RealtimeClientASR


def make_client():
    client = RealtimeClientASR(argparse.Namespace())
    client.websocket = AsyncMock()
    return client


def make_session_update_client(**overrides):
    args = {
        "mic": False,
        "language_code": None,
        "model_name": None,
        "prompt": None,
        "sample_rate_hz": None,
        "num_channels": None,
        "max_alternatives": None,
        "automatic_punctuation": None,
        "word_time_offsets": None,
        "profanity_filter": None,
        "no_verbatim_transcripts": False,
        "speaker_diarization": False,
        "boosted_lm_words": None,
        "custom_configuration": "",
        "start_history": -1,
        "start_threshold": -1.0,
        "stop_history": -1,
        "stop_threshold": -1.0,
        "stop_history_eou": -1,
        "stop_threshold_eou": -1.0,
    }
    args.update(overrides)
    client = RealtimeClientASR(argparse.Namespace(**args))
    client.session_config = {
        "input_audio_format": "none",
        "recognition_config": {
            "enable_verbatim_transcripts": True,
            "custom_configuration": "",
        },
    }
    client._send_message = AsyncMock()
    client._handle_session_update_response = AsyncMock(return_value=True)
    return client


def sent_messages(client):
    return [json.loads(call.args[0]) for call in client.websocket.send.await_args_list]


def test_send_audio_chunks_adds_force_eou_to_selected_chunk():
    client = make_client()

    asyncio.run(client.send_audio_chunks([b"first", b"second"], [False, True]))

    assert sent_messages(client) == [
        {
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(b"first").decode("utf-8"),
        },
        {"type": "input_audio_buffer.commit"},
        {
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(b"second").decode("utf-8"),
            "runtime_config": {"force_eou": "true"},
        },
        {"type": "input_audio_buffer.commit"},
        {"type": "input_audio_buffer.done"},
    ]


def test_request_force_eou_applies_once_to_next_chunk():
    client = make_client()
    client.request_force_eou()

    asyncio.run(client.send_audio_chunks([b"first", b"second"]))

    messages = sent_messages(client)
    assert messages[0]["runtime_config"] == {"force_eou": "true"}
    assert "runtime_config" not in messages[2]


def test_send_audio_chunks_supports_async_audio_iterators():
    client = make_client()

    async def audio_chunks():
        yield b"first"
        yield b"second"

    asyncio.run(client.send_audio_chunks(audio_chunks(), [True, False]))

    messages = sent_messages(client)
    assert messages[0]["runtime_config"] == {"force_eou": "true"}
    assert "runtime_config" not in messages[2]


def test_update_session_places_custom_configuration_under_recognition_config():
    client = make_session_update_client(custom_configuration="enable_preprocessing:true")

    asyncio.run(client._update_session())

    request = client._send_message.await_args.args[0]
    assert "custom_configuration" not in request["session"]
    assert request["session"]["recognition_config"]["custom_configuration"] == "enable_preprocessing:true"


def test_update_session_maps_no_verbatim_transcripts_to_itn():
    client = make_session_update_client(no_verbatim_transcripts=True)

    asyncio.run(client._update_session())

    request = client._send_message.await_args.args[0]
    assert request["session"]["recognition_config"]["enable_verbatim_transcripts"] is False
