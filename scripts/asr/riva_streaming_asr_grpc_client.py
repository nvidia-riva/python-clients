# Script to stream audio file to Riva and print FINAL transcripts with audio_processed info

import argparse
from pathlib import Path
import grpc
import riva.client
import riva.client.proto.riva_asr_pb2 as riva_asr_pb2
import riva.client.proto.riva_asr_pb2_grpc as riva_asr_pb2_grpc
from riva.client.argparse_utils import add_asr_config_argparse_parameters, add_connection_argparse_parameters


def read_responses(responses):
    try:
        final_transcript = ""
        for response in responses:
            if not response.results:
                continue
            for result in response.results:
                if not result.alternatives:
                    continue
                if result.is_final:
                    final_transcript += result.alternatives[0].transcript
                    print(f"FINAL: {result.audio_processed:.2f} : {result.alternatives[0].transcript}")
                else:
                    print(f"PARTIAL: {result.audio_processed:.2f} : {result.alternatives[0].transcript}")

        # print("Transcript:", final_transcript)

    except grpc.RpcError as error:
        print(error.code(), error.details())
        return


def generate_requests(args):
    print(f"File: {args.input_file}")
    streaming_config = riva_asr_pb2.StreamingRecognitionConfig(
        config=riva_asr_pb2.RecognitionConfig(
            language_code="en-US", max_alternatives=1, profanity_filter=True, enable_automatic_punctuation=True,
        ),
        interim_results=False,
    )

    # First send the config
    yield riva_asr_pb2.StreamingRecognizeRequest(streaming_config=streaming_config)

    # Followed by audio
    try:
        for audio_chunk in riva.client.AudioChunkFileIterator(args.input_file, args.chunk_duration_ms):
            yield riva_asr_pb2.StreamingRecognizeRequest(audio_content=audio_chunk)
    except Exception as e:
        print(e)
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Streaming transcription via Riva AI Services. Uses direct gRPC API",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input-file", required=True, type=Path, help="Name of the WAV file with LINEAR_PCM encoding to transcribe."
    )
    parser.add_argument("--chunk-duration-ms", type=int, default=100, help="Chunk duration in milliseconds.")
    parser.add_argument(
        "--interim-results", default=False, action='store_true', help="Print intermediate transcripts",
    )
    parser = add_connection_argparse_parameters(parser)
    parser = add_asr_config_argparse_parameters(
        parser, max_alternatives=True, profanity_filter=True, word_time_offsets=True
    )
    args = parser.parse_args()
    if args.max_alternatives < 1:
        parser.error("`--max-alternatives` must be greater than or equal to 1")
    return args


def main() -> None:
    args = parse_args()

    # Open channel
    auth = riva.client.Auth(None, use_ssl=args.use_ssl, uri=args.server, metadata_args=args.metadata)

    # Create stub
    riva_stub = riva_asr_pb2_grpc.RivaSpeechRecognitionStub(auth.channel)

    # Get response stream to read transcripts
    read_responses(riva_stub.StreamingRecognize(generate_requests(args)))


if __name__ == "__main__":
    main()
