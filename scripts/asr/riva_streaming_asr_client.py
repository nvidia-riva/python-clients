import argparse
import os
import queue
import time
from threading import Thread

import riva_api
from riva_api.asr import get_wav_file_parameters
from riva_api.argparse_utils import add_asr_config_argparse_parameters, add_connection_argparse_parameters


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Streaming transcription via Riva AI Services. Unlike `scripts/asr/transcribe_file.py` script "
        "this script allows to perform transcription several times on the same audio if `--num-iterations` is "
        "greater than 1. If you `--num-clients` is greater than 1, then a file will be transcribed independently "
        "in several threads. Unlike other ASR scripts, this script does not print output but saves it in files "
        "with names in format `output_<thread_num>.txt`.",
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
    parser = add_asr_config_argparse_parameters(parser, max_alternatives=True, word_time_offsets=True)
    args = parser.parse_args()
    if args.max_alternatives < 1:
        parser.error("`--max-alternatives` must be greater than or equal to 1")
    return args


def streaming_transcription_worker(
    args: argparse.Namespace, output_file: os.PathLike, thread_i: int, exception_queue: queue.Queue
) -> None:
    try:
        auth = riva_api.Auth(args.ssl_cert, args.use_ssl, args.server)
        asr_service = riva_api.ASRService(auth)
        config = riva_api.StreamingRecognitionConfig(
            config=riva_api.RecognitionConfig(
                encoding=riva_api.AudioEncoding.LINEAR_PCM,
                language_code=args.language_code,
                max_alternatives=args.max_alternatives,
                enable_automatic_punctuation=args.automatic_punctuation,
                verbatim_transcripts=not args.no_verbatim_transcripts,
                enable_word_time_offsets=args.word_time_offsets,
            ),
            interim_results=True,
        )
        riva_api.add_audio_file_specs_to_config(config, args.input_file)
        riva_api.add_word_boosting_to_config(config, args.boosted_lm_words, args.boosted_lm_score)
        for _ in range(args.num_iterations):
            with riva_api.AudioChunkFileIterator(
                args.input_file,
                args.file_streaming_chunk,
                delay_callback=riva_api.sleep_audio_length if args.simulate_realtime else None,
            ) as audio_chunk_iterator:
                riva_api.print_streaming(
                    response_generator=asr_service.streaming_response_generator(
                        audio_chunks=audio_chunk_iterator,
                        streaming_config=config,
                    ),
                    output_file=output_file,
                    additional_info='time',
                    file_mode='a',
                    word_time_offsets=args.word_time_offsets,
                )
    except BaseException as e:
        exception_queue.put((e, thread_i))
        raise


def main() -> None:
    args = parse_args()
    print("Number of clients:", args.num_clients)
    print("Number of iteration:", args.num_iterations)
    print("Input file:", args.input_file)
    wav_parameters = get_wav_file_parameters(args.input_file)
    print(f"File duration: {wav_parameters['duration']:.2f}s")
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
