import argparse
import os
import wave
from typing import Iterator

import grpc

import riva.client
import riva.client.proto.riva_asr_pb2 as riva_asr_pb2
import riva.client.proto.riva_nmt_pb2 as riva_nmt_pb2
from riva.client.argparse_utils import add_connection_argparse_parameters


def parse_arguments():
    parser = argparse.ArgumentParser(description='Riva Speech-to-Speech Translation Client')
    parser.add_argument('--audio-file', required=True, help='Path to the input audio file (WAV format)')
    parser.add_argument('--source-language', default='en-US', help='Source language code (default: en-US)')
    parser.add_argument('--target-language', default='es-ES', help='Target language code (default: es-ES)')
    parser.add_argument('--voice', default='', help='Voice name (optional)')
    parser.add_argument('--sample-rate-hz', type=int, default=16000, help='Sample rate (default: 16000)')
    parser.add_argument('--list-models', action='store_true', help='List available models')
    parser.add_argument('--output-file', default='output.wav', help='Output file (optional)')
    parser = add_connection_argparse_parameters(parser)

    return parser.parse_args()


def main():
    args = parse_arguments()

    # Validate input file
    if not os.path.exists(args.audio_file):
        raise FileNotFoundError(f"Input audio file not found: {args.audio_file}")

    auth = riva.client.Auth(args.ssl_cert, args.use_ssl, args.server, args.metadata)
    nmt_client = riva.client.NeuralMachineTranslationClient(auth)

    if args.list_models:
        response = nmt_client.get_config()
        print(response)
        return

    try:
        print(f"Translating speech from {args.source_language} to {args.target_language}")
        print(f"Using audio file: {args.audio_file}")
        print(f"Server address: {args.server}")

        # Create ASR config
        asr_config = riva_asr_pb2.StreamingRecognitionConfig(
            config=riva_asr_pb2.RecognitionConfig(
                language_code=args.source_language, max_alternatives=1, enable_automatic_punctuation=True
            ),
            interim_results=True,
        )

        # Create translation config
        translation_config = riva_nmt_pb2.TranslationConfig(
            source_language_code=args.source_language, target_language_code=args.target_language,
        )

        # Create synthesis config
        tts_config = riva_nmt_pb2.SynthesizeSpeechConfig(
            encoding=riva.client.AudioEncoding.LINEAR_PCM,
            language_code=args.target_language,
            voice_name=args.voice,
            sample_rate_hz=args.sample_rate_hz,
        )

        # Create streaming config
        streaming_config = riva_nmt_pb2.StreamingTranslateSpeechToSpeechConfig(
            asr_config=asr_config, translation_config=translation_config, tts_config=tts_config
        )

        responses = nmt_client.streaming_s2s_response_generator(
            audio_chunks=riva.client.AudioChunkFileIterator(args.audio_file, 100), streaming_config=streaming_config
        )

        try:
            output_file = None
            for response in responses:
                if len(response.speech.audio) > 0 and output_file is None:
                    output_file = wave.open(str(args.output_file), 'wb')
                    output_file.setnchannels(1)
                    output_file.setsampwidth(2)
                    output_file.setframerate(args.sample_rate_hz)
                output_file.writeframesraw(response.speech.audio)

        finally:
            if output_file is not None:
                print(f"Written {output_file.getnframes()} samples to {args.output_file}")
                output_file.close()

    except Exception as e:
        print(f"Error during translation: {e}")


if __name__ == "__main__":
    main()
