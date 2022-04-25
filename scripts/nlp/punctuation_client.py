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


class BertPunctuatorClient(object):
    def __init__(self, grpc_server, model_name="riva_punctuation", use_ssl=False, ssl_cert=""):
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

    def run(self, input_strings):
        if isinstance(input_strings, str):
            # user probably passed a single string instead of a list/iterable
            input_strings = [input_strings]

        request = rnlp.TextTransformRequest()
        request.model.model_name = self.model_name
        for q in input_strings:
            request.text.append(q)
        response = self.riva_nlp.TransformText(request)

        return response.text[0]


def get_args():
    parser = argparse.ArgumentParser(description="Client app to test Punctuation on Riva")
    parser.add_argument("--server", default="localhost:50051", type=str, help="URI to GRPC server endpoint")
    parser.add_argument("--model", default="riva_punctuation", type=str, help="Model on Riva Server to execute")
    parser.add_argument("--query", default="can you prove that you are self aware", type=str, help="Input Query")
    parser.add_argument("--run_tests", default=False, action='store_true', help="Flag to run sanity tests")
    parser.add_argument("--ssl_cert", type=str, default="", help="Path to SSL client certificatates file")
    parser.add_argument(
        "--use_ssl", default=False, action='store_true', help="Boolean to control if SSL/TLS encryption should be used"
    )
    return parser.parse_args()


def run_punct_capit(args):
    client = BertPunctuatorClient(args.server, model_name=args.model, use_ssl=args.use_ssl, ssl_cert=args.ssl_cert)
    result = client.run(args.query)
    print(result)


def run_tests(args):
    test_inputs = [
        "can you prove that you are self aware",
        "will you have $103 and ₩111 at 12:45 pm",
        # "Hi My name is markus stoinis How are you ?", # This fails for onnx model
        "the train leaves station by 09:45 A.M. and reaches destination in 3 hours",
        "Loona (stylized as LOOΠΔ, Korean: 이달의 소녀; Hanja: Idarui Sonyeo; lit. ''Girl of the Month'') is a South Korean girl group formed by Blockberry Creative",
    ]
    test_output_ref = [
        "Can you prove that you are self aware?",
        "Will you have $103 and ₩111 at 12:45 pm?",
        # "Hi, My name is Markus Stoinis. How are you ?",
        "The train leaves station by 09:45 A.M. and reaches destination in 3 hours.",
        "Loona (stylized as LOOΠΔ, Korean: 이달의 소녀; Hanja: Idarui Sonyeo; lit. ''Girl of the Month'') is a South Korean girl group formed by Blockberry Creative.",
    ]

    client = BertPunctuatorClient(args.server, model_name=args.model)

    fail_count = 0
    for input, output_ref in zip(test_inputs, test_output_ref):
        result = client.run(input)
        print(f"Input: {input}")
        print(f"Output: {result}")
        if result != output_ref:
            print(f"Output mismatched!")
            print(f"Output reference: {output_ref}")
            fail_count += 1

    print(f"Tests passed: {len(test_inputs) - fail_count}")
    print(f"Tests failed: {fail_count}")
    return fail_count


if __name__ == '__main__':
    args = get_args()
    if args.run_tests:
        exit(run_tests(args))
    else:
        run_punct_capit(args)
