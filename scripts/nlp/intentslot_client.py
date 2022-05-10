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


def get_args():
    parser = argparse.ArgumentParser(
        description="Client app to test intent slot on Riva", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--model", default="riva_intent_weather", type=str, help="Model on Riva Server to " "execute"
    )
    parser.add_argument("--query", default="What is the weather tomorrow?", type=str, help="Input Query")
    parser = add_connection_argparse_parameters(parser)
    return parser.parse_args()


def main() -> None:
    args = get_args()
    auth = riva_api.Auth(args.ssl_cert, args.use_ssl, args.server)
    service = riva_api.NLPService(auth)
    intents, intent_confidences = riva_api.extract_most_probable_text_class_and_confidence(
        service.classify_text(input_strings=args.query, model_name=args.model)
    )
    tokens, slots, slot_confidences, _, _ = riva_api.extract_most_probable_token_classification_predictions(
        service.classify_tokens(input_strings=args.query, model_name=args.model)
    )
    results = [(intents[i], intent_confidences[i], slots[i], tokens[i], slot_confidences[i]) for i in range(len(slots))]
    print(results)


if __name__ == '__main__':
    main()
