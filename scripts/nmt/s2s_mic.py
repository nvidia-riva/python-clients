# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
import wave
import riva.client
from riva.client.argparse_utils import add_asr_config_argparse_parameters, add_connection_argparse_parameters
from typing import Callable, Dict, Generator, Iterable, List, Optional, TextIO, Union
import riva.client.audio_io
import riva.client.proto.riva_nmt_pb2 as riva_nmt

def parse_args() -> argparse.Namespace:
    default_device_info = riva.client.audio_io.get_default_input_device_info()
    default_device_index = None if default_device_info is None else default_device_info['index']
    parser = argparse.ArgumentParser(
        description="Streaming speech to speech translation from microphone via Riva AI Services",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input-device", type=int, default=default_device_index, help="An input audio device to use.")
    parser.add_argument("--list-input-devices", action="store_true", help="List input audio device indices.")
    parser.add_argument("--list-output-devices", action="store_true", help="List input audio device indices.")
    parser.add_argument("--output-device", type=int, help="Output device to use.")
    parser.add_argument(
        "--play-audio",
        action="store_true",
        help="Play input audio simultaneously with transcribing and translating it. If `--output-device` is not provided, "
        "then the default output audio device will be used.",
    )

    parser = add_asr_config_argparse_parameters(parser, profanity_filter=True)
    parser = add_connection_argparse_parameters(parser)
    parser.add_argument(
        "--sample-rate-hz",
        type=int,
        help="A number of frames per second in audio streamed from a microphone.",
        default=16000,
    )
    parser.add_argument(
        "--file-streaming-chunk",
        type=int,
        default=1600,
        help="A maximum number of frames in a audio chunk sent to server.",
    )
    args = parser.parse_args()
    return args

def play_responses(responses: Iterable[riva_nmt.StreamingTranslateSpeechToSpeechResponse],
                   sound_stream) -> None:
    count = 0
    for response in responses:
        #if first:
            #print(f"time to first audio {(stop - start):.3f}s")
        #    first=False
        if sound_stream is not None:
            sound_stream(response.speech.audio)
            fname = "response" + str(count)
            out_f = wave.open(fname, 'wb')
            out_f.setnchannels(1)
            out_f.setsampwidth(2)
            out_f.setframerate(44100)
        count += 1


def main() -> None:
    args = parse_args()
    sound_stream = None
    sampwidth = 2
    nchannels = 1
    if args.list_input_devices:
        riva.client.audio_io.list_input_devices()
        return
    if args.output_device is not None or args.play_audio:
        print("playing audio")
        sound_stream = riva.client.audio_io.SoundCallBack(
            args.output_device, nchannels=nchannels, sampwidth=sampwidth, framerate=44100
        )
        print(sound_stream)
    first = True # first tts output chunk received
    auth = riva.client.Auth(args.ssl_cert, args.use_ssl, args.server)
    nmt_service = riva.client.NeuralMachineTranslationClient(auth)
    s2s_config = riva.client.StreamingTranslateSpeechToSpeechConfig(
        asrConfig = riva.client.StreamingRecognitionConfig(
            config=riva.client.RecognitionConfig(
                encoding=riva.client.AudioEncoding.LINEAR_PCM,
                language_code=args.language_code,
                max_alternatives=1,
                profanity_filter=args.profanity_filter,
                enable_automatic_punctuation=args.automatic_punctuation,
                verbatim_transcripts=not args.no_verbatim_transcripts,
                sample_rate_hertz=args.sample_rate_hz,
                audio_channel_count=1,
            ),
            interim_results=True,
        )
    )

    #riva.client.add_word_boosting_to_config(config, args.boosted_lm_words, args.boosted_lm_score)
    with riva.client.audio_io.MicrophoneStream(
        args.sample_rate_hz,
        args.file_streaming_chunk,
        device=args.input_device,
    ) as audio_chunk_iterator:
        play_responses(responses=nmt_service.streaming_s2s_response_generator(
            audio_chunks=audio_chunk_iterator,
            streaming_config=s2s_config), sound_stream=sound_stream)
        # if first:
        #         first = False
        #     if sound_stream is not None:
        #         sound_stream(response.audio)



if __name__ == '__main__':
    main()
