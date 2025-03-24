# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

from typing import Callable, Dict, Generator, Iterable, List, Optional, TextIO, Union
from grpc._channel import _MultiThreadedRendezvous

import riva.client.proto.riva_nmt_pb2 as riva_nmt
import riva.client.proto.riva_nmt_pb2_grpc as riva_nmt_srv
from riva.client import Auth

def streaming_s2s_request_generator(
    audio_chunks: Iterable[bytes], streaming_config: riva_nmt.StreamingTranslateSpeechToSpeechConfig
) -> Generator[riva_nmt.StreamingTranslateSpeechToSpeechRequest, None, None]:
    yield riva_nmt.StreamingTranslateSpeechToSpeechRequest(config=streaming_config)
    for chunk in audio_chunks:
        yield riva_nmt.StreamingTranslateSpeechToSpeechRequest(audio_content=chunk)

def streaming_s2t_request_generator(
    audio_chunks: Iterable[bytes], streaming_config: riva_nmt.StreamingTranslateSpeechToTextConfig
) -> Generator[riva_nmt.StreamingTranslateSpeechToTextRequest, None, None]:
    yield riva_nmt.StreamingTranslateSpeechToTextRequest(config=streaming_config)
    for chunk in audio_chunks:
        yield riva_nmt.StreamingTranslateSpeechToTextRequest(audio_content=chunk)

def add_dnt_phrases_dict(req, dnt_phrases_dict):
    dnt_phrases = None
    if dnt_phrases_dict is not None:
        dnt_phrases = [f"{key}##{value}" for key, value in dnt_phrases_dict.items()]
    if dnt_phrases:
        result_dnt_phrases = ",".join(dnt_phrases)
        req.dnt_phrases.append(result_dnt_phrases)

class NeuralMachineTranslationClient:
    """
    A class for translating text to text. Provides :meth:`translate` which returns translated text
    """
    def __init__(self, auth: Auth) -> None:
        """
        Initializes an instance of the class.

        Args:
            auth (:obj:`Auth`): an instance of :class:`riva.client.auth.Auth` which is used for authentication metadata
                generation.
        """
        self.auth = auth
        self.stub = riva_nmt_srv.RivaTranslationStub(self.auth.channel)

    def streaming_s2s_response_generator(
        self, audio_chunks: Iterable[bytes], streaming_config: riva_nmt.StreamingTranslateSpeechToSpeechConfig
    ) -> Generator[riva_nmt.StreamingTranslateSpeechToSpeechResponse, None, None]:
        """
        Generates speech to speech translation responses for fragments of speech audio in :param:`audio_chunks`.
        The purpose of the method is to perform speech to speech translation "online" - as soon as
        audio is acquired on small chunks of audio.

        All available audio chunks will be sent to a server on first ``next()`` call.

        Args:
            audio_chunks (:obj:`Iterable[bytes]`): an iterable object which contains raw audio fragments
                of speech. For example, such raw audio can be obtained with

                .. code-block:: python

                    import wave
                    with wave.open(file_name, 'rb') as wav_f:
                        raw_audio = wav_f.readframes(n_frames)

            streaming_config (:obj:`riva.client.proto.riva_nmt_pb2.StreamingTranslateSpeechToSpeechConfig`): a config for streaming.
                You may find description of config fields in message ``StreamingTranslateSpeechToSpeechConfig`` in
                `common repo
                <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-nmt-proto>`_.
                An example of creation of streaming config:

                .. code-style:: python

                    from riva.client import RecognitionConfig, StreamingRecognitionConfig, StreamingTranslateSpeechToSpeechConfig, TranslationConfig, SynthesizeSpeechConfig
                    config = RecognitionConfig(enable_automatic_punctuation=True)
                    asr_config = StreamingRecognitionConfig(config, interim_results=True)
                    translation_config = TranslationConfig(source_language_code="es-US",  target_language_code="en-US")
                    tts_config = SynthesizeSpeechConfig(sample_rate_hz=44100, voice_name="English-US.Female-1")
                    streaming_config = StreamingTranslateSpeechToSpeechConfig(asr_config, translation_config, tts_config)

        Yields:
            :obj:`riva.client.proto.riva_nmt_pb2.StreamingTranslateSpeechToSpeechResponse`: responses for audio chunks in
            :param:`audio_chunks`. You may find description of response fields in declaration of
            ``StreamingTranslateSpeechToSpeechResponse``
            message `here
            <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-nmt-proto>`_.
        """
        generator = streaming_s2s_request_generator(audio_chunks, streaming_config)
        for response in self.stub.StreamingTranslateSpeechToSpeech(generator, metadata=self.auth.get_auth_metadata()):
            yield response


    def streaming_s2t_response_generator(
        self, audio_chunks: Iterable[bytes], streaming_config: riva_nmt.StreamingTranslateSpeechToTextConfig
    ) -> Generator[riva_nmt.StreamingTranslateSpeechToTextResponse, None, None]:
        """
        Generates speech to text translation responses for fragments of speech audio in :param:`audio_chunks`.
        The purpose of the method is to perform speech to text translation "online" - as soon as
        audio is acquired on small chunks of audio.

        All available audio chunks will be sent to a server on first ``next()`` call.

        Args:
            audio_chunks (:obj:`Iterable[bytes]`): an iterable object which contains raw audio fragments
                of speech. For example, such raw audio can be obtained with

                .. code-block:: python

                    import wave
                    with wave.open(file_name, 'rb') as wav_f:
                        raw_audio = wav_f.readframes(n_frames)

            streaming_config (:obj:`riva.client.proto.riva_nmt_pb2.StreamingTranslateSpeechToTextConfig`): a config for streaming.
                You may find description of config fields in message ``StreamingTranslateSpeechToTextConfig`` in
                `common repo
                <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-nmt-proto>`_.
                An example of creation of streaming config:

                .. code-style:: python

                    from riva.client import RecognitionConfig, StreamingRecognitionConfig, StreamingTranslateSpeechToTextConfig, TranslationConfig
                    config = RecognitionConfig(enable_automatic_punctuation=True)
                    asr_config = StreamingRecognitionConfig(config, interim_results=True)
                    translation_config = TranslationConfig(source_language_code="es-US",  target_language_code="en-US")
                    streaming_config = StreamingTranslateSpeechToTextConfig(asr_config, translation_config)

        Yields:
            :obj:`riva.client.proto.riva_nmt_pb2.StreamingTranslateSpeechToTextResponse`: responses for audio chunks in
            :param:`audio_chunks`. You may find description of response fields in declaration of
            ``StreamingTranslateSpeechToTextResponse``
            message `here
            <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-nmt-proto>`_.
        """
        generator = streaming_s2t_request_generator(audio_chunks, streaming_config)
        for response in self.stub.StreamingTranslateSpeechToText(generator, metadata=self.auth.get_auth_metadata()):
            yield response


    def translate(
        self,
        texts: List[str],
        model: str,
        source_language: str,
        target_language: str,
        future: bool = False,
        dnt_phrases_dict: Optional[dict] = None,
        max_len_variation: Optional[str] = None,
    ) -> Union[riva_nmt.TranslateTextResponse, _MultiThreadedRendezvous]:
        """
        Translate input list of input text :param:`text` using model :param:`model` from :param:`source_language` into :param:`target_language`

        Args:
            text (:obj:`list[str]`): input text.
            future (:obj:`bool`, defaults to :obj:`False`): whether to return an async result instead of usual
                response. You can get a response by calling ``result()`` method of the future object.

        Returns:
            :obj:`Union[riva.client.proto.riva_nmt_pb2.TranslateTextResponse, grpc._channel._MultiThreadedRendezvous]`:
            a response with output. You may find :class:`riva.client.proto.riva_nmt_pb2.TranslateTextResponse` fields
            description `here
            <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-nmt-proto>`_.
        """
        req = riva_nmt.TranslateTextRequest(
            texts=texts,
            model=model,
            source_language=source_language,
            target_language=target_language
        )
        add_dnt_phrases_dict(req, dnt_phrases_dict)
        if max_len_variation:
            req.max_len_variation = max_len_variation
        func = self.stub.TranslateText.future if future else self.stub.TranslateText
        return func(req, metadata=self.auth.get_auth_metadata())

    def get_config(
            self,
            model: str,
            future: bool = False,
    ) -> Union[riva_nmt.AvailableLanguageResponse, _MultiThreadedRendezvous]:
        req = riva_nmt.AvailableLanguageRequest(model=model)
        func = self.stub.ListSupportedLanguagePairs.future if future else self.stub.ListSupportedLanguagePairs
        return func(req, metadata=self.auth.get_auth_metadata())
