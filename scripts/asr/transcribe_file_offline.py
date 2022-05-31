# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
from pathlib import Path

import grpc
import riva_api
from riva_api.argparse_utils import add_asr_config_argparse_parameters, add_connection_argparse_parameters


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline file transcription via Riva AI Services. \"Offline\" means that entire audio "
        "content of `--input-file` is sent in one request and then a transcript for whole file recieved in "
        "one response.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input-file", required=True, type=Path, help="A path to local file to stream.")
    parser = add_connection_argparse_parameters(parser)
    parser = add_asr_config_argparse_parameters(parser)
    args = parser.parse_args()
    args.input_file = args.input_file.expanduser()
    return args


def main() -> None:
    args = parse_args()
    auth = riva_api.Auth(args.ssl_cert, args.use_ssl, args.server)
    asr_service = riva_api.ASRService(auth)
    config = riva_api.RecognitionConfig(
        encoding=riva_api.AudioEncoding.LINEAR_PCM,
        language_code=args.language_code,
        max_alternatives=1,
        enable_automatic_punctuation=args.automatic_punctuation,
        verbatim_transcripts=not args.no_verbatim_transcripts,
    )
    riva_api.add_audio_file_specs_to_config(config, args.input_file)
    riva_api.add_word_boosting_to_config(config, args.boosted_lm_words, args.boosted_lm_score)
    with args.input_file.open('rb') as fh:
        data = fh.read()
    try:
        riva_api.print_offline(response=asr_service.offline_recognize(data, config))
    except grpc.RpcError as e:
        print(e.details())


if __name__ == "__main__":
    main()
