# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

from typing import List, Union
from unittest.mock import patch, Mock

import riva.client.proto.riva_nlp_pb2 as rnlp
from riva.client import NLPService

from .helpers import set_auth_mock


MODEL_NAME = 'model_name'
LANGUAGE_CODE = 'ru-RU'
INPUT_STRINGS = ['What is the name of your dog?', 'Your cat is great!']
# TEXT_CLASS_NAMES = ['usual', 'question', 'exclamation']
# TEXT_CLASS_SCORES = [0.7, 0.2, 0.1]


def fill_multiple_strings_request(
    req: Union[rnlp.TextClassRequest, rnlp.TokenClassRequest, rnlp.TextTransformRequest],
    input_strings: List[str],
    model_name: str,
    language_code: str,
) -> Union[rnlp.TextClassRequest, rnlp.TokenClassRequest, rnlp.TextTransformRequest]:
    for text in input_strings:
        req.text.append(text)
    req.model.model_name = model_name
    req.model.language_code = language_code
    return req


TEXT_CLASS_RESPONSE = rnlp.TextClassResponse()
TEXT_CLASS_REQUEST = fill_multiple_strings_request(rnlp.TextClassRequest(), INPUT_STRINGS, MODEL_NAME, LANGUAGE_CODE)
CLASSIFY_TEXT_MOCK = Mock(return_value=TEXT_CLASS_RESPONSE)
CLASSIFY_TEXT_MOCK.future = Mock(return_value=TEXT_CLASS_RESPONSE)

TOKENS_CLASS_RESPONSE = rnlp.TokenClassResponse()
TOKEN_CLASS_REQUEST = fill_multiple_strings_request(rnlp.TokenClassRequest(), INPUT_STRINGS, MODEL_NAME, LANGUAGE_CODE)
CLASSIFY_TOKENS_MOCK = Mock(return_value=TOKENS_CLASS_RESPONSE)
CLASSIFY_TOKENS_MOCK.future = Mock(return_value=TOKENS_CLASS_RESPONSE)

TEXT_TRANSFORM_RESPONSE = rnlp.TextTransformResponse()
TEXT_TRANSFORM_REQUEST = fill_multiple_strings_request(
    rnlp.TextTransformRequest(), INPUT_STRINGS, MODEL_NAME, LANGUAGE_CODE
)
TRANSFORM_TEXT_MOCK = Mock(return_value=TEXT_TRANSFORM_RESPONSE)
TRANSFORM_TEXT_MOCK.future = Mock(return_value=TEXT_TRANSFORM_RESPONSE)
PUNCTUATE_TEXT_MOCK = Mock(return_value=TEXT_TRANSFORM_RESPONSE)
PUNCTUATE_TEXT_MOCK.future = Mock(return_value=TEXT_TRANSFORM_RESPONSE)

ANALYZE_INTENT_RESPONSE = rnlp.AnalyzeIntentResponse()
ANALYZE_INTENT_REQUEST = rnlp.AnalyzeIntentRequest(query=INPUT_STRINGS[0], options=rnlp.AnalyzeIntentOptions())
ANALYZE_INTENT_MOCK = Mock(return_value=ANALYZE_INTENT_RESPONSE)
ANALYZE_INTENT_MOCK.future = Mock(return_value=ANALYZE_INTENT_RESPONSE)

ANALYZE_ENTITIES_REQUEST = rnlp.AnalyzeEntitiesRequest(query=INPUT_STRINGS[0], options=rnlp.AnalyzeEntitiesOptions())
ANALYZE_ENTITIES_REQUEST.options.lang = LANGUAGE_CODE
ANALYZE_ENTITIES_MOCK = Mock(return_value=TOKENS_CLASS_RESPONSE)
ANALYZE_ENTITIES_MOCK.future = Mock(return_value=TOKENS_CLASS_RESPONSE)

TOP_N = 2
NATURAL_QUERY_RESPONSE = rnlp.NaturalQueryResponse()
NATURAL_QUERY_REQUEST = rnlp.NaturalQueryRequest(query=INPUT_STRINGS[0], context=INPUT_STRINGS[1], top_n=TOP_N)
NATURAL_QUERY_MOCK = Mock(return_value=NATURAL_QUERY_RESPONSE)
NATURAL_QUERY_MOCK.future = Mock(return_value=NATURAL_QUERY_RESPONSE)


def riva_nlp_stub_init_patch(self, channel):
    self.ClassifyText = CLASSIFY_TEXT_MOCK
    self.ClassifyTokens = CLASSIFY_TOKENS_MOCK
    self.TransformText = TRANSFORM_TEXT_MOCK
    self.AnalyzeEntities = ANALYZE_ENTITIES_MOCK
    self.AnalyzeIntent = ANALYZE_INTENT_MOCK
    self.PunctuateText = PUNCTUATE_TEXT_MOCK
    self.NaturalQuery = NATURAL_QUERY_MOCK


@patch("riva.client.proto.riva_nlp_pb2_grpc.RivaLanguageUnderstandingStub.__init__", riva_nlp_stub_init_patch)
class TestSpeechSynthesisService:
    def test_classify_text(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        service = NLPService(auth)
        CLASSIFY_TEXT_MOCK.reset_mock()
        resp = service.classify_text(INPUT_STRINGS, model_name=MODEL_NAME, language_code=LANGUAGE_CODE)
        assert isinstance(resp, rnlp.TextClassResponse)
        CLASSIFY_TEXT_MOCK.assert_called_with(
            TEXT_CLASS_REQUEST, metadata=return_value_of_get_auth_metadata,
        )

    def test_classify_text_future(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        service = NLPService(auth)
        CLASSIFY_TEXT_MOCK.reset_mock()
        CLASSIFY_TEXT_MOCK.future.reset_mock()
        resp = service.classify_text(INPUT_STRINGS, model_name=MODEL_NAME, language_code=LANGUAGE_CODE, future=True)
        assert isinstance(resp, rnlp.TextClassResponse)
        CLASSIFY_TEXT_MOCK.future.assert_called_with(
            TEXT_CLASS_REQUEST, metadata=return_value_of_get_auth_metadata,
        )

    def test_classify_tokens(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        service = NLPService(auth)
        CLASSIFY_TOKENS_MOCK.reset_mock()
        resp = service.classify_tokens(INPUT_STRINGS, model_name=MODEL_NAME, language_code=LANGUAGE_CODE)
        assert isinstance(resp, rnlp.TokenClassResponse)
        CLASSIFY_TOKENS_MOCK.assert_called_with(
            TOKEN_CLASS_REQUEST, metadata=return_value_of_get_auth_metadata,
        )

    def test_classify_tokens_future(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        service = NLPService(auth)
        CLASSIFY_TOKENS_MOCK.reset_mock()
        CLASSIFY_TOKENS_MOCK.future.reset_mock()
        resp = service.classify_tokens(INPUT_STRINGS, model_name=MODEL_NAME, language_code=LANGUAGE_CODE, future=True)
        assert isinstance(resp, rnlp.TokenClassResponse)
        CLASSIFY_TOKENS_MOCK.future.assert_called_with(
            TOKEN_CLASS_REQUEST, metadata=return_value_of_get_auth_metadata,
        )

    def test_transform_text(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        service = NLPService(auth)
        TRANSFORM_TEXT_MOCK.reset_mock()
        resp = service.transform_text(INPUT_STRINGS, model_name=MODEL_NAME, language_code=LANGUAGE_CODE)
        assert isinstance(resp, rnlp.TextTransformResponse)
        TRANSFORM_TEXT_MOCK.assert_called_with(
            TEXT_TRANSFORM_REQUEST, metadata=return_value_of_get_auth_metadata,
        )

    def test_transform_text_future(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        service = NLPService(auth)
        TRANSFORM_TEXT_MOCK.reset_mock()
        TRANSFORM_TEXT_MOCK.future.reset_mock()
        resp = service.transform_text(INPUT_STRINGS, model_name=MODEL_NAME, language_code=LANGUAGE_CODE, future=True)
        assert isinstance(resp, rnlp.TextTransformResponse)
        TRANSFORM_TEXT_MOCK.future.assert_called_with(
            TEXT_TRANSFORM_REQUEST, metadata=return_value_of_get_auth_metadata,
        )

    def test_punctuate_text(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        service = NLPService(auth)
        PUNCTUATE_TEXT_MOCK.reset_mock()
        resp = service.punctuate_text(INPUT_STRINGS, model_name=MODEL_NAME, language_code=LANGUAGE_CODE)
        assert isinstance(resp, rnlp.TextTransformResponse)
        PUNCTUATE_TEXT_MOCK.assert_called_with(
            TEXT_TRANSFORM_REQUEST, metadata=return_value_of_get_auth_metadata,
        )

    def test_punctuate_text_future(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        service = NLPService(auth)
        PUNCTUATE_TEXT_MOCK.reset_mock()
        PUNCTUATE_TEXT_MOCK.future.reset_mock()
        resp = service.punctuate_text(INPUT_STRINGS, model_name=MODEL_NAME, language_code=LANGUAGE_CODE, future=True)
        assert isinstance(resp, rnlp.TextTransformResponse)
        PUNCTUATE_TEXT_MOCK.future.assert_called_with(
            TEXT_TRANSFORM_REQUEST, metadata=return_value_of_get_auth_metadata,
        )

    def test_analyze_intent(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        service = NLPService(auth)
        ANALYZE_INTENT_MOCK.reset_mock()
        resp = service.analyze_intent(INPUT_STRINGS[0], rnlp.AnalyzeIntentOptions())
        assert isinstance(resp, rnlp.AnalyzeIntentResponse)
        ANALYZE_INTENT_MOCK.assert_called_with(ANALYZE_INTENT_REQUEST, metadata=return_value_of_get_auth_metadata)

    def test_analyze_intent_future(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        service = NLPService(auth)
        ANALYZE_INTENT_MOCK.reset_mock()
        ANALYZE_INTENT_MOCK.future.reset_mock()
        resp = service.analyze_intent(INPUT_STRINGS[0], rnlp.AnalyzeIntentOptions(), future=True)
        assert isinstance(resp, rnlp.AnalyzeIntentResponse)
        ANALYZE_INTENT_MOCK.future.assert_called_with(
            ANALYZE_INTENT_REQUEST, metadata=return_value_of_get_auth_metadata
        )

    def test_analyze_entities(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        service = NLPService(auth)
        ANALYZE_ENTITIES_MOCK.reset_mock()
        resp = service.analyze_entities(INPUT_STRINGS[0], LANGUAGE_CODE)
        assert isinstance(resp, rnlp.TokenClassResponse)
        ANALYZE_ENTITIES_MOCK.assert_called_with(ANALYZE_ENTITIES_REQUEST, metadata=return_value_of_get_auth_metadata)

    def test_analyze_entities_future(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        service = NLPService(auth)
        ANALYZE_ENTITIES_MOCK.reset_mock()
        ANALYZE_ENTITIES_MOCK.future.reset_mock()
        resp = service.analyze_entities(INPUT_STRINGS[0], LANGUAGE_CODE, future=True)
        assert isinstance(resp, rnlp.TokenClassResponse)
        ANALYZE_ENTITIES_MOCK.future.assert_called_with(
            ANALYZE_ENTITIES_REQUEST, metadata=return_value_of_get_auth_metadata
        )

    def test_natural_query(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        service = NLPService(auth)
        NATURAL_QUERY_MOCK.reset_mock()
        resp = service.natural_query(INPUT_STRINGS[0], INPUT_STRINGS[1], TOP_N)
        assert isinstance(resp, rnlp.NaturalQueryResponse)
        NATURAL_QUERY_MOCK.assert_called_with(NATURAL_QUERY_REQUEST, metadata=return_value_of_get_auth_metadata)

    def test_natural_query_future(self) -> None:
        auth, return_value_of_get_auth_metadata = set_auth_mock()
        service = NLPService(auth)
        NATURAL_QUERY_MOCK.reset_mock()
        NATURAL_QUERY_MOCK.future.reset_mock()
        resp = service.natural_query(INPUT_STRINGS[0], INPUT_STRINGS[1], TOP_N, future=True)
        assert isinstance(resp, rnlp.NaturalQueryResponse)
        NATURAL_QUERY_MOCK.future.assert_called_with(NATURAL_QUERY_REQUEST, metadata=return_value_of_get_auth_metadata)
