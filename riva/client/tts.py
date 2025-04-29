# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

from typing import Generator, Optional, Union

from grpc._channel import _MultiThreadedRendezvous

import riva.client.proto.riva_tts_pb2 as rtts
import riva.client.proto.riva_tts_pb2_grpc as rtts_srv
from riva.client import Auth
from riva.client.proto.riva_audio_pb2 import AudioEncoding
import wave

def add_custom_dictionary_to_config(req, custom_dictionary):
    result_list = None
    if custom_dictionary is not None:
        result_list = [f"{key}  {value}" for key, value in custom_dictionary.items()]
    if result_list:
        result_string = ','.join(result_list)
        req.custom_dictionary = result_string

class SpeechSynthesisService:
    """
    A class for synthesizing speech from text. Provides :meth:`synthesize` which returns entire audio for a text
    and :meth:`synthesize_online` which returns audio in small chunks as it is becoming available.
    """
    def __init__(self, auth: Auth) -> None:
        """
        Initializes an instance of the class.

        Args:
            auth (:obj:`Auth`): an instance of :class:`riva.client.auth.Auth` which is used for authentication metadata
                generation.
        """
        self.auth = auth
        self.stub = rtts_srv.RivaSpeechSynthesisStub(self.auth.channel)

    def synthesize(
        self,
        text: str,
        voice_name: Optional[str] = None,
        language_code: str = "en-US",
        encoding: AudioEncoding = AudioEncoding.LINEAR_PCM,
        sample_rate_hz: int = 44100,
        zero_shot_audio_prompt_file: Optional[str] = None,
        audio_prompt_encoding: AudioEncoding = AudioEncoding.ENCODING_UNSPECIFIED,
        zero_shot_quality: int = 20,
        future: bool = False,
        custom_dictionary: Optional[dict] = None,
        zero_shot_transcript: Optional[str] = None,
    ) -> Union[rtts.SynthesizeSpeechResponse, _MultiThreadedRendezvous]:
        """
        Synthesizes an entire audio for text :param:`text`.

        Args:
            text (:obj:`str`): An input text.
            voice_name (:obj:`str`, `optional`): A name of the voice, e.g. ``"English-US-Female-1"``. You may find
                available voices in server logs or in server model directory. If this parameter is :obj:`None`, then
                a server will select the first available model with correct :param:`language_code` value.
            language_code (:obj:`str`): a language to use.
            encoding (:obj:`AudioEncoding`): An output audio encoding, e.g. ``AudioEncoding.LINEAR_PCM``.
            sample_rate_hz (:obj:`int`): Number of frames per second in output audio.
            zero_shot_audio_prompt_file (:obj:`str`): Input audio prompt file for Zero Shot Model. Audio length should be between 3-10 seconds.
            audio_prompt_encoding: (:obj:`AudioEncoding`): Encoding of audio prompt file, e.g. ``AudioEncoding.LINEAR_PCM``.
            zero_shot_quality: (:obj:`int`): Required quality of output audio, ranges between 1-40.
            future (:obj:`bool`, defaults to :obj:`False`): Whether to return an async result instead of usual
                response. You can get a response by calling ``result()`` method of the future object.
            custom_dictionary (:obj:`dict`, `optional`): Dictionary with key-value pair containing grapheme and corresponding phoneme
            zero_shot_transcript (:obj:`str`, `optional`): Transcript corresponding to Zero shot audio prompt.
        Returns:
            :obj:`Union[riva.client.proto.riva_tts_pb2.SynthesizeSpeechResponse, grpc._channel._MultiThreadedRendezvous]`:
            a response with output. You may find :class:`riva.client.proto.riva_tts_pb2.SynthesizeSpeechResponse` fields
            description `here
            <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-tts-proto>`_.
        """
        req = rtts.SynthesizeSpeechRequest(
            text=text,
            language_code=language_code,
            sample_rate_hz=sample_rate_hz,
            encoding=encoding,
        )
        if voice_name is not None:
            req.voice_name = voice_name
        if zero_shot_audio_prompt_file is not None:
            with zero_shot_audio_prompt_file.open('rb') as f:
                audio_data = f.read()
                req.zero_shot_data.audio_prompt = audio_data
            req.zero_shot_data.encoding = audio_prompt_encoding
            req.zero_shot_data.quality = zero_shot_quality
            if zero_shot_transcript is not None:
                req.zero_shot_data.transcript = zero_shot_transcript

        add_custom_dictionary_to_config(req, custom_dictionary)

        func = self.stub.Synthesize.future if future else self.stub.Synthesize
        return func(req, metadata=self.auth.get_auth_metadata())

    def synthesize_online(
        self,
        text: str,
        voice_name: Optional[str] = None,
        language_code: str = 'en-US',
        encoding: AudioEncoding = AudioEncoding.LINEAR_PCM,
        sample_rate_hz: int = 44100,
        zero_shot_audio_prompt_file: Optional[str] = None,
        audio_prompt_encoding: AudioEncoding = AudioEncoding.ENCODING_UNSPECIFIED,
        zero_shot_quality: int = 20,
        custom_dictionary: Optional[dict] = None,
    ) -> Generator[rtts.SynthesizeSpeechResponse, None, None]:
        """
        Synthesizes and yields output audio chunks for text :param:`text` as the chunks
        becoming available.

        Args:
            text (:obj:`str`): An input text.
            voice_name (:obj:`str`, `optional`): A name of the voice, e.g. ``"English-US-Female-1"``. You may find
                available voices in server logs or in server model directory. If this parameter is :obj:`None`, then
                a server will select the first available model with correct :param:`language_code` value.
            language_code (:obj:`str`): A language to use.
            encoding (:obj:`AudioEncoding`): An output audio encoding, e.g. ``AudioEncoding.LINEAR_PCM``.
            sample_rate_hz (:obj:`int`): Number of frames per second in output audio.
            zero_shot_audio_prompt_file (:obj:`str`): Input audio prompt file for Zero Shot Model. Audio length should be between 3-10 seconds.
            audio_prompt_encoding: (:obj:`AudioEncoding`): Encoding of audio prompt file, e.g. ``AudioEncoding.LINEAR_PCM``.
            zero_shot_quality: (:obj:`int`): Required quality of output audio, ranges between 1-40.
            custom_dictionary (:obj:`dict`, `optional`): Dictionary with key-value pair containing grapheme and corresponding phoneme

        Yields:
            :obj:`riva.client.proto.riva_tts_pb2.SynthesizeSpeechResponse`: a response with output. You may find
            :class:`riva.client.proto.riva_tts_pb2.SynthesizeSpeechResponse` fields description `here
            <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-tts-proto>`_.
            If :param:`future` is :obj:`True`, then a future object is returned. You may retrieve a response from a
            future object by calling ``result()`` method.
        """
        req = rtts.SynthesizeSpeechRequest(
            text=text,
            language_code=language_code,
            sample_rate_hz=sample_rate_hz,
            encoding=encoding,
        )
        if voice_name is not None:
            req.voice_name = voice_name

        if zero_shot_audio_prompt_file is not None:
            with zero_shot_audio_prompt_file.open('rb') as f:
                audio_data = f.read()
                req.zero_shot_data.audio_prompt = audio_data
            req.zero_shot_data.encoding = audio_prompt_encoding
            req.zero_shot_data.quality = zero_shot_quality

        add_custom_dictionary_to_config(req, custom_dictionary)                   

        return self.stub.SynthesizeOnline(req, metadata=self.auth.get_auth_metadata())
