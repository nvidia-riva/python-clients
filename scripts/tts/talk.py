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

#!/usr/bin/env python

import argparse
import time
import wave
from pathlib import Path

import riva_api
from riva_api.argparse_utils import add_connection_argparse_parameters
from riva_api.audio_io import SoundCallBack, list_output_devices


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Streaming transcription via Riva AI Services",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--voice", type=str, help="voice name to use", default="English-US-Female-1")
    parser.add_argument("-o", "--output", default=None, type=Path, help="Output file to write last utterance")
    parser.add_argument("--list-devices", action="store_true", help="list output devices indices")
    parser.add_argument("--output-device", type=int, help="Output device to use")
    parser.add_argument("--language-code", default='en-US')
    parser.add_argument("--sample-rate-hz", type=int, default=44100)
    parser.add_argument("--stream", action="store_true")
    parser = add_connection_argparse_parameters(parser)
    args = parser.parse_args()
    if args.output is not None:
        args.output = args.output.expanduser()
    return args


def main() -> None:
    args = get_args()
    if args.list_devices:
        list_output_devices()
        return
    auth = riva_api.Auth(args.ssl_cert, args.use_ssl, args.server)
    service = riva_api.SpeechSynthesisService(auth)
    nchannels = 1
    sampwidth = 2
    with SoundCallBack(
        args.output_device, nchannels=nchannels, sampwidth=sampwidth, framerate=args.sample_rate_hz
    ) as sound_stream:
        try:
            if args.output is not None:
                out_f = wave.open(str(args.output), 'wb')
                out_f.setnchannels(nchannels)
                out_f.setsampwidth(sampwidth)
                out_f.setframerate(args.sample_rate_hz)
            else:
                out_f = None
            while True:
                text = input("Speak: ")
                print("Generating audio for request...")
                print(f"  > '{text}': ", end='')
                start = time.time()
                if args.stream:
                    responses = service.synthesize_online(
                        text, args.voice, args.language_code, sample_rate_hz=args.sample_rate_hz
                    )
                    first = True
                    for resp in responses:
                        stop = time.time()
                        if first:
                            print(f"Time to first audio: {(stop - start):.3f}s")
                            first = False
                        sound_stream(resp.audio)
                        if out_f is not None:
                            out_f.writeframesraw(resp.audio)
                else:
                    resp = service.synthesize(text, args.voice, args.language_code, sample_rate_hz=args.sample_rate_hz)
                    stop = time.time()
                    print(f"Time spent: {(stop - start):.3f}s")
                    sound_stream(resp.audio)
                    if out_f is not None:
                        out_f.writeframesraw(resp.audio)
        finally:
            if args.output is not None:
                out_f.close()


if __name__ == '__main__':
    main()
