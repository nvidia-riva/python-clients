# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
import functools
import sys

import grpc

# Exit codes shared by the CLI scripts. Pipelines that compose these scripts
# rely on a non-zero status to detect failure; see also `cli_main` below.
EXIT_OK = 0
EXIT_GENERIC_ERROR = 1
EXIT_BAD_INPUT = 2          # malformed args, missing file, empty/whitespace text, ...
EXIT_UNAVAILABLE = 3        # gRPC UNAVAILABLE (server down, wrong port, ...)
EXIT_INVALID_ARGUMENT = 4   # gRPC INVALID_ARGUMENT or NOT_FOUND (bad model/lang/voice)
EXIT_INTERRUPTED = 130      # SIGINT


def _grpc_exit_code(error: grpc.RpcError) -> int:
    code = error.code() if callable(getattr(error, "code", None)) else None
    if code == grpc.StatusCode.UNAVAILABLE:
        return EXIT_UNAVAILABLE
    if code in (grpc.StatusCode.INVALID_ARGUMENT, grpc.StatusCode.NOT_FOUND):
        return EXIT_INVALID_ARGUMENT
    return EXIT_GENERIC_ERROR


def cli_main(func):
    """Translate exceptions raised by a CLI ``main`` into consistent exit codes.

    Wrapped function may return an int exit code or ``None`` (treated as
    ``EXIT_OK``). Unhandled exceptions are caught and mapped: gRPC ``RpcError``
    via status code, ``FileNotFoundError`` / ``ValueError`` → ``EXIT_BAD_INPUT``,
    anything else → ``EXIT_GENERIC_ERROR``. The error is also printed to stderr
    so CI logs surface the cause.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return EXIT_OK if result is None else int(result)
        except KeyboardInterrupt:
            return EXIT_INTERRUPTED
        except grpc.RpcError as e:
            details = e.details() if callable(getattr(e, "details", None)) else str(e)
            print(f"Error: {details}", file=sys.stderr)
            return _grpc_exit_code(e)
        except (FileNotFoundError, IsADirectoryError, ValueError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return EXIT_BAD_INPUT
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return EXIT_GENERIC_ERROR

    return wrapper


def validate_grpc_message_size(value):
    """Validate that the GRPC message size is within acceptable limits."""
    min_size = 4 * 1024 * 1024  # 4MB
    max_size = 1024 * 1024 * 1024  # 1GB

    try:
        size = int(value)
        if size < min_size:
            raise argparse.ArgumentTypeError(f"GRPC message size must be at least {min_size} bytes (4MB)")
        if size > max_size:
            raise argparse.ArgumentTypeError(f"GRPC message size must be at most {max_size} bytes (1GB)")
        return size
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a valid integer")

def add_asr_config_argparse_parameters(
    parser: argparse.ArgumentParser, max_alternatives: bool = False, profanity_filter: bool = False, word_time_offsets: bool = False
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
        "--no-verbatim-transcripts",
        default=False,
        action='store_true',
        help="If specified, text inverse normalization will be applied",
    )
    parser.add_argument("--language-code", default="en-US", help="Language code of the model to be used.")
    parser.add_argument("--model-name", default="", help="Model name to be used.")
    parser.add_argument("--boosted-lm-words", action='append', help="Words to boost when decoding. Can be used multiple times to boost multiple words.")
    parser.add_argument(
        "--boosted-lm-score", type=float, default=4.0, help="Recommended range for the boost score is 20 to 100. The higher the boost score, the more biased the ASR engine is towards this word."
    )
    parser.add_argument(
        "--speaker-diarization",
        default=False,
        action='store_true',
        help="Flag that controls if speaker diarization should be performed",
    )
    parser.add_argument(
        "--diarization-max-speakers",
        default=3,
        type=int,
        help="Max number of speakers to detect when performing speaker diarization",
    )
    parser.add_argument(
        "--start-history",
        default=-1,
        type=int,
        help="Value (in milliseconds) to detect and initiate start of speech utterance",
    )
    parser.add_argument(
        "--start-threshold",
        default=-1.0,
        type=float,
        help="Threshold value for detecting the start of speech utterance",
    )
    parser.add_argument(
        "--stop-history",
        default=-1,
        type=int,
        help="Value (in milliseconds) to detect end of utterance and reset decoder",
    )
    parser.add_argument(
        "--stop-threshold",
        default=-1.0,
        type=float,
        help="Threshold value for detecting the end of speech utterance",
    )
    parser.add_argument(
        "--stop-history-eou",
        default=-1,
        type=int,
        help="Value (in milliseconds) to detect end of utterance for the 1st pass and generate an intermediate final transcript",
    )
    parser.add_argument(
        "--stop-threshold-eou",
        default=-1.0,
        type=float,
        help="Threshold value for likelihood of blanks before detecting end of utterance",
    )
    parser.add_argument(
        "--custom-configuration",
        default="",
        type=str,
        help="Custom configurations to be sent to the server as key value pairs <key:value,key:value,...>",
    )
    return parser


def add_connection_argparse_parameters(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--server", default="localhost:50051", help="URI to GRPC server endpoint.")
    parser.add_argument("--ssl-root-cert", help="Path to SSL root certificates file.")
    parser.add_argument("--ssl-client-cert", help="Path to SSL client certificates file.")
    parser.add_argument("--ssl-client-key", help="Path to SSL client key file.")
    parser.add_argument(
        "--use-ssl", action='store_true', help="Boolean to control if SSL/TLS encryption should be used."
    )
    parser.add_argument("--metadata", action='append', nargs='+', help="Send HTTP Header(s) to server")
    parser.add_argument("--options", action='append', nargs='+', help="Send GRPC options to server")
    parser.add_argument(
        "--max-message-length", type=validate_grpc_message_size, default=64 * 1024 * 1024, help="Maximum message length for GRPC server."
    )
    return parser

def add_realtime_config_argparse_parameters(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--endpoint", default="/v1/realtime", help="Endpoint to WebSocket server endpoint.")
    parser.add_argument("--query-params", default="intent=transcription", help="Query parameters to WebSocket server endpoint.")
    return parser