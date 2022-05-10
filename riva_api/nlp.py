from typing import List, Tuple, Union

import riva_api.proto.riva_nlp_pb2 as rnlp
import riva_api.proto.riva_nlp_pb2_grpc as rnlp_srv
from riva_api import Auth


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
    request.model.model_name = model_name
    request.model.language_code = language_code
    for q in input_strings:
        request.text.append(q)
    return request


class NLPService:
    def __init__(self, auth: Auth) -> None:
        self.auth = auth
        self.stub = rnlp_srv.RivaLanguageUnderstandingStub(self.auth.channel)

    def classify_text(
        self, input_strings: Union[List[str], str], model_name: str, language_code: str = 'en-US'
    ) -> rnlp.TextClassResponse:
        if isinstance(input_strings, str):
            input_strings = [input_strings]
        request = rnlp.TextClassRequest()
        request.model.model_name = model_name
        request.model.language_code = language_code
        for q in input_strings:
            request.text.append(q)
        return self.stub.ClassifyText(request)

    def classify_tokens(
        self, input_strings: Union[List[str], str], model_name: str, language_code: str = 'en-US'
    ) -> rnlp.TokenClassResponse:
        if isinstance(input_strings, str):
            input_strings = [input_strings]
        request = rnlp.TokenClassRequest()
        request.model.model_name = model_name
        request.model.language_code = language_code
        for q in input_strings:
            request.text.append(q)
        return self.stub.ClassifyTokens(request)

    def transform_text(
        self, input_strings: Union[List[str], str], model_name: str, language_code: str = 'en-US',
    ) -> rnlp.TextTransformResponse:
        request = prepare_transform_text_request(input_strings, model_name, language_code)
        return self.stub.TransformText(request)

    def analyze_entities(self, input_string: str, language_code: str = 'en-US') -> rnlp.TokenClassResponse:
        request = rnlp.AnalyzeEntitiesRequest(query=input_string)
        request.options.lang = language_code
        return self.stub.AnalyzeEntities(request)

    def analyze_intent(self, input_string: str, options: rnlp.AnalyzeIntentOptions) -> rnlp.AnalyzeIntentResponse:
        request = rnlp.AnalyzeEntitiesRequest(query=input_string)
        request.options = options
        return self.stub.AnalyzeIntent(request)

    def punctuate_text(
        self, input_strings: Union[List[str], str], model_name: str, language_code: str = 'en-US',
    ) -> rnlp.TextTransformResponse:
        request = prepare_transform_text_request(input_strings, model_name, language_code)
        return self.stub.PunctuateText(request)

    def natural_query(self, query: str, context: str, top_n: int = 1) -> rnlp.NaturalQueryResult:
        request = rnlp.NaturalQueryRequest(query=query, context=context, top_n=top_n)
        return self.stub.NaturalQuery(request)
