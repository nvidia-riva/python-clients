# Copyright (c) 2020, NVIDIA CORPORATION. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#  * Neither the name of NVIDIA CORPORATION nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
# OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import argparse

import riva_api
from riva_api.argparse_utils import add_asr_config_argparse_parameters, add_connection_argparse_parameters

import riva_api.audio_io


def parse_args() -> argparse.Namespace:
    default_device_info = riva_api.audio_io.get_default_input_device_info()
    default_device_index = None if default_device_info is None else default_device_info['index']
    parser = argparse.ArgumentParser(
        description="Streaming transcription from microphone via Riva AI Services",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input-device", type=int, default=default_device_index, help="Input device to use.")
    parser.add_argument("--list-devices", action="store_true", help="List input devices indices.")
    parser = add_asr_config_argparse_parameters(parser)
    parser = add_connection_argparse_parameters(parser)
    parser.add_argument(
        "--sample-rate-hz",
        type=int,
        help="Frame for input device. If not provided, then default value is used.",
        default=16000,
    )
    parser.add_argument("--file-streaming-chunk", type=int, default=1600)
    args = parser.parse_args()
    return args


def main() -> None:
    args = parse_args()
    if args.list_devices:
        riva_api.audio_io.list_input_devices()
        return
    auth = riva_api.Auth(args.ssl_cert, args.use_ssl, args.server)
    asr_service = riva_api.ASRService(auth)
    config = riva_api.StreamingRecognitionConfig(
        config=riva_api.RecognitionConfig(
            encoding=riva_api.AudioEncoding.LINEAR_PCM,
            language_code=args.language_code,
            max_alternatives=1,
            enable_automatic_punctuation=args.automatic_punctuation,
            verbatim_transcripts=not args.no_verbatim_transcripts,
            sample_rate_hertz=args.sample_rate_hz,
            audio_channel_count=1,
        ),
        interim_results=True,
    )
    riva_api.add_word_boosting_to_config(config, args.boosted_lm_words, args.boosted_lm_score)
    with riva_api.audio_io.MicrophoneStream(
        args.sample_rate_hz,
        args.file_streaming_chunk,
        device=args.input_device,
    ) as audio_chunk_iterator:
        riva_api.print_streaming(
            response_generator=asr_service.streaming_response_generator(
                audio_chunks=audio_chunk_iterator,
                streaming_config=config,
            ),
            show_intermediate=True,
        )


if __name__ == '__main__':
    main()
