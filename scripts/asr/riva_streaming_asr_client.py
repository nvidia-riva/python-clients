import argparse
import os
from threading import Thread

import riva_api
from riva_api.asr import get_wav_file_parameters
from riva_api.argparse_utils import add_asr_config_argparse_parameters, add_connection_argparse_parameters


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Streaming transcription via Riva AI Services",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--num-clients", default=1, type=int, help="Number of client threads")
    parser.add_argument("--num-iterations", default=1, type=int, help="Number of iterations over the file")
    parser.add_argument(
        "--input-file", required=True, type=str, help="Name of the WAV file with LINEAR_PCM encoding to transcribe"
    )
    parser.add_argument("--simulate-realtime", action='store_true', help="Option to simulate realtime transcription")
    parser.add_argument("--file-streaming-chunk", type=int, default=1600)
    parser = add_connection_argparse_parameters(parser)
    parser = add_asr_config_argparse_parameters(parser, max_alternatives=True, word_time_offsets=True)
    args = parser.parse_args()
    if args.max_alternatives < 1:
        parser.error("`--max-alternatives` must be greater than or equal to 1")
    return args


def print_streaming(args: argparse.Namespace, output_file: os.PathLike) -> None:
    auth = riva_api.Auth(args.ssl_cert, args.use_ssl, args.riva_uri)
    asr_service = riva_api.ASRService(auth)
    config = riva_api.StreamingRecognitionConfig(
        config=riva_api.RecognitionConfig(
            encoding=riva_api.AudioEncoding.LINEAR_PCM,
            language_code=args.language_code,
            max_alternatives=1,
            enable_automatic_punctuation=args.automatic_punctuation,
            verbatim_transcripts=not args.no_verbatim_transcripts,
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
            )


def main() -> None:
    args = get_args()

    print("Number of clients:", args.num_clients)
    print("Number of iteration:", args.num_iterations)
    print("Input file:", args.input_file)
    wav_parameters = get_wav_file_parameters(args.input_file)
    print(f"File duration: {wav_parameters['duration']:.2f}s")
    threads = []
    for i in range(args.num_clients):
        t = Thread(target=print_streaming, args=[args, f"output_{i:d}.txt"])
        t.start()
        threads.append(t)
    for i, t in enumerate(threads):
        t.join()
    print(str(args.num_clients), "threads done, output written to output_<thread_id>.txt")


if __name__ == "__main__":
    main()
