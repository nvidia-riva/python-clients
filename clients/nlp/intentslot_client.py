# Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

import argparse
import os

import grpc
import riva_api.proto.riva_nlp_pb2 as rnlp
import riva_api.proto.riva_nlp_pb2_grpc as rnlp_srv


class BertIntentSlotClient(object):
    def __init__(self, grpc_server, model_name="riva_intent_weather-misc", use_ssl=False, ssl_cert=""):
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

        self.has_bos_eos = False

    # use the internal slot/intent lists and network logits to return top-1 classes for intent/slots
    def postprocess_labels_server(self, ct_response, tokens_response):
        results = []

        for i in range(0, len(ct_response.results)):
            intent_str = ct_response.results[i].labels[0].class_name
            intent_conf = ct_response.results[i].labels[0].score

            slots = []
            slot_scores = []
            tokens = []
            for j in range(0, len(tokens_response.results[i].results)):
                entity = tokens_response.results[i].results[j]
                tokens.append(entity.token)
                slots.append(entity.label[0].class_name)
                slot_scores.append(entity.label[0].score)

            results.append((intent_str, intent_conf, slots, tokens, slot_scores))

        return results

    # accept a list of strings, return a list of tuples ('intent', ['slot', 'label', 'per', 'token'])
    def run(self, input_strings, api="classify_tokens"):
        if isinstance(input_strings, str):
            # user probably passed a single string instead of a list/iterable
            input_strings = [input_strings]

        # get intent of the query
        request = rnlp.TextClassRequest()
        request.model.model_name = self.model_name
        for q in input_strings:
            request.text.append(q)
        ct_response = self.riva_nlp.ClassifyText(request)

        # get slots/entities
        request = rnlp.TokenClassRequest()
        request.model.model_name = self.model_name
        for q in input_strings:
            request.text.append(q)
        if api == "classify_tokens":
            tokens_response = self.riva_nlp.ClassifyTokens(request)
        else:
            tokens_response = self.riva_nlp.AnalyzeIntent(request)

        return self.postprocess_labels_server(ct_response, tokens_response)


def get_args():
    parser = argparse.ArgumentParser(description="Client app to test intent slot on Riva")
    parser.add_argument("--server", default="localhost:50051", type=str, help="URI to GRPC server endpoint")
    parser.add_argument(
        "--model", default="riva_intent_weather-misc", type=str, help="Model on Riva Server to " "execute"
    )
    parser.add_argument("--query", default="What is the weather tomorrow?", type=str, help="Input Query")
    parser.add_argument("--api", default="classify_tokens", type=str, help="Which API to use")
    parser.add_argument("--ssl_cert", type=str, default="", help="Path to SSL client certificatates file")
    parser.add_argument(
        "--use_ssl", default=False, action='store_true', help="Boolean to control if SSL/TLS encryption should be used"
    )
    return parser.parse_args()


def run_intent_slot():
    args = get_args()
    client = BertIntentSlotClient(args.server, model_name=args.model, use_ssl=args.use_ssl, ssl_cert=args.ssl_cert)
    result = client.run(args.query)
    print(result)


if __name__ == '__main__':
    run_intent_slot()
