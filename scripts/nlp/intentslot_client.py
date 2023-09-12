# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
import time
from typing import List

import riva.client
from riva.client.argparse_utils import add_connection_argparse_parameters


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Client app to run intent slot on Riva", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--model", default="riva_intent_weather", help="Model on Riva Server to execute."
    )
    parser.add_argument("--query", default="What is the weather tomorrow?", help="Input Query")
    parser.add_argument(
        "--interactive",
        action='store_true',
        help="If this option is set, then `--query` argument is ignored and the script suggests user to enter "
        "queries to standard input.",
    )
    parser = add_connection_argparse_parameters(parser)
    return parser.parse_args()


def pretty_print_result(
    intent: str, intent_score: float, slots: List[str], tokens: List[str], slot_scores: List[float], duration: float
) -> None:
    print(f"Inference complete in {duration * 1000:.4f} ms")
    print("Intent:", intent)
    print("Intent Score:", intent_score)
    print("Slots:", slots)
    print("Slots Scores:", slot_scores)
    if len(tokens) > 0:
        print("Combined: ", end="")
        for token, slot in zip(tokens, slots):
            print(f"{token}{f'({slot})' if slot != 'O' else ''}", end=" ")
        print("\n")


def main() -> None:
    args = parse_args()
    auth = riva.client.Auth(args.ssl_cert, args.use_ssl, args.server, args.metadata)
    service = riva.client.NLPService(auth)
    if args.interactive:
        while True:
            query = input("Enter a query: ")
            start = time.time()
            intents, intent_confidences = riva.client.extract_most_probable_text_class_and_confidence(
                service.classify_text(input_strings=query, model_name=args.model)
            )
            tokens, slots, slot_confidences, _, _ = riva.client.extract_most_probable_token_classification_predictions(
                service.classify_tokens(input_strings=query, model_name=args.model)
            )
            end = time.time()
            pretty_print_result(
                intents[0], intent_confidences[0], slots[0], tokens[0], slot_confidences[0], end - start
            )
    else:
        intents, intent_confidences = riva.client.extract_most_probable_text_class_and_confidence(
            service.classify_text(input_strings=args.query, model_name=args.model)
        )
        tokens, slots, slot_confidences, _, _ = riva.client.extract_most_probable_token_classification_predictions(
            service.classify_tokens(input_strings=args.query, model_name=args.model)
        )
        results = [
            (intents[i], intent_confidences[i], slots[i], tokens[i], slot_confidences[i]) for i in range(len(slots))
        ]
        print(results)


if __name__ == '__main__':
    main()
