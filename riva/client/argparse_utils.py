# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
import riva.client


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
        "--encoding",
        type=int,
        default=riva.client.AudioEncoding.Value('ENCODING_UNSPECIFIED'),
        help=f"Encoding of the audio data. Supported values are {riva.client.AudioEncoding.items()}",
    )
    parser.add_argument(
        "--sample-rate-hertz", type=int, default=None, help=f"Sample rate in Hz of the audio data",
    )
    parser.add_argument(
        "--audio-channel-count", type=int, default=None, help=f"Channel count of the audio data",
    )
    parser.add_argument(
        "--automatic-punctuation",
        default=False,
        action='store_true',
        help="Flag that controls if transcript should be automatically punctuated",
    )
    parser.add_argument(
        "--verbatim-transcripts",
        default=False,
        action='store_true',
        help="Flag to disable Inverse Text Normalization (ITN) and return the text exactly as it was said",
    )
    parser.add_argument("--model-name", default="", help="Name of the model to be used to be used.")
    parser.add_argument("--language-code", default="en-US", help="Language code of the model to be used.")
    parser.add_argument("--boosted-lm-words", action='append', help="Words to boost when decoding.")
    parser.add_argument(
        "--boosted-lm-score", type=float, default=4.0, help="Value by which to boost words when decoding."
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
