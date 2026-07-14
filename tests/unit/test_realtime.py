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
