# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, Union

from google.protobuf.message import Message
from grpc._channel import _MultiThreadedRendezvous

import riva.client.proto.riva_nlp_pb2 as rnlp
import riva.client.proto.riva_nlp_pb2_grpc as rnlp_srv
from riva.client import Auth


def extract_all_text_classes_and_confidences(
    response: rnlp.TextClassResponse
) -> Tuple[List[List[str]], List[List[float]]]:
    text_classes, confidences = [], []
    for batch_elem_result in response.results:
        text_classes.append([lbl.class_name for lbl in batch_elem_result.labels])
        confidences.append([lbl.score for lbl in batch_elem_result.labels])
    return text_classes, confidences


def extract_most_probable_text_class_and_confidence(response: rnlp.TextClassResponse) -> Tuple[List[str], List[float]]:
    intents, confidences = extract_all_text_classes_and_confidences(response)
    return [x[0] for x in intents], [x[0] for x in confidences]


def extract_all_token_classification_predictions(
    response: rnlp.TokenClassResponse
) -> Tuple[
    List[List[str]],
    List[List[List[str]]],
    List[List[List[float]]],
    List[List[List[int]]],
    List[List[List[int]]]
]:
    tokens, token_classes, confidences, starts, ends = [], [], [], [], []
    for batch_elem_result in response.results:
        elem_tokens, elem_token_classes, elem_confidences, elem_starts, elem_ends = [], [], [], [], []
        for token_result in batch_elem_result.results:
            elem_tokens.append(token_result.token)
            elem_token_classes.append([lbl.class_name for lbl in token_result.label])
            elem_confidences.append([lbl.score for lbl in token_result.label])
            elem_starts.append([span.start for span in token_result.span])
            elem_ends.append([span.end for span in token_result.span])
        tokens.append(elem_tokens)
        token_classes.append(elem_token_classes)
        confidences.append(elem_confidences)
        starts.append(elem_starts)
        ends.append(elem_ends)
    return tokens, token_classes, confidences, starts, ends


def extract_most_probable_token_classification_predictions(
    response: rnlp.TokenClassResponse
) -> Tuple[List[List[str]], List[List[str]], List[List[float]], List[List[int]], List[List[int]]]:
    tokens, token_classes, confidences, starts, ends = extract_all_token_classification_predictions(response)
    return (
        tokens,
        [[xx[0] for xx in x] for x in token_classes],
        [[xx[0] for xx in x] for x in confidences],
        [[xx[0] for xx in x] for x in starts],
        [[xx[0] for xx in x] for x in ends],
    )


def extract_all_transformed_texts(response: rnlp.TextTransformResponse) -> List[str]:
    return [t for t in response.text]


def extract_most_probable_transformed_text(response: rnlp.TextTransformResponse) -> str:
    return response.text[0]


def prepare_transform_text_request(
    input_strings: Union[List[str], str], model_name: str, language_code: str = 'en-US'
) -> rnlp.TextTransformRequest:
    if isinstance(input_strings, str):
        input_strings = [input_strings]
    request = rnlp.TextTransformRequest()
    if model_name is not None:
        request.model.model_name = model_name
    request.model.language_code = language_code
    for q in input_strings:
        request.text.append(q)
    return request


class NLPService:
    """
    Provides
        - text classification,
        - token classification,
        - text transformation,
        - intent recognition,
        - punctuation and capitalization restoring,
        - question answering
    services.
    """
    def __init__(self, auth: Auth) -> None:
        """
        Initializes an instance of the class.

        Args:
            auth (:obj:`Auth`): an instance of :class:`riva.client.auth.Auth` which is used for
                authentication metadata generation.
        """
        self.auth = auth
        self.stub = rnlp_srv.RivaLanguageUnderstandingStub(self.auth.channel)

    def classify_text(
        self, input_strings: Union[List[str], str], model_name: str, language_code: str = 'en-US', future: bool = False
    ) -> Union[rnlp.TextClassResponse, _MultiThreadedRendezvous]:
        """
        Classifies text provided in :param:`input_strings`. For example, this method can be used for
        intent classification.

        Args:
            input_strings (:obj:`Union[List[str], str]`): a text or a list of texts which will be classified.
            model_name (:obj:`str`): a name of a model. You can look up the model name in server logs or in server
                directory with models. A value for quickstart v2.0.0: ``"riva_intent_weather"``.
            language_code (:obj:`str`): a language of input text if :param:`model_name` is available for several
                languages.
            future (:obj:`bool`, defaults to :obj:`False`): whether to return an async result instead of usual
                response. You can get a response by calling ``result()`` method of the future object.
        Returns:
            :obj:`Union[riva.client.proto.riva_nlp_pb2.TextClassResponse, grpc._channel._MultiThreadedRendezvous]`: a
            response with :param:`input_strings` classification results. You may find :class:`TextClassResponse`
            fields description `here
            <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-nlp-proto>`_.
            If :param:`future` is :obj:`True`, then a future object is returned. You may retrieve a response from a
            future object by calling ``result()`` method.
        """
        if isinstance(input_strings, str):
            input_strings = [input_strings]
        request = rnlp.TextClassRequest()
        request.model.model_name = model_name
        request.model.language_code = language_code
        for q in input_strings:
            request.text.append(q)
        func = self.stub.ClassifyText.future if future else self.stub.ClassifyText
        return func(request, metadata=self.auth.get_auth_metadata())

    def classify_tokens(
        self, input_strings: Union[List[str], str], model_name: str, language_code: str = 'en-US', future: bool = False
    ) -> Union[rnlp.TokenClassResponse, _MultiThreadedRendezvous]:
        """
        Classifies tokens in texts in :param:`input_strings`. Can be used for slot classification or NER.

        Args:
            input_strings (:obj:`Union[List[str], str]`): a text or a list of texts.
            model_name (:obj:`Union[List[str], str]`): a name of a model. You can look up the model name in server logs
                or in server directory with models. Valid values for quickstart v2.0.0: ``"riva_intent_weather"``
                and ``"riva_ner"``.
            language_code: a language of input text if :param:`model_name` is available for several
                languages.
            future (:obj:`bool`, defaults to :obj:`False`): whether to return an async result instead of usual
                response. You can get a response by calling ``result()`` method of the future object.
        Returns:
            :obj:`Union[riva.client.proto.riva_nlp_pb2.TokenClassResponse, grpc._channel._MultiThreadedRendezvous]`: a
            response with results. You may find :class:`TokenClassResponse` fields description `here
            <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-nlp-proto>`_.
            If :param:`future` is :obj:`True`, then a future object is returned. You may retrieve a response from a
            future object by calling ``result()`` method.
        """
        if isinstance(input_strings, str):
            input_strings = [input_strings]
        request = rnlp.TokenClassRequest()
        request.model.model_name = model_name
        request.model.language_code = language_code
        for q in input_strings:
            request.text.append(q)
        func = self.stub.ClassifyTokens.future if future else self.stub.ClassifyTokens
        return func(request, metadata=self.auth.get_auth_metadata())

    def transform_text(
        self, input_strings: Union[List[str], str], model_name: str, language_code: str = 'en-US', future: bool = False
    ) -> Union[rnlp.TextTransformResponse, _MultiThreadedRendezvous]:
        """
        The behavior of the function is defined entirely by the underlying model and may be used for
        tasks like translation, adding punctuation, augment the input directly, etc.

        Args:
            input_strings (:obj:`Union[List[str], str]`): a string or a list of strings which will be
                transformed.
            model_name (:obj:`str`): a name of a model.
            language_code (:obj:`str`): a string containing a language code for the model.
            future (:obj:`bool`, defaults to :obj:`False`): whether to return an async result instead of usual
                response. You can get a response by calling ``result()`` method of the future object.
        Returns:
            :obj:`Union[riva.client.proto.riva_nlp_pb2.TextTransformResponse, grpc._channel._MultiThreadedRendezvous]`: a
            model response. You may find :class:`TextTransformResponse` fields description `here
            <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-nlp-proto>`_.
            If :param:`future` is :obj:`True`, then a future object is returned. You may retrieve a response from a
            future object by calling ``result()`` method.
        """
        request = prepare_transform_text_request(input_strings, model_name, language_code)
        func = self.stub.TransformText.future if future else self.stub.TransformText
        return func(request, metadata=self.auth.get_auth_metadata())

    def analyze_entities(
        self, input_string: str, language_code: str = 'en-US', future: bool = False
    ) -> Union[rnlp.TokenClassResponse, _MultiThreadedRendezvous]:
        """
        Accepts an input string and returns all named entities within the text, as well as a category and likelihood.

        Args:
            input_string (:obj:`str`): a string which will be processed.
            language_code (:obj:`str`): a language code.
            future (:obj:`bool`, defaults to :obj:`False`): whether to return an async result instead of usual
                response. You can get a response by calling ``result()`` method of the future object.
        Returns:
            :obj:`Union[riva.client.proto.riva_nlp_pb2.TokenClassResponse, grpc._channel._MultiThreadedRendezvous]`: a
            model response. You may find :class:`TokenClassResponse` fields description `here
            <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-nlp-proto>`_.
            If :param:`future` is :obj:`True`, then a future object is returned. You may retrieve a response from a
            future object by calling ``result()`` method.
        """
        request = rnlp.AnalyzeEntitiesRequest(query=input_string)
        request.options.lang = language_code
        func = self.stub.AnalyzeEntities.future if future else self.stub.AnalyzeEntities
        return func(request, metadata=self.auth.get_auth_metadata())

    def analyze_intent(
        self, input_string: str, options: Optional[rnlp.AnalyzeIntentOptions] = None, future: bool = False
    ) -> Union[rnlp.AnalyzeIntentResponse, _MultiThreadedRendezvous]:
        """
        Accepts an input string and returns the most likely intent as well as slots relevant to that intent.

        The model requires that a valid "domain" be passed in, and optionally supports including a previous
        intent classification result to provide context for the model.

        Args:
            input_string (:obj:`str`): a string which will be classified.
            options (:obj:`riva.client.proto.riva_nlp_pb2.AnalyzeIntentOptions`, `optional`,
                defaults to :obj:`riva.client.proto.riva_nlp_pb2.AnalyzeIntentOptions()`):
                an intent options. You may find fields description `here
                <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-nlp-proto>`_.
                Defaults to an instance of :obj:`AnalyzeIntentOptions` created without parameters.
            future (:obj:`bool`, defaults to :obj:`False`): whether to return an async result instead of usual
                response. You can get a response by calling ``result()`` method of the future object.
        Returns:
            :obj:`Union[riva.client.proto.riva_nlp_pb2.AnalyzeIntentResponse, grpc._channel._MultiThreadedRendezvous]`: a
            response with results. You may find fields description `here
            <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-nlp-proto>`_.
            If :param:`future` is :obj:`True`, then a future object is returned. You may retrieve a response from a
            future object by calling ``result()`` method.
        """
        if options is None:
            options = rnlp.AnalyzeIntentOptions()
        request = rnlp.AnalyzeIntentRequest(query=input_string, options=options)
        func = self.stub.AnalyzeIntent.future if future else self.stub.AnalyzeIntent
        return func(request, metadata=self.auth.get_auth_metadata())

    def punctuate_text(
        self,
        input_strings: Union[List[str], str],
        model_name: Optional[str] = None,
        language_code: str = 'en-US',
        future: bool = False,
    ) -> Union[rnlp.TextTransformResponse, _MultiThreadedRendezvous]:
        """
        Takes text with no- or limited- punctuation and returns the same text with corrected punctuation and
        capitalization.

        Args:
            input_strings (:obj:`Union[List[str], str]`): a string or a list of strings which will be
                processed.
            model_name (:obj:`str`, `optional`): a name of a model.
            language_code (:obj:`str`): a string containing a language code for the model.
            future (:obj:`bool`, defaults to :obj:`False`): whether to return an async result instead of usual
                response. You can get a response by calling ``result()`` method of the future object.
        Returns:
            :obj:`Union[riva.client.proto.riva_nlp_pb2.TextTransformResponse, grpc._channel._MultiThreadedRendezvous]`: a
            response with results. You may find fields description `here
            <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-nlp-proto>`_.
            If :param:`future` is :obj:`True`, then a future object is returned. You may retrieve a response from a
            future object by calling ``result()`` method.
        """
        request = prepare_transform_text_request(input_strings, model_name, language_code)
        func = self.stub.PunctuateText.future if future else self.stub.PunctuateText
        return func(request, metadata=self.auth.get_auth_metadata())

    def natural_query(
        self, query: str, context: str, top_n: int = 1, future: bool = False
    ) -> Union[rnlp.NaturalQueryResponse, _MultiThreadedRendezvous]:
        """
        A search function that enables querying one or more documents or contexts with a query that is written in
        natural language.

        Args:
            query (:obj:`str): a natural language query.
            context (:obj:`str): a context to search with the above query.
            top_n (:obj:`int`): a maximum number of answers to return for the query.
            future (:obj:`bool`, defaults to :obj:`False`): whether to return an async result instead of usual
                response. You can get a response by calling ``result()`` method of the future object.
        Returns:
            :obj:`Union[riva.client.proto.riva_nlp_pb2.NaturalQueryResult, grpc._channel._MultiThreadedRendezvous]`: a
            response with a result. You may find fields description `here
            <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-nlp-proto>`_.
            If :param:`future` is :obj:`True`, then a future object is returned. You may retrieve a response from a
            future object by calling ``result()`` method.
        """
        request = rnlp.NaturalQueryRequest(query=query, context=context, top_n=top_n)
        func = self.stub.NaturalQuery.future if future else self.stub.NaturalQuery
        return func(request, metadata=self.auth.get_auth_metadata())


def batch_generator(examples: List[Any], batch_size: int) -> Generator[List[Any], None, None]:
    for i in range(0, len(examples), batch_size):
        yield examples[i : i + batch_size]


def process_batches_async(
    b_gen: Generator[List[Any], None, None],
    process_func: Callable[..., _MultiThreadedRendezvous],
    kwargs_except_future_and_input: Dict[str, Any],
    max_async_requests_to_queue: int,
) -> List[Message]:
    responses = []
    n_req = max_async_requests_to_queue
    while n_req == max_async_requests_to_queue:
        n_req = 0
        futures = []
        for batch in b_gen:
            futures.append(process_func(input_strings=batch, **kwargs_except_future_and_input, future=True))
            n_req += 1
            if n_req == max_async_requests_to_queue:
                break
        for f in futures:
            responses.append(f.result())
    return responses


def check_max_async_requests_to_queue(max_async_requests_to_queue: int) -> None:
    if not isinstance(max_async_requests_to_queue, int) or max_async_requests_to_queue < 0:
        raise ValueError(
            f"Parameter `max_async_requests_to_queue` has to be not negative integer whereas "
            f"`max_async_requests_to_queue={max_async_requests_to_queue}` was given."
        )


def classify_text_batch(
    nlp_service: NLPService,
    input_strings: List[str],
    model_name: str,
    batch_size: int,
    language_code: str = 'en-US',
    max_async_requests_to_queue: int = 0,
) -> Tuple[List[str], List[float]]:
    check_max_async_requests_to_queue(max_async_requests_to_queue)
    if max_async_requests_to_queue == 0:
        responses = []
        for batch in batch_generator(input_strings, batch_size):
            responses.append(nlp_service.classify_text(batch, model_name, language_code))
    else:
        responses = process_batches_async(
            batch_generator(input_strings, batch_size),
            nlp_service.classify_text,
            {'model_name': model_name, 'language_code': language_code},
            max_async_requests_to_queue,
        )
    classes, confidences = [], []
    for response in responses:
        b_classes, b_confidences = extract_most_probable_text_class_and_confidence(response)
        classes += b_classes
        confidences += b_confidences
    return classes, confidences


def classify_tokens_batch(
    nlp_service: NLPService,
    input_strings: List[str],
    model_name: str,
    batch_size: int,
    language_code: str = 'en-US',
    max_async_requests_to_queue: int = 0,
) -> Tuple[List[List[str]], List[List[str]], List[List[float]], List[List[int]], List[List[int]]]:
    check_max_async_requests_to_queue(max_async_requests_to_queue)
    if max_async_requests_to_queue == 0:
        responses = []
        for batch in batch_generator(input_strings, batch_size):
            responses.append(
                nlp_service.classify_tokens(input_strings=batch, model_name=model_name, language_code=language_code)
            )
    else:
        responses = process_batches_async(
            batch_generator(input_strings, batch_size),
            nlp_service.classify_tokens,
            {'model_name': model_name, 'language_code': language_code},
            max_async_requests_to_queue,
        )
    tokens, token_classes, confidences, starts, ends = [], [], [], [], []
    for response in responses:
        b_t, b_tc, b_conf, b_s, b_e = extract_most_probable_token_classification_predictions(response)
        tokens += b_t
        token_classes += b_tc
        confidences += b_conf
        starts += b_s
        ends += b_e
    return tokens, token_classes, confidences, starts, ends
