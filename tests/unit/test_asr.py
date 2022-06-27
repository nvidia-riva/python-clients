# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

from math import ceil
from typing import Any, Generator, List, Union
from unittest.mock import patch, Mock

import riva.client.proto.riva_asr_pb2 as rasr
from riva.client import ASRService
from riva.client.asr import streaming_request_generator

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
