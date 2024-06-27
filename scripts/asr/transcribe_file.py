# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse

import riva.client
from riva.client.argparse_utils import add_asr_config_argparse_parameters, add_connection_argparse_parameters


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Streaming transcription of a file via Riva AI Services. Streaming means that audio is sent to a "
        "server in small chunks and transcripts are returned as soon as these transcripts are ready. "
        "You may play transcribed audio simultaneously with transcribing by setting one of parameters "
        "`--play-audio` or `--output-device`.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input-file", help="A path to a local file to stream.")
    parser.add_argument("--list-devices", action="store_true", help="List output devices indices")
    parser.add_argument(
        "--show-intermediate", action="store_true", help="Show intermediate transcripts as they are available."
    )
    parser.add_argument(
        "--output-device",
        type=int,
        default=None,
        help="Output audio device to use for playing audio simultaneously with transcribing. If this parameter is "
        "provided, then you do not have to `--play-audio` option."
    )
    parser.add_argument(
        "--play-audio",
        action="store_true",
        help="Whether to play input audio simultaneously with transcribing. If `--output-device` is not provided, "
        "then the default output audio device will be used.",
    )
    parser.add_argument(
        "--file-streaming-chunk",
        type=int,
        default=1600,
        help="A maximum number of frames in one chunk sent to server.",
    )
    parser.add_argument(
        "--simulate-realtime",
        action='store_true',
        help="Option to simulate realtime transcription. Audio fragments are sent to a server at a pace that mimics "
        "normal speech.",
    )
    parser.add_argument(
        "--print-confidence", action="store_true", help="Whether to print stability and confidence of transcript."
    )
    parser = add_connection_argparse_parameters(parser)
    parser = add_asr_config_argparse_parameters(parser, max_alternatives=True, profanity_filter=True, word_time_offsets=True)
    args = parser.parse_args()
    if not args.list_devices and args.input_file is None:
        parser.error(
            "You have to provide at least one of parameters `--input-file` and `--list-devices` whereas both "
            "parameters are missing."
        )
    if args.play_audio or args.output_device is not None or args.list_devices:
        import riva.client.audio_io
    return args


def main() -> None:
    args = parse_args()
    if args.list_devices:
        riva.client.audio_io.list_output_devices()
        return
    auth = riva.client.Auth(args.ssl_cert, args.use_ssl, args.server, args.metadata)
    asr_service = riva.client.ASRService(auth)
    config = riva.client.StreamingRecognitionConfig(
        config=riva.client.RecognitionConfig(
            language_code=args.language_code,
            max_alternatives=1,
            profanity_filter=args.profanity_filter,
            enable_automatic_punctuation=args.automatic_punctuation,
            verbatim_transcripts=not args.no_verbatim_transcripts,
        ),
        interim_results=True,
    )
    riva.client.add_word_boosting_to_config(config, args.boosted_lm_words, args.boosted_lm_score)
    riva.client.add_endpoint_parameters_to_config(
        config,
        args.start_history,
        args.start_threshold,
        args.stop_history,
        args.stop_history_eou,
        args.stop_threshold,
        args.stop_threshold_eou
    )
    sound_callback = None
    try:
        if args.play_audio or args.output_device is not None:
            wp = riva.client.get_wav_file_parameters(args.input_file)
            sound_callback = riva.client.audio_io.SoundCallBack(
                args.output_device, wp['sampwidth'], wp['nchannels'], wp['framerate'],
            )
            delay_callback = sound_callback
        else:
            delay_callback = riva.client.sleep_audio_length if args.simulate_realtime else None
        with riva.client.AudioChunkFileIterator(
            args.input_file, args.file_streaming_chunk, delay_callback,
        ) as audio_chunk_iterator:
            riva.client.print_streaming(
                responses=asr_service.streaming_response_generator(
                    audio_chunks=audio_chunk_iterator,
                    streaming_config=config,
                ),
                show_intermediate=args.show_intermediate,
                additional_info="confidence" if args.print_confidence else "no",
            )
    finally:
        if sound_callback is not None and sound_callback.opened:
            sound_callback.close()


if __name__ == "__main__":
    main()
