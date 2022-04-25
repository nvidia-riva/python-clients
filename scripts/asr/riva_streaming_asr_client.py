import argparse
from threading import Thread

from riva_api import ASR_Client, AudioEncoding, Auth, RecognitionConfig, StreamingRecognitionConfig, print_streaming
from riva_api.asr import get_wav_file_parameters
from riva_api.script_utils import add_asr_config_argparse_parameters, add_connection_argparse_parameters


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Streaming transcription via Riva AI Services")
    parser.add_argument("--num-clients", default=1, type=int, help="Number of client threads")
    parser.add_argument("--num-iterations", default=1, type=int, help="Number of iterations over the file")
    parser.add_argument(
        "--input-file", required=True, type=str, help="Name of the WAV file with LINEAR_PCM encoding to transcribe"
    )
    parser.add_argument(
        "--simulate-realtime", default=False, action='store_true', help="Option to simulate realtime transcription"
    )
    parser.add_argument("--file-streaming-chunk", type=int, default=1600)
    parser = add_connection_argparse_parameters(parser)
    parser = add_asr_config_argparse_parameters(parser, max_alternatives=True, word_time_offsets=True)
    args = parser.parse_args()
    if args.max_alternatives < 1:
        parser.error("`--max-alternatives` must be greater than or equal to 1")
    return args


def main() -> None:
    parser = get_args()

    print("Number of clients:", parser.num_clients)
    print("Number of iteration:", parser.num_iterations)
    print("Input file:", parser.input_file)

    threads = []
    output_filenames = []
    for i in range(parser.num_clients):
        wav_parameters = get_wav_file_parameters(parser.input_file)
        if i == 0:
            print(f"File duration: {wav_parameters['duration']:.2f}s")
        output_filenames.append(f"output_{i:d}.txt")
        auth = Auth(parser.ssl_cert, parser.use_ssl, parser.riva_uri)
        asr_client = ASR_Client(auth)
        config = StreamingRecognitionConfig(
            config=RecognitionConfig(
                encoding=AudioEncoding.LINEAR_PCM,
                language_code=parser.language_code,
                max_alternatives=parser.max_alternatives,
                enable_automatic_punctuation=parser.automatic_punctuation,
                enable_word_time_offsets=parser.word_time_offsets,
                verbatim_transcripts=not parser.no_verbatim_transcripts,
            ),
            interim_results=True,
        )
        t = Thread(
            target=print_streaming,
            kwargs={
                "generator": asr_client.streaming_recognize_file_generator(
                    input_file=parser.input_file,
                    streaming_config=config,
                    num_iterations=parser.num_iterations,
                    simulate_realtime=parser.simulate_realtime,
                    boosted_lm_score=parser.boosted_lm_score,
                    boosted_lm_words=parser.boosted_lm_words,
                    file_streaming_chunk=parser.file_streaming_chunk,
                ),
                "output_file": output_filenames[-1],
                "mode": "show_time",
            },
        )
        t.start()
        threads.append(t)

    for i, t in enumerate(threads):
        t.join()

    print(str(parser.num_clients), "threads done, output written to output_<thread_id>.txt")


if __name__ == "__main__":
    main()
