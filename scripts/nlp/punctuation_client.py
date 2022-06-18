# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
import time

import riva_api
from riva_api.argparse_utils import add_connection_argparse_parameters


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Client app to restore Punctuation and Capitalization with Riva",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--model",
        help="Model on Riva Server to execute. If this parameter is missing, than server will try to select a first "
        "available Punctuation & Capitalization model.",
    )
    parser.add_argument("--query", default="can you prove that you are self aware", help="Input Query")
    parser.add_argument(
        "--run_tests",
        action='store_true',
        help="Flag to run sanity tests. If this option is chosen, then options `--query` and `--interactive` are "
        "ignored and a model is run on several hardcoded examples and numbers of passed and failed tests are shown.",
    )
    parser.add_argument(
        "--interactive",
        action='store_true',
        help="If this option is set, then `--query` argument is ignored and the script suggests user to enter "
        "queries to standard input.",
    )
    parser = add_connection_argparse_parameters(parser)
    return parser.parse_args()


def run_punct_capit(args: argparse.Namespace) -> None:
    auth = riva_api.Auth(args.ssl_cert, args.use_ssl, args.server)
    nlp_service = riva_api.NLPService(auth)
    if args.interactive:
        while True:
            query = input("Enter a query: ")
            start = time.time()
            result = riva_api.nlp.extract_most_probable_transformed_text(
                nlp_service.punctuate_text(input_strings=query, model_name=args.model)
            )
            end = time.time()
            print(f"Inference complete in {(end - start) * 1000:.4f} ms")
            print(result, end='\n' * 2)
    else:
        print(
            riva_api.nlp.extract_most_probable_transformed_text(
                nlp_service.punctuate_text(input_strings=args.query, model_name=args.model)
            )
        )


def run_tests(args: argparse.Namespace) -> int:
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
    args = parse_args()
    if args.run_tests:
        exit(run_tests(args))
    else:
        run_punct_capit(args)


if __name__ == '__main__':
    main()
