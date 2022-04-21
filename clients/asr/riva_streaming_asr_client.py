import argparse
from threading import Thread

import riva_api.proto.riva_asr_pb2 as rasr
import riva_api.proto.riva_audio_pb2 as ra
from riva_api.asr import ASR_Client, get_wav_file_frames_rate_duration
from riva_api.auth import Auth


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
    parser.add_argument(
        "--word-time-offsets", default=False, action='store_true', help="Option to output word timestamps"
    )
    parser.add_argument(
        "--max-alternatives",
        default=1,
        type=int,
        help="Maximum number of alternative transcripts to return (up to limit configured on server)",
    )
    parser.add_argument(
        "--automatic-punctuation",
        default=False,
        action='store_true',
        help="Flag that controls if transcript should be automatically punctuated",
    )
    parser.add_argument("--riva-uri", default="localhost:50051", type=str, help="URI to access Riva server")
    parser.add_argument(
        "--no-verbatim-transcripts",
        default=False,
        action='store_true',
        help="If specified, text inverse normalization will be applied",
    )
    parser.add_argument("--language-code", default="en-US", type=str, help="Language code of the model to be used")
    parser.add_argument("--boosted_lm_words", type=str, action='append', help="Words to boost when decoding")
    parser.add_argument(
        "--boosted_lm_score", type=float, default=4.0, help="Value by which to boost words when decoding"
    )

    parser.add_argument("--ssl_cert", type=str, help="Path to SSL client certificatates file")
    parser.add_argument(
        "--use_ssl", default=False, action='store_true', help="Boolean to control if SSL/TLS encryption should be used"
    )
    parser.add_argument("--file_streaming_chunk", type=int, default=1600)
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
        _, _, duration = get_wav_file_frames_rate_duration(parser.input_file)
        if i == 0:
            print(f"File duration: {duration:.2f}s")
        output_filenames.append(f"output_{i:d}.txt")
        auth = Auth(parser.ssl_cert, parser.use_ssl, parser.riva_uri)
        asr_client = ASR_Client(auth)
        config = rasr.StreamingRecognitionConfig(
            config=rasr.RecognitionConfig(
                encoding=ra.AudioEncoding.LINEAR_PCM,
                language_code=parser.language_code,
                max_alternatives=parser.max_alternatives,
                enable_automatic_punctuation=parser.automatic_punctuation,
                enable_word_time_offsets=parser.word_time_offsets,
                verbatim_transcripts=not parser.no_verbatim_transcripts,
            ),
            interim_results=True,
        )
        t = Thread(
            target=asr_client.streaming_recognize_file_print,
            kwargs={
                "output_file": output_filenames[-1],
                "streaming_config": config,
                "input_file": parser.input_file,
                "num_iterations": parser.num_iterations,
                "simulate_realtime": parser.simulate_realtime,
                "boosted_lm_words": parser.boosted_lm_words,
                "boosted_lm_score": parser.boosted_lm_score,
                "file_streaming_chunk": parser.file_streaming_chunk,
            },
        )
        t.start()
        threads.append(t)

    for i, t in enumerate(threads):
        t.join()

    print(str(parser.num_clients), "threads done, output written to output_<thread_id>.txt")


if __name__ == "__main__":
    main()
