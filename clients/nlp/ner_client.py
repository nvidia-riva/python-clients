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
import riva_api.riva_nlp_pb2 as rnlp
import riva_api.riva_nlp_pb2_grpc as rnlp_srv


class BertNERClient(object):
    def __init__(self, grpc_server, model_name="riva_ner", use_ssl=False, ssl_cert=""):
        # generate the correct model based on precision and whether or not ensemble is used
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

    # use the NER network to return top-1 classes for entities
    def postprocess_labels_server(self, tokens_response):
        results = []
        for i in range(0, len(tokens_response.results)):
            slots = []
            slot_scores = []
            tokens = []
            starts = []
            ends = []
            for j in range(0, len(tokens_response.results[i].results)):
                entity = tokens_response.results[i].results[j]
                tokens.append(entity.token)
                slots.append(entity.label[0].class_name)
                slot_scores.append(entity.label[0].score)
                starts.append(entity.span[0].start)
                ends.append(entity.span[0].end)
            results.append((slots, tokens, slot_scores, starts, ends))

        return results

    # accept a list of strings, return a list of resuls((slots, tokens, scores, starts, ends))
    def run(self, input_strings):
        # get slots/entities
        request = rnlp.TokenClassRequest()
        request.model.model_name = self.model_name
        for q in input_strings:
            request.text.append(q)
        tokens_response = self.riva_nlp.ClassifyTokens(request)

        return self.postprocess_labels_server(tokens_response)


def get_args():
    parser = argparse.ArgumentParser(description="Client app to test intent slot on Riva")
    parser.add_argument("--server", default="localhost:50051", type=str, help="URI to GRPC server endpoint")
    parser.add_argument("--model", default="riva_ner", type=str, help="Model on Riva Server to execute")
    parser.add_argument(
        "--query", nargs="+", default=["Where is San Francisco?", "Jensen Huang is the CEO of NVIDIA Corporation."]
    )
    parser.add_argument("--test", default="label", type=str, help="Testing mode")
    parser.add_argument("--ssl_cert", type=str, default="", help="Path to SSL client certificatates file")
    parser.add_argument(
        "--use_ssl", default=False, action='store_true', help="Boolean to control if SSL/TLS encryption should be used"
    )
    return parser.parse_args()


def run_ner_client():
    args = get_args()
    client = BertNERClient(args.server, model_name=args.model, use_ssl=args.use_ssl, ssl_cert=args.ssl_cert)
    results = client.run(args.query)
    test_mode = args.test

    if test_mode == "label":
        labels = []
        for i in range(0, len(results)):
            labels += results[i][0]
        print(labels)

    elif test_mode == "span_start":
        starts = []
        for i in range(0, len(results)):
            starts += results[i][3]
        print(starts)

    elif test_mode == "span_end":
        ends = []
        for i in range(0, len(results)):
            ends += results[i][4]
        print(ends)

    else:
        raise RuntimeError('Cannot find the testing option')


if __name__ == '__main__':
    run_ner_client()
