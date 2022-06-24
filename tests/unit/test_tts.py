# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

from math import ceil
from typing import Any, Generator
from unittest.mock import patch, Mock

import riva.client.proto.riva_tts_pb2 as rtts
from riva.client import AudioEncoding
from riva.client.tts import SpeechSynthesisService

from .helpers import set_auth_mock


TEXT = 'foo'
VOICE_NAME = "English-US-Female-1"
LANGUAGE_CODE = 'en-US'
ENCODING = AudioEncoding.LINEAR_PCM
SAMPLE_RATE_HZ = 44100
SAMPLE_WIDTH = 2
STREAMING_CHUNK_SIZE = 1000

AUDIO_BYTES_1_SECOND = b'a' * SAMPLE_WIDTH * SAMPLE_RATE_HZ


def response_generator(chunk_size: int = STREAMING_CHUNK_SIZE) -> Generator[rtts.SynthesizeSpeechResponse, None, None]:
    for i in range(0, len(AUDIO_BYTES_1_SECOND), chunk_size):
        yield rtts.SynthesizeSpeechResponse(audio=AUDIO_BYTES_1_SECOND[i * chunk_size : (i + 1) * chunk_size])


SYNTHESIZE_MOCK = Mock(
    return_value=rtts.SynthesizeSpeechResponse(audio=AUDIO_BYTES_1_SECOND)
)
SYNTHESIZE_MOCK.future = Mock(
    return_value=rtts.SynthesizeSpeechResponse(audio=AUDIO_BYTES_1_SECOND)
)
SYNTHESIZE_ONLINE_MOCK = Mock(return_value=response_generator())


def riva_tts_stub_init_patch(self, channel):
    self.Synthesize = SYNTHESIZE_MOCK
    self.SynthesizeOnline = SYNTHESIZE_ONLINE_MOCK


def is_iterable(obj: Any) -> bool:
    try:
        iter(obj)
    except TypeError:
        return False
    return True


@patch("riva.client.proto.riva_tts_pb2_grpc.RivaSpeechSynthesisStub.__init__", riva_tts_stub_init_patch)
class TestSpeechSynthesisService:
    def test_synthesize(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        SYNTHESIZE_MOCK.reset_mock()
        service = SpeechSynthesisService(auth)
        resp = service.synthesize(TEXT, VOICE_NAME, LANGUAGE_CODE, ENCODING, SAMPLE_RATE_HZ)
        assert isinstance(resp, rtts.SynthesizeSpeechResponse)
        SYNTHESIZE_MOCK.assert_called_with(
            rtts.SynthesizeSpeechRequest(
                text=TEXT,
                voice_name=VOICE_NAME,
                language_code=LANGUAGE_CODE,
                encoding=ENCODING,
                sample_rate_hz=SAMPLE_RATE_HZ,
            ),
            metadata=return_value_of_get_auth_metadata,
        )

    def test_synthesize_future(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        SYNTHESIZE_MOCK.reset_mock()
        SYNTHESIZE_MOCK.future.reset_mock()
        service = SpeechSynthesisService(auth)
        resp = service.synthesize(TEXT, VOICE_NAME, LANGUAGE_CODE, ENCODING, SAMPLE_RATE_HZ, future=True)
        assert isinstance(resp, rtts.SynthesizeSpeechResponse)
        SYNTHESIZE_MOCK.future.assert_called_with(
            rtts.SynthesizeSpeechRequest(
                text=TEXT,
                voice_name=VOICE_NAME,
                language_code=LANGUAGE_CODE,
                encoding=ENCODING,
                sample_rate_hz=SAMPLE_RATE_HZ,
            ),
            metadata=return_value_of_get_auth_metadata,
        )

    def test_synthesize_online(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        SYNTHESIZE_ONLINE_MOCK.reset_mock()
        service = SpeechSynthesisService(auth)
        responses = service.synthesize_online(TEXT, VOICE_NAME, LANGUAGE_CODE, ENCODING, SAMPLE_RATE_HZ)
        assert is_iterable(responses), "`SpeechSynthesisService.synthesize_online()` method has to return an iterable."
        SYNTHESIZE_ONLINE_MOCK.assert_called_with(
            rtts.SynthesizeSpeechRequest(
                text=TEXT,
                voice_name=VOICE_NAME,
                language_code=LANGUAGE_CODE,
                encoding=ENCODING,
                sample_rate_hz=SAMPLE_RATE_HZ,
            ),
            metadata=return_value_of_get_auth_metadata,
        )
        count = 0
        for resp in responses:
            assert isinstance(
                resp, rtts.SynthesizeSpeechResponse
            ), (
                "`SpeechSynthesisService.synthesize_online()` returned iterable has to contain instances of "
                "`SynthesizeSpeechResponse`"
            )
            count += 1
        assert count == ceil(len(AUDIO_BYTES_1_SECOND) / STREAMING_CHUNK_SIZE)


