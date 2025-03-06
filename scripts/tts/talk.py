# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
import time
import wave
import json
from pathlib import Path

import riva.client
from riva.client.argparse_utils import add_connection_argparse_parameters
from riva.client.proto.riva_audio_pb2 import AudioEncoding

def read_file_to_dict(file_path):
    result_dict = {}
    with open(file_path, 'r') as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            try:
                key, value = line.split('  ', 1)  # Split by double space
                result_dict[str(key.strip())] = str(value.strip())
            except ValueError:
                print(f"Warning: Malformed line {line}")
                continue
    if not result_dict:
        raise ValueError("Error: No valid entries found in the file.")
    return result_dict

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Speech synthesis via Riva AI Services",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", type=str, help="Text input to synthesize.")
    group.add_argument("--list-devices", action="store_true", help="List output audio devices indices.")
    group.add_argument("--list-voices", action="store_true", help="List available voices.")
    parser.add_argument(
        "--voice",
        help="A voice name to use. If this parameter is missing, then the server will try a first available model "
        "based on parameter `--language-code`.",
    )
    parser.add_argument(
        "--audio_prompt_file",
        type=Path,
        help="An input audio prompt (.wav) file for zero shot model. This is required to do zero shot inferencing.")
    parser.add_argument("-o", "--output", type=Path, default="output.wav", help="Output file .wav file to write synthesized audio.")
    parser.add_argument("--quality", type=int, help="Number of times decoder should be run on the output audio. A higher number improves quality of the produced output but introduces latencies.")
    parser.add_argument(
        "--play-audio",
        action="store_true",
        help="Whether to play input audio simultaneously with transcribing. If `--output-device` is not provided, "
        "then the default output audio device will be used.",
    )
    parser.add_argument("--output-device", type=int, help="Output device to use.")
    parser.add_argument("--language-code", default='en-US', help="A language of input text.")
    parser.add_argument(
        "--sample-rate-hz", type=int, default=44100, help="Number of audio frames per second in synthesized audio."
    )
    parser.add_argument("--encoding", default="LINEAR_PCM", choices={"LINEAR_PCM", "OGGOPUS"}, help="Output audio encoding.")
    parser.add_argument("--custom-dictionary", type=str, help="A file path to a user dictionary with key-value pairs separated by double spaces.")
    parser.add_argument(
        "--stream",
        action="store_true",
        help="If this option is set, then streaming synthesis is applied. Streaming means that audio is yielded "
        "as it gets ready. If `--stream` is not set, then a synthesized audio is returned in 1 response only when "
        "all text is processed.",
    )
    parser = add_connection_argparse_parameters(parser)
    args = parser.parse_args()
    if args.output is not None:
        args.output = args.output.expanduser()
    if args.list_devices or args.output_device or args.play_audio:
        import riva.client.audio_io
    return args


def main() -> None:
    args = parse_args()
    if args.output.is_dir():
        print("Empty output file path not allowed")
        return
    if args.list_devices:
        riva.client.audio_io.list_output_devices()
        return

    auth = riva.client.Auth(args.ssl_cert, args.use_ssl, args.server, args.metadata)
    service = riva.client.SpeechSynthesisService(auth)
    nchannels = 1
    sampwidth = 2
    sound_stream, out_f = None, None

    if args.list_voices:
        config_response = service.stub.GetRivaSynthesisConfig(
                riva.client.proto.riva_tts_pb2.RivaSynthesisConfigRequest()
            )
        tts_models = dict()
        for model_config in config_response.model_config:
                language_code = model_config.parameters['language_code']
                voice_name = model_config.parameters['voice_name']
                subvoices = [voice.split(':')[0] for voice in model_config.parameters['subvoices'].split(',')]
                full_voice_names = [voice_name + "." + subvoice for subvoice in subvoices]

                if language_code in tts_models:
                    tts_models[language_code]['voices'].extend(full_voice_names)
                else:
                    tts_models[language_code] = {"voices": full_voice_names}

        tts_models = dict(sorted(tts_models.items()))
        print(json.dumps(tts_models, indent=4))
        return

    if not args.text:
        print("No input text provided")
        return

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

        custom_dictionary_input = {}
        if args.custom_dictionary is not None:
            custom_dictionary_input = read_file_to_dict(args.custom_dictionary)

        print("Generating audio for request...")
        start = time.time()
        if args.stream:
            responses = service.synthesize_online(
                args.text, args.voice, args.language_code, sample_rate_hz=args.sample_rate_hz,
                encoding=AudioEncoding.OGGOPUS if args.encoding == "OGGOPUS" else AudioEncoding.LINEAR_PCM,
                audio_prompt_file=args.audio_prompt_file, quality=20 if args.quality is None else args.quality,
                custom_dictionary=custom_dictionary_input
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
                encoding=AudioEncoding.OGGOPUS if args.encoding == "OGGOPUS" else AudioEncoding.LINEAR_PCM,
                audio_prompt_file=args.audio_prompt_file, quality=20 if args.quality is None else args.quality,
                custom_dictionary=custom_dictionary_input
            )
            stop = time.time()
            print(f"Time spent: {(stop - start):.3f}s")
            if sound_stream is not None:
                sound_stream(resp.audio)
            if out_f is not None:
                out_f.writeframesraw(resp.audio)
    except Exception as e:
        print(e.details())
    finally:
        if out_f is not None:
            out_f.close()
        if sound_stream is not None:
            sound_stream.close()


if __name__ == '__main__':
    main()
