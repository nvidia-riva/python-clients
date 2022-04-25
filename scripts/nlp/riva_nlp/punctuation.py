import os

import grpc
import riva_api.proto.riva_nlp_pb2 as rnlp
import riva_api.proto.riva_nlp_pb2_grpc as rnlp_srv


class BertPunctuator(object):
    def __init__(self, grpc_server, model_name="punctuator", use_ssl=False, ssl_cert=""):
        # generate the correct model based on precision and whether or not ensemble is used
        print("Using model: {}".format(model_name))

        self.model_name = model_name
        if ssl_cert != "" or use_ssl:
            root_certificates = None
            if ssl_cert != "" and os.path.exists(ssl_cert):
                with open(ssl_cert, 'rb') as f:
                    root_certificates = f.read()
            creds = grpc.ssl_channel_credentials(root_certificates)
            self.channel = grpc.secure_channel(grpc_server, creds)
        else:
            self.channel = grpc.insecure_channel(grpc_server)
        self.riva_nlp = rnlp_srv.RivaLanguageUnderstandingStub(self.channel)

        self.has_bos = True
        self.has_eos = False

    def postprocess_labels_server(self, output_strings):
        results = []

        for result_idx in range(len(output_strings)):
            result = output_strings[result_idx][0].decode("utf-8")

            results.append(result)
        return results

    # accept a list of strings, returns a list of strings ['tokens', 'with', 'punctuation'])
    def run(self, input_strings):
        if isinstance(input_strings, str):
            # user probably passed a single string instead of a list/iterable
            input_strings = [input_strings]

        request = rnlp.TextTransformRequest()
        request.model.model_name = self.model_name
        request.full_text = input_strings
        request.text.append(input_strings)
        response = riva_nlp.TransformText(request)
        riva_response = self.riva_nlp.TokenClassResponse(request)

        return self.postprocess_labels_server(response.text[0])
