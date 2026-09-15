# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
from io import StringIO
from math import ceil
from typing import Any, Generator, List, Union
from unittest.mock import patch, Mock

import riva.client.proto.riva_asr_pb2 as rasr
from riva.client import ASRService
from riva.client.argparse_utils import add_asr_config_argparse_parameters
from riva.client.asr import add_speaker_diarization_to_config, print_streaming, streaming_request_generator

from .helpers import set_auth_mock


SAMPLE_RATE_HZ = 44100
SAMPLE_WIDTH = 2
STREAMING_CHUNK_SIZE = 1000

AUDIO_BYTES_1_SECOND = b'a' * SAMPLE_WIDTH * SAMPLE_RATE_HZ
AUDIO_CHUNKS = [
    AUDIO_BYTES_1_SECOND[i * STREAMING_CHUNK_SIZE : (i + 1) * STREAMING_CHUNK_SIZE]
    for i in range(ceil(len(AUDIO_BYTES_1_SECOND) / STREAMING_CHUNK_SIZE))
]


RECOGNITION_CONFIG = rasr.RecognitionConfig()
RECOGNIZE_REQUEST = rasr.RecognizeRequest(config=RECOGNITION_CONFIG, audio=AUDIO_BYTES_1_SECOND)
RECOGNIZE_RESPONSE = rasr.RecognizeResponse()
RECOGNIZE_MOCK = Mock(return_value=RECOGNIZE_RESPONSE)
RECOGNIZE_MOCK.future = Mock(return_value=RECOGNIZE_RESPONSE)


STREAMING_RECOGNITION_CONFIG = rasr.StreamingRecognitionConfig()


def response_generator(chunk_size: int = STREAMING_CHUNK_SIZE) -> Generator[rasr.StreamingRecognizeResponse, None, None]:
    for i in range(0, len(AUDIO_BYTES_1_SECOND), chunk_size):
        yield rasr.StreamingRecognizeResponse()


STREAMING_RECOGNIZE_MOCK = Mock(return_value=response_generator(STREAMING_CHUNK_SIZE))


def test_diarization_max_speakers_defaults_to_server_selection() -> None:
    parser = add_asr_config_argparse_parameters(argparse.ArgumentParser())

    args = parser.parse_args([])

    assert args.diarization_max_speakers == 0


def test_speaker_diarization_uses_server_default_unless_max_is_positive() -> None:
    config = rasr.RecognitionConfig()

    add_speaker_diarization_to_config(config, True, 0)

    assert config.diarization_config.enable_speaker_diarization is True
    assert config.diarization_config.max_speaker_count == 0
    assert [field.name for field, _ in config.diarization_config.ListFields()] == [
        "enable_speaker_diarization"
    ]

    add_speaker_diarization_to_config(config, True, 4)

    assert config.diarization_config.max_speaker_count == 4


def riva_asr_stub_init_patch(self, channel):
    self.Recognize = RECOGNIZE_MOCK
    self.StreamingRecognize = STREAMING_RECOGNIZE_MOCK


def is_iterable(obj: Any) -> bool:
    try:
        iter(obj)
    except TypeError:
        return False
    return True


@patch("riva.client.proto.riva_asr_pb2_grpc.RivaSpeechRecognitionStub.__init__", riva_asr_stub_init_patch)
class TestSpeechSynthesisService:
    def test_offline_recognize(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        service = ASRService(auth)
        RECOGNIZE_MOCK.reset_mock()
        resp = service.offline_recognize(AUDIO_BYTES_1_SECOND, config=RECOGNITION_CONFIG)
        assert isinstance(resp, rasr.RecognizeResponse)
        RECOGNIZE_MOCK.assert_called_with(RECOGNIZE_REQUEST, metadata=return_value_of_get_auth_metadata)

    def test_offline_recognize_future(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        service = ASRService(auth)
        RECOGNIZE_MOCK.reset_mock()
        RECOGNIZE_MOCK.future.reset_mock()
        resp = service.offline_recognize(AUDIO_BYTES_1_SECOND, config=RECOGNITION_CONFIG, future=True)
        assert isinstance(resp, rasr.RecognizeResponse)
        RECOGNIZE_MOCK.future.assert_called_with(RECOGNIZE_REQUEST, metadata=return_value_of_get_auth_metadata)

    def test_streaming_response_generator(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        service = ASRService(auth)
        STREAMING_RECOGNIZE_MOCK.reset_mock()
        responses = service.streaming_response_generator(AUDIO_CHUNKS, STREAMING_RECOGNITION_CONFIG)
        count = 0
        assert is_iterable(responses)
        for resp in responses:
            assert isinstance(resp, rasr.StreamingRecognizeResponse)
            count += 1
        assert len(AUDIO_CHUNKS) == count
        count = 0
        for req in STREAMING_RECOGNIZE_MOCK.call_args.args[0]:
            assert isinstance(req, rasr.StreamingRecognizeRequest)
            count += 1
        assert len(AUDIO_CHUNKS) + 1 == count
        assert len(STREAMING_RECOGNIZE_MOCK.call_args.kwargs) == 1
        assert 'metadata' in STREAMING_RECOGNIZE_MOCK.call_args.kwargs
        assert STREAMING_RECOGNIZE_MOCK.call_args.kwargs['metadata'] == return_value_of_get_auth_metadata


def test_print_streaming_includes_word_confidence_with_timestamps() -> None:
    response = rasr.StreamingRecognizeResponse(
        results=[
            rasr.StreamingRecognitionResult(
                is_final=True,
                alternatives=[
                    rasr.SpeechRecognitionAlternative(
                        transcript="hello",
                        words=[rasr.WordInfo(word="hello", start_time=10, end_time=20, confidence=0.75)],
                    )
                ],
            )
        ]
    )
    output = StringIO()

    print_streaming(
        responses=[response],
        output_file=output,
        additional_info="time",
        word_time_offsets=True,
    )

    rendered = output.getvalue()
    assert "Confidence" in rendered
    assert "hello" in rendered
    assert "0.7500" in rendered
