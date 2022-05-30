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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Streaming transcription of a file via Riva AI Services. Streaming means that audio is sent to "
        "server in small chunks and transcripts are returned audio fragments as soon as these transcripts are ready. "
        "You may play transcribed audio simultaneously with transcribing by setting one of parameters "
        "`--play-audio` or `--output-device`.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input-file", help="A path to local file to stream.")
    parser.add_argument("--list-devices", action="store_true", help="list output devices indices")
    parser.add_argument(
        "--show-intermediate", action="store_true", help="Show intermediate transcripts as they are available."
    )
    parser.add_argument("--output-device", type=int, default=None, help="Output audio device to use.")
    parser.add_argument(
        "--play-audio",
        action="store_true",
        help="Whether to play input audio simultaneously with transcribing. If `--output-device` is not provided, "
        "then the default output audio device will be used.",
    )
    parser.add_argument(
        "--file-streaming-chunk", type=int, default=1600, help="Number of frames in one chunk sent to server."
    )
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
    parser = add_asr_config_argparse_parameters(parser)
    args = parser.parse_args()
    if not args.list_devices and args.input_file is None:
        parser.error(
            "You have to provide at least one of parameters `--input-file` and `--list-devices` whereas both "
            "parameters are missing."
        )
    if args.play_audio or args.output_device is not None or args.list_devices:
        import riva_api.audio_io
    return args


def main() -> None:
    args = parse_args()
    if args.list_devices:
        riva_api.audio_io.list_output_devices()
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
        ),
        interim_results=True,
    )
    riva_api.add_audio_file_specs_to_config(config, args.input_file)
    riva_api.add_word_boosting_to_config(config, args.boosted_lm_words, args.boosted_lm_score)
    sound_callback = None
    try:
        if args.play_audio or args.output_device is not None:
            wp = riva_api.get_wav_file_parameters(args.input_file)
            sound_callback = riva_api.audio_io.SoundCallBack(
                args.output_device, wp['sampwidth'], wp['nchannels'], wp['framerate'],
            )
            delay_callback = sound_callback
        else:
            delay_callback = riva_api.sleep_audio_length if args.simulate_realtime else None
        with riva_api.AudioChunkFileIterator(
            args.input_file, args.file_streaming_chunk, delay_callback,
        ) as audio_chunk_iterator:
            riva_api.print_streaming(
                response_generator=asr_service.streaming_response_generator(
                    audio_chunks=audio_chunk_iterator,
                    streaming_config=config,
                ),
                show_intermediate=args.show_intermediate,
                additional_info="confidence" if args.print_confidence else "no",
            )
    finally:
        if sound_callback is not None and sound_callback.opened:
            sound_callback.close()


if __name__ == "__main__":
    main()
