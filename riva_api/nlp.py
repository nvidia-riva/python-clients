from typing import List, Union

import riva_api.proto.riva_nlp_pb2 as rnlp
import riva_api.proto.riva_nlp_pb2_grpc as rnlp_srv
from riva_api import Auth


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

    def natural_query(self, query: str, context: str, top_n: int) -> rnlp.NaturalQueryResult:
        request = rnlp.NaturalQueryRequest(query=query, context=context, top_n=top_n)
        return self.stub.NaturalQuery(request)
