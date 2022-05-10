# Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

import argparse

import riva_api
from riva_api.argparse_utils import add_connection_argparse_parameters


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Client app to test Punctuation on Riva")
    parser.add_argument("--model", default="riva_punctuation", type=str, help="Model on Riva Server to execute")
    parser.add_argument("--query", default="can you prove that you are self aware", type=str, help="Input Query")
    parser.add_argument("--run_tests", default=False, action='store_true', help="Flag to run sanity tests")
    parser = add_connection_argparse_parameters(parser)
    return parser.parse_args()


def run_punct_capit(args):
    auth = riva_api.Auth(args.ssl_cert, args.use_ssl, args.server)
    nlp_service = riva_api.NLPService(auth)
    print(
        riva_api.nlp.extract_most_probable_transformed_text(
            nlp_service.punctuate_text(
                input_strings=args.query,
                model_name=args.model,
            )
        )
    )


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

    auth = riva_api.Auth(args.ssl_cert, args.use_ssl, args.server)
    nlp_service = riva_api.NLPService(auth)

    fail_count = 0
    for input, output_ref in zip(test_inputs, test_output_ref):
        pred = riva_api.nlp.extract_most_probable_transformed_text(
            nlp_service.punctuate_text(
                input_strings=input,
                model_name=args.model,
            )
        )
        print(f"Input: {input}")
        print(f"Output: {pred}")
        if pred != output_ref:
            print(f"Output mismatched!")
            print(f"Output reference: {output_ref}")
            fail_count += 1

    print(f"Tests passed: {len(test_inputs) - fail_count}")
    print(f"Tests failed: {fail_count}")
    return fail_count


def main() -> None:
    args = get_args()
    if args.run_tests:
        exit(run_tests(args))
    else:
        run_punct_capit(args)


if __name__ == '__main__':
    main()
