# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse

import riva.client
from riva.client.argparse_utils import add_connection_argparse_parameters


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Client app to run NER on Riva", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--model", default="riva_ner", help="Model on Riva Server to execute.")
    parser.add_argument(
        "--query", nargs="+", default=["Where is San Francisco?", "Jensen Huang is the CEO of NVIDIA Corporation."]
    )
    parser.add_argument(
        "--test",
        default="label",
        choices=['label', 'span_start', 'span_end'],
        help="What info will be printed to STDOUT. If 'label', then a class of an entity will be printed. "
        "If 'span_start', then indices of first characters of entities are printed. For example, for a query "
        "'cats are nice' if an entity is 'cats', then 'span_start' is 0. If 'span_end', then indices of "
        "first characters following entities are printed. For example, for the query 'cats are nice' for entity "
        "'cats' 'span_end' is 4.",
    )
    parser = add_connection_argparse_parameters(parser)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    auth = riva.client.Auth(args.ssl_cert, args.use_ssl, args.server)
    service = riva.client.NLPService(auth)
    tokens, slots, slot_confidences, starts, ends = riva.client.extract_most_probable_token_classification_predictions(
        service.classify_tokens(input_strings=args.query, model_name=args.model)
    )
    test_mode = args.test
    if test_mode == "label":
        print(slots)
    elif test_mode == "span_start":
        print(starts)
    elif test_mode == "span_end":
        print(ends)
    else:
        raise ValueError(
            f"Testing mode '{test_mode}' is not supported. Supported testing modes are: 'label', 'span_start', "
            f"'span_end'"
        )


if __name__ == '__main__':
    main()
