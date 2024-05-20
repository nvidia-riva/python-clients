# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
import json
from pathlib import Path

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
    parser.add_argument(
        "--input-file",
        required=True,
        type=Path,
        help="A path to a local file to stream or a JSONL file containing list of files. JSONL file should contain JSON entry on each line, for example: {'audio_filepath': 'audio.wav'} ",
    )
    parser.add_argument("--list-devices", action="store_true", help="List output devices indices")
    parser.add_argument(
        "--interim-results", default=False, action='store_true', help="Print intermediate transcripts",
    )
    parser.add_argument(
        "--output-device",
        type=int,
        default=None,
        help="Output audio device to use for playing audio simultaneously with transcribing. If this parameter is "
        "provided, then you do not have to `--play-audio` option.",
    )
    parser.add_argument(
        "--play-audio",
        action="store_true",
        help="Whether to play input audio simultaneously with transcribing. If `--output-device` is not provided, "
        "then the default output audio device will be used.",
    )
    parser.add_argument("--chunk-duration-ms", type=int, default=100, help="Chunk duration in milliseconds.")
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
    parser = add_asr_config_argparse_parameters(
        parser, max_alternatives=True, profanity_filter=True, word_time_offsets=True
    )
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
    input_files = []
    if args.input_file.suffix == ".json":
        with open(args.input_file) as f:
            lines = f.read().splitlines()
            for line in lines:
                data = json.loads(line)
                if "audio_filepath" in data:
                    input_files.append(data["audio_filepath"])
    else:
        input_files = [args.input_file]

    auth = riva.client.Auth(args.ssl_cert, args.use_ssl, args.server, args.metadata)
    asr_service = riva.client.ASRService(auth)
    config = riva.client.StreamingRecognitionConfig(
        config=riva.client.RecognitionConfig(
            language_code=args.language_code,
            max_alternatives=args.max_alternatives,
            profanity_filter=args.profanity_filter,
            enable_automatic_punctuation=args.automatic_punctuation,
            verbatim_transcripts=args.verbatim_transcripts,
            enable_word_time_offsets=args.word_time_offsets,
            model=args.model_name,
        ),
        interim_results=args.interim_results,
    )
    riva.client.add_word_boosting_to_config(config, args.boosted_words_file, args.boosted_words_score)
    sound_callback = None

    for file in input_files:
        try:
            if args.play_audio or args.output_device is not None:
                wp = riva.client.get_wav_file_parameters(file)
                sound_callback = riva.client.audio_io.SoundCallBack(
                    args.output_device, wp['sampwidth'], wp['nchannels'], wp['framerate'],
                )
                delay_callback = sound_callback
            else:
                delay_callback = riva.client.sleep_audio_length if args.simulate_realtime else None

            with riva.client.AudioChunkFileIterator(
                file, args.chunk_duration_ms, delay_callback,
            ) as audio_chunk_iterator:
                riva.client.print_streaming(
                    responses=asr_service.streaming_response_generator(
                        audio_chunks=audio_chunk_iterator, streaming_config=config,
                    ),
                    input_file=file,
                    show_intermediate=args.interim_results,
                    additional_info="confidence" if args.print_confidence else "no",
                )
        finally:
            if sound_callback is not None and sound_callback.opened:
                sound_callback.close()


if __name__ == "__main__":
    main()
