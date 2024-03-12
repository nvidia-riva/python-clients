# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
import time
import wave
from pathlib import Path

import riva.client
from riva.client.argparse_utils import add_connection_argparse_parameters


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A speech synthesis via Riva AI Services. You HAVE TO provide at least one of arguments "
        "`--output`, `--play-audio`, `--list-devices`, `--output-device`.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--voice",
        help="A voice name to use. If this parameter is missing, then the server will try a first available model "
        "based on parameter `--language-code`.",
    )
    parser.add_argument("--text", type=str, required=True, help="Text input to synthesize.")
    parser.add_argument(
        "--audio_prompt_file",
        type=Path,
        help="An input audio prompt (.wav) file for zero shot model. This is required to do zero shot inferencing.")
    parser.add_argument("-o", "--output", type=Path, help="Output file .wav file to write synthesized audio.")
    parser.add_argument("--quality", type=int, help="Number of times decoder should be run on the output audio. A higher number improves quality of the produced output but introduces latencies.")
    parser.add_argument(
        "--play-audio",
        action="store_true",
        help="Whether to play input audio simultaneously with transcribing. If `--output-device` is not provided, "
        "then the default output audio device will be used.",
    )
    parser.add_argument("--list-devices", action="store_true", help="List output audio devices indices.")
    parser.add_argument("--output-device", type=int, help="Output device to use.")
    parser.add_argument("--language-code", default='en-US', help="A language of input text.")
    parser.add_argument(
        "--sample-rate-hz", type=int, default=44100, help="Number of audio frames per second in synthesized audio."
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="If this option is set, then streaming synthesis is applied. Streaming means that audio is yielded "
        "as it gets ready. If `--stream` is not set, then a synthesized audio is returned in 1 response only when "
        "all text is processed.",
    )
    parser = add_connection_argparse_parameters(parser)
    args = parser.parse_args()
    if args.output is None and not args.play_audio and args.output_device is None and not args.list_devices:
        parser.error(
            f"You have to provide at least one of arguments: `--play-audio`, `--output-device`, `--output`, "
            f"`--list-devices`."
        )
    if args.output is not None:
        args.output = args.output.expanduser()
    if args.list_devices or args.output_device or args.play_audio:
        import riva.client.audio_io
    return args


def main() -> None:
    args = parse_args()
    if args.list_devices:
        riva.client.audio_io.list_output_devices()
        return
    auth = riva.client.Auth(args.ssl_cert, args.use_ssl, args.server, args.metadata)
    service = riva.client.SpeechSynthesisService(auth)
    nchannels = 1
    sampwidth = 2
    sound_stream, out_f = None, None
    try:
        if args.output_device is not None or args.play_audio:
            sound_stream = riva.client.audio_io.SoundCallBack(
                args.output_device, nchannels=nchannels, sampwidth=sampwidth, framerate=args.sample_rate_hz
            )
        if args.output is not None:
            out_f = wave.open(str(args.output), 'wb')
            out_f.setnchannels(nchannels)
            out_f.setsampwidth(sampwidth)
            out_f.setframerate(args.sample_rate_hz)

        print("Generating audio for request...")
        start = time.time()
        if args.stream:
            responses = service.synthesize_online(
                args.text, args.voice, args.language_code, sample_rate_hz=args.sample_rate_hz,
                audio_prompt_file=args.audio_prompt_file, quality=20 if args.quality is None else args.quality
            )
            first = True
            for resp in responses:
                stop = time.time()
                if first:
                    print(f"Time to first audio: {(stop - start):.3f}s")
                    first = False
                if sound_stream is not None:
                    sound_stream(resp.audio)
                if out_f is not None:
                    out_f.writeframesraw(resp.audio)
        else:
            resp = service.synthesize(
                args.text, args.voice, args.language_code, sample_rate_hz=args.sample_rate_hz,
                audio_prompt_file=args.audio_prompt_file, quality=20 if args.quality is None else args.quality
            )
            stop = time.time()
            print(f"Time spent: {(stop - start):.3f}s")
            if sound_stream is not None:
                sound_stream(resp.audio)
            if out_f is not None:
                out_f.writeframesraw(resp.audio)
    finally:
        if out_f is not None:
            out_f.close()
        if sound_stream is not None:
            sound_stream.close()


if __name__ == '__main__':
    main()
