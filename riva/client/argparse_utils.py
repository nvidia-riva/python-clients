# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
from pathlib import Path


def add_asr_config_argparse_parameters(
    parser: argparse.ArgumentParser,
    max_alternatives: bool = False,
    profanity_filter: bool = False,
    word_time_offsets: bool = False,
) -> argparse.ArgumentParser:
    if word_time_offsets:
        parser.add_argument(
            "--word-time-offsets", default=False, action='store_true', help="Option to output word timestamps."
        )
    if max_alternatives:
        parser.add_argument(
            "--max-alternatives",
            default=1,
            type=int,
            help="Maximum number of alternative transcripts to return (up to limit configured on server).",
        )
    if profanity_filter:
        parser.add_argument(
            "--profanity-filter",
            default=False,
            action='store_true',
            help="Flag that controls the profanity filtering in the generated transcripts",
        )
    parser.add_argument(
        "--automatic-punctuation",
        default=False,
        action='store_true',
        help="Flag that controls if transcript should be automatically punctuated",
    )
    parser.add_argument(
        "--verbatim-transcripts",
        default=True,
        action='store_false',
        help="True returns text exactly as it was said. False applies Inverse text normalization",
    )
    parser.add_argument("--language-code", default="en-US", help="Language code of the model to be used.")
    parser.add_argument("--model-name", default="", help="Name of the model to be used to be used.")
    parser.add_argument(
        "--boosted-words-file", default=None, type=Path, help="File with a list of words to boost. One line per word."
    )
    parser.add_argument(
        "--boosted-words-score", type=float, default=4.0, help="Score by which to boost the boosted words."
    )
    parser.add_argument(
        "--speaker-diarization",
        default=False,
        action='store_true',
        help="Flag that controls if speaker diarization should be performed",
    )
    return parser


def add_connection_argparse_parameters(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--server", default="localhost:50051", help="URI to GRPC server endpoint.")
    parser.add_argument("--ssl-cert", help="Path to SSL client certificates file.")
    parser.add_argument(
        "--use-ssl", action='store_true', help="Boolean to control if SSL/TLS encryption should be used."
    )
    parser.add_argument("--metadata", action='append', nargs='+', help="Send HTTP Header(s) to server")
    return parser
