# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse

import riva_api
from riva_api.argparse_utils import add_connection_argparse_parameters


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Client app to run Text Classification on Riva.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--model", default="riva_text_classification_domain", help="Model on Riva Server to execute.")
    parser.add_argument("--query", default="How much sun does california get?", help="An input query.")
    parser = add_connection_argparse_parameters(parser)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    auth = riva_api.Auth(args.ssl_cert, args.use_ssl, args.server)
    service = riva_api.NLPService(auth)
    print(riva_api.nlp.extract_most_probable_text_class_and_confidence(service.classify_text(args.query, args.model)))


if __name__ == '__main__':
    main()
