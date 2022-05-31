# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse

import riva_api
from riva_api.argparse_utils import add_asr_config_argparse_parameters, add_connection_argparse_parameters

import riva_api.audio_io


def parse_args() -> argparse.Namespace:
    default_device_info = riva_api.audio_io.get_default_input_device_info()
    default_device_index = None if default_device_info is None else default_device_info['index']
    parser = argparse.ArgumentParser(
        description="Streaming transcription from microphone via Riva AI Services",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input-device", type=int, default=default_device_index, help="An input audio device to use.")
    parser.add_argument("--list-devices", action="store_true", help="List input audio device indices.")
    parser = add_asr_config_argparse_parameters(parser)
    parser = add_connection_argparse_parameters(parser)
    parser.add_argument(
        "--sample-rate-hz",
        type=int,
        help="A number of frames per second in audio streamed from a microphone.",
        default=16000,
    )
    parser.add_argument(
        "--file-streaming-chunk",
        type=int,
        default=1600,
        help="A maximum number of frames in a audio chunk sent to server.",
    )
    args = parser.parse_args()
    return args


def main() -> None:
    args = parse_args()
    if args.list_devices:
        riva_api.audio_io.list_input_devices()
        return
    auth = riva_api.Auth(args.ssl_cert, args.use_ssl, args.server)
    asr_service = riva_api.ASRService(auth)
    config = riva_api.StreamingRecognitionConfig(
        config=riva_api.RecognitionConfig(
            encoding=riva_api.AudioEncoding.LINEAR_PCM,
            language_code=args.language_code,
            max_alternatives=1,
            enable_automatic_punctuation=args.automatic_punctuation,
            verbatim_transcripts=not args.no_verbatim_transcripts,
            sample_rate_hertz=args.sample_rate_hz,
            audio_channel_count=1,
        ),
        interim_results=True,
    )
    riva_api.add_word_boosting_to_config(config, args.boosted_lm_words, args.boosted_lm_score)
    with riva_api.audio_io.MicrophoneStream(
        args.sample_rate_hz,
        args.file_streaming_chunk,
        device=args.input_device,
    ) as audio_chunk_iterator:
        riva_api.print_streaming(
            responses=asr_service.streaming_response_generator(
                audio_chunks=audio_chunk_iterator,
                streaming_config=config,
            ),
            show_intermediate=True,
        )


if __name__ == '__main__':
    main()
