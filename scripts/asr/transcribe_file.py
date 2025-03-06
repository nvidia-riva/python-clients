# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse

import os
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
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input-file", help="A path to a local file to stream.")
    group.add_argument("--list-models", action="store_true", help="List available models.")
    group.add_argument("--list-devices", action="store_true", help="List output devices indices")

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
        "--print-confidence", action="store_true", help="Whether to print stability and confidence of transcript. If `--word-time-offsets` or `--speaker-diarization` is set, then confidence is not printed."
    )
    parser = add_connection_argparse_parameters(parser)
    parser = add_asr_config_argparse_parameters(parser, max_alternatives=True, profanity_filter=True, word_time_offsets=True)
    args = parser.parse_args()
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

    if args.list_models:
        asr_models = dict()
        config_response = asr_service.stub.GetRivaSpeechRecognitionConfig(riva.client.proto.riva_asr_pb2.RivaSpeechRecognitionConfigRequest())
        for model_config in config_response.model_config:
            if model_config.parameters["type"] == "online":
                language_code = model_config.parameters['language_code']
                model = {"model": [model_config.model_name]}
                if language_code in asr_models:
                    asr_models[language_code].append(model)
                else:
                    asr_models[language_code] = [model]

        print("Available ASR models")
        asr_models = dict(sorted(asr_models.items()))
        print(asr_models)
        return

    if not os.path.isfile(args.input_file):
        print(f"Invalid input file path: {args.input_file}")
        return

    config = riva.client.StreamingRecognitionConfig(
        config=riva.client.RecognitionConfig(
            language_code=args.language_code,
            model=args.model_name,
            max_alternatives=1,
            profanity_filter=args.profanity_filter,
            enable_automatic_punctuation=args.automatic_punctuation,
            verbatim_transcripts=not args.no_verbatim_transcripts,
            enable_word_time_offsets=args.word_time_offsets or args.speaker_diarization,
        ),
        interim_results=True,
    )
    riva.client.add_word_boosting_to_config(config, args.boosted_lm_words, args.boosted_lm_score)
    riva.client.add_speaker_diarization_to_config(config, args.speaker_diarization, args.diarization_max_speakers)
    riva.client.add_endpoint_parameters_to_config(
        config,
        args.start_history,
        args.start_threshold,
        args.stop_history,
        args.stop_history_eou,
        args.stop_threshold,
        args.stop_threshold_eou
    )
    riva.client.add_custom_configuration_to_config(
        config,
        args.custom_configuration
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
                additional_info="time" if (args.word_time_offsets or args.speaker_diarization) else ("confidence" if args.print_confidence else "no"),
                word_time_offsets=args.word_time_offsets or args.speaker_diarization,
                speaker_diarization=args.speaker_diarization,
            )
    finally:
        if sound_callback is not None and sound_callback.opened:
            sound_callback.close()


if __name__ == "__main__":
    main()
