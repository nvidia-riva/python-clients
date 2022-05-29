import argparse


def add_asr_config_argparse_parameters(
    parser: argparse.ArgumentParser, max_alternatives: bool = False, word_time_offsets: bool = False
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
    parser.add_argument("--language-code", default="en-US", type=str, help="Language code of the model to be used.")
    parser.add_argument("--boosted-lm-words", type=str, action='append', help="Words to boost when decoding.")
    parser.add_argument(
        "--boosted-lm-score", type=float, default=4.0, help="Value by which to boost words when decoding."
    )
    return parser


def add_connection_argparse_parameters(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--server", default="localhost:50051", type=str, help="URI to GRPC server endpoint.")
    parser.add_argument("--ssl_cert", type=str, help="Path to SSL client certificates file.")
    parser.add_argument(
        "--use_ssl", action='store_true', help="Boolean to control if SSL/TLS encryption should be used."
    )
    return parser
