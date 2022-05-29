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


def parse_args():
    parser = argparse.ArgumentParser(
        description="Client app to test intent slot on Riva", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--model", default="riva_ner", type=str, help="Model on Riva Server to execute")
    parser.add_argument(
        "--query", nargs="+", default=["Where is San Francisco?", "Jensen Huang is the CEO of NVIDIA Corporation."]
    )
    parser.add_argument("--test", default="label", type=str, help="Testing additional_info")
    parser = add_connection_argparse_parameters(parser)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    auth = riva_api.Auth(args.ssl_cert, args.use_ssl, args.server)
    service = riva_api.NLPService(auth)
    tokens, slots, slot_confidences, starts, ends = riva_api.extract_most_probable_token_classification_predictions(
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
