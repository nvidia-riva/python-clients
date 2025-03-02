# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
import os
import queue
import time
from pathlib import Path
from threading import Thread
from typing import Union

import riva.client
from riva.client.asr import get_wav_file_parameters
from riva.client.argparse_utils import add_asr_config_argparse_parameters, add_connection_argparse_parameters


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Streaming transcription via Riva AI Services. Unlike `scripts/asr/transcribe_file.py` script, "
        "this script can perform transcription several times on same audio if `--num-iterations` is "
        "greater than 1. If `--num-clients` is greater than 1, then a file will be transcribed independently "
        "in several threads. Unlike other ASR scripts, this script does not print output but saves it in files "
        "which names follow a format `output_<thread_num>.txt`.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--num-clients", default=1, type=int, help="Number of client threads.")
    parser.add_argument("--num-iterations", default=1, type=int, help="Number of iterations over the file.")
    parser.add_argument(
        "--input-file", required=True, type=str, help="Name of the WAV file with LINEAR_PCM encoding to transcribe."
    )
    parser.add_argument(
        "--simulate-realtime",
        action='store_true',
        help="Option to simulate realtime transcription. Audio fragments are sent to a server at a pace that mimics "
        "normal speech.",
    )
    parser.add_argument(
        "--file-streaming-chunk", type=int, default=1600, help="Number of frames in one chunk sent to server."
    )
    parser = add_connection_argparse_parameters(parser)
    parser = add_asr_config_argparse_parameters(parser, max_alternatives=True, profanity_filter=True, word_time_offsets=True)
    args = parser.parse_args()
    if args.max_alternatives < 1:
        parser.error("`--max-alternatives` must be greater than or equal to 1")
    return args


def streaming_transcription_worker(
    args: argparse.Namespace, output_file: Union[str, os.PathLike], thread_i: int, exception_queue: queue.Queue
) -> None:
    output_file = Path(output_file).expanduser()
    try:
        auth = riva.client.Auth(args.ssl_cert, args.use_ssl, args.server, args.metadata)
        asr_service = riva.client.ASRService(auth)
        config = riva.client.StreamingRecognitionConfig(
            config=riva.client.RecognitionConfig(
                language_code=args.language_code,
                model=args.model_name,
                max_alternatives=args.max_alternatives,
                profanity_filter=args.profanity_filter,
                enable_automatic_punctuation=args.automatic_punctuation,
                verbatim_transcripts=not args.no_verbatim_transcripts,
                enable_word_time_offsets=args.word_time_offsets or args.speaker_diarization,
            ),
            interim_results=True,
        )
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
        riva.client.add_word_boosting_to_config(config, args.boosted_lm_words, args.boosted_lm_score)
        riva.client.add_speaker_diarization_to_config(config, args.speaker_diarization, args.diarization_max_speakers)
        for _ in range(args.num_iterations):
            with riva.client.AudioChunkFileIterator(
                args.input_file,
                args.file_streaming_chunk,
                delay_callback=riva.client.sleep_audio_length if args.simulate_realtime else None,
            ) as audio_chunk_iterator:
                riva.client.print_streaming(
                    responses=asr_service.streaming_response_generator(
                        audio_chunks=audio_chunk_iterator,
                        streaming_config=config,
                    ),
                    output_file=output_file,
                    additional_info='time',
                    file_mode='a',
                    word_time_offsets=args.word_time_offsets or args.speaker_diarization,
                    speaker_diarization=args.speaker_diarization,
                )
    except BaseException as e:
        exception_queue.put((e, thread_i))
        raise


def main() -> None:
    args = parse_args()
    print("Number of clients:", args.num_clients)
    print("Number of iteration:", args.num_iterations)
    print("Input file:", args.input_file)
    threads = []
    exception_queue = queue.Queue()
    for i in range(args.num_clients):
        t = Thread(target=streaming_transcription_worker, args=[args, f"output_{i:d}.txt", i, exception_queue])
        t.start()
        threads.append(t)
    while True:
        try:
            exc, thread_i = exception_queue.get(block=False)
        except queue.Empty:
            pass
        else:
            raise RuntimeError(f"A thread with index {thread_i} failed with error:\n{exc}")
        all_dead = True
        for t in threads:
            t.join(0.0)
            if t.is_alive():
                all_dead = False
                break
        if all_dead:
            break
        time.sleep(0.05)
    print(str(args.num_clients), "threads done, output written to output_<thread_id>.txt")


if __name__ == "__main__":
    main()
