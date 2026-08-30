# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import time
from typing import Dict, Generator, Optional, Union, Iterable

import grpc
from grpc._channel import _MultiThreadedRendezvous

import riva.client.proto.riva_tts_pb2 as rtts
import riva.client.proto.riva_tts_pb2_grpc as rtts_srv
from riva.client import Auth
from riva.client.proto.riva_audio_pb2 import AudioEncoding
import wave

def parse_custom_configuration(custom_configuration: str) -> Dict[str, str]:
    """Parse a comma-separated ``key:value`` string into a dictionary.

    Args:
        custom_configuration: String in format ``"key1:value1,key2:value2"``.

    Returns:
        Dictionary of parsed key/value pairs (empty if the input is empty).

    Raises:
        ValueError: If any pair is not in ``key:value`` form.
    """
    result: Dict[str, str] = {}
    custom_configuration = custom_configuration.strip().replace(" ", "")
    if not custom_configuration:
        return result
    for pair in custom_configuration.split(","):
        key_value = pair.split(":")
        if len(key_value) == 2:
            result[key_value[0]] = key_value[1]
        else:
            raise ValueError(f"Invalid key:value pair {key_value}")
    return result


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
        sample_rate_hz: int = 22050,
        zero_shot_audio_prompt_file: Optional[str] = None,
        audio_prompt_encoding: AudioEncoding = AudioEncoding.ENCODING_UNSPECIFIED,
        zero_shot_quality: int = 20,
        future: bool = False,
        custom_dictionary: Optional[dict] = None,
        zero_shot_transcript: Optional[str] = None,
        custom_configuration: Optional[Dict[str, str]] = None,
        enable_word_time_offsets: Optional[bool] = None,
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
            custom_configuration (:obj:`Dict[str, str]`, `optional`): Free-form key/value parameters forwarded
                to the synthesizer (e.g. ``{"exaggeration_factor": "1.5"}``). Model-specific.
            enable_word_time_offsets (:obj:`bool`, `optional`): If :obj:`True`, request per-word
                start/end timestamps, returned in ``response.meta.words`` (supported by models that produce
                word alignment, e.g. Magpie TTS).
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
        if enable_word_time_offsets is not None:
            req.enable_word_time_offsets = enable_word_time_offsets
        if zero_shot_audio_prompt_file is not None:
            with zero_shot_audio_prompt_file.open('rb') as f:
                audio_data = f.read()
                req.zero_shot_data.audio_prompt = audio_data
            req.zero_shot_data.encoding = audio_prompt_encoding
            req.zero_shot_data.quality = zero_shot_quality
            if zero_shot_transcript is not None:
                req.zero_shot_data.transcript = zero_shot_transcript

        if custom_configuration:
            for key, value in custom_configuration.items():
                req.custom_configuration[key] = str(value)

        add_custom_dictionary_to_config(req, custom_dictionary)

        func = self.stub.Synthesize.future if future else self.stub.Synthesize
        return func(req, metadata=self.auth.get_auth_metadata())

    def synthesize_online(
        self,
        text: Union[str, list[str], Iterable[str]],
        voice_name: Optional[str] = None,
        language_code: str = 'en-US',
        encoding: AudioEncoding = AudioEncoding.LINEAR_PCM,
        sample_rate_hz: int = 22050,
        zero_shot_audio_prompt_file: Optional[str] = None,
        audio_prompt_encoding: AudioEncoding = AudioEncoding.ENCODING_UNSPECIFIED,
        zero_shot_quality: int = 20,
        custom_dictionary: Optional[dict] = None,
        custom_configuration: Optional[Dict[str, str]] = None,
        enable_word_time_offsets: Optional[bool] = None,
    ) -> Generator[rtts.SynthesizeSpeechResponse, None, None]:
        """
        Synthesizes and yields output audio chunks for text :param:`text` as the chunks
        becoming available.

        Args:
            text (:obj:`Union[str, list[str], Iterable[str]]`): An input text.
                If a string, it will be synthesized as a single text.
                If a list of strings, it will be synthesized as a list of texts.
                If an iterable of strings, it will be synthesized as an iterable of texts.
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
            custom_configuration (:obj:`Dict[str, str]`, `optional`): Free-form key/value parameters forwarded
                to the synthesizer (e.g. ``{"exaggeration_factor": "1.5"}``). Model-specific.
            enable_word_time_offsets (:obj:`bool`, `optional`): If :obj:`True`, request per-word
                start/end timestamps, returned in ``response.meta.words`` (supported by models that produce
                word alignment, e.g. Magpie TTS).
        Yields:
            :obj:`riva.client.proto.riva_tts_pb2.SynthesizeSpeechResponse`: a response with output. You may find
            :class:`riva.client.proto.riva_tts_pb2.SynthesizeSpeechResponse` fields description `here
            <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-tts-proto>`_.
            If :param:`future` is :obj:`True`, then a future object is returned. You may retrieve a response from a
            future object by calling ``result()`` method.
        """
        req = rtts.SynthesizeSpeechRequest(
            text="",
            language_code=language_code,
            sample_rate_hz=sample_rate_hz,
            encoding=encoding,
        )
        if voice_name is not None:
            req.voice_name = voice_name
        if enable_word_time_offsets is not None:
            req.enable_word_time_offsets = enable_word_time_offsets

        if zero_shot_audio_prompt_file is not None:
            with zero_shot_audio_prompt_file.open('rb') as f:
                audio_data = f.read()
                req.zero_shot_data.audio_prompt = audio_data
            req.zero_shot_data.encoding = audio_prompt_encoding
            req.zero_shot_data.quality = zero_shot_quality

        if custom_configuration:
            for key, value in custom_configuration.items():
                req.custom_configuration[key] = str(value)

        add_custom_dictionary_to_config(req, custom_dictionary)

        def request_generator(text):
            if isinstance(text, str):
                req.text = text
                yield req
            elif isinstance(text, list):
                for t in text:
                    req.text = t
                    yield req
            elif isinstance(text, Iterable[str]):
                for t in text:
                    req.text = t
                    yield req
            else:
                raise ValueError(f"Invalid text type: {type(text)}")

        return self.stub.SynthesizeOnline(request_generator(text), metadata=self.auth.get_auth_metadata())


import logging
from typing import Iterator

import grpc

from riva.client.retry import is_retryable_grpc_error, exponential_backoff

LOGGER = logging.getLogger(__name__)


class ResilientStreamingTTS:
    """A resilient wrapper around :class:`SpeechSynthesisService` for streaming TTS.

    This class retries individual text segments on transient gRPC failures,
    yielding audio chunks as they arrive. It is designed for long-running
    streaming synthesis where network blips should not terminate the session.

    Example:
        >>> auth = Auth(uri="localhost:50051")
        >>> tts = SpeechSynthesisService(auth)
        >>> resilient_tts = ResilientStreamingTTS(tts)
        >>> for audio_chunk in resilient_tts.synthesize_stream(
        ...     ["Hello world", "This is a test."],
        ...     voice_name="English-US-Female-1",
        ... ):
        ...     play_audio(audio_chunk)

    Args:
        tts_service: The underlying :class:`SpeechSynthesisService` instance.
        max_retries: Maximum number of retry attempts per text segment.
        base_delay: Initial backoff delay in seconds.
        max_delay: Maximum backoff delay in seconds.
    """

    def __init__(
        self,
        tts_service: SpeechSynthesisService,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ) -> None:
        self.tts_service = tts_service
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._retry_count = 0

    def synthesize_stream(
        self,
        text_segments: Union[str, list[str], Iterable[str]],
        voice_name: Optional[str] = None,
        language_code: str = 'en-US',
        encoding: AudioEncoding = AudioEncoding.LINEAR_PCM,
        sample_rate_hz: int = 22050,
        zero_shot_audio_prompt_file: Optional[str] = None,
        audio_prompt_encoding: AudioEncoding = AudioEncoding.ENCODING_UNSPECIFIED,
        zero_shot_quality: int = 20,
        custom_dictionary: Optional[dict] = None,
        custom_configuration: Optional[Dict[str, str]] = None,
        enable_word_time_offsets: Optional[bool] = None,
    ) -> Generator[rtts.SynthesizeSpeechResponse, None, None]:
        """Synthesize speech from text segments with automatic recovery.

        Each text segment is sent independently. If the gRPC stream fails
        while synthesizing a segment, that segment is retried up to
        *max_retries* times before the error is propagated.

        Args:
            text_segments: Input text. A single string, a list, or any iterable
                of strings. Each element is treated as one retryable unit.
            voice_name: See :meth:`SpeechSynthesisService.synthesize_online`.
            language_code: See :meth:`SpeechSynthesisService.synthesize_online`.
            encoding: See :meth:`SpeechSynthesisService.synthesize_online`.
            sample_rate_hz: See :meth:`SpeechSynthesisService.synthesize_online`.
            zero_shot_audio_prompt_file: See :meth:`SpeechSynthesisService.synthesize_online`.
            audio_prompt_encoding: See :meth:`SpeechSynthesisService.synthesize_online`.
            zero_shot_quality: See :meth:`SpeechSynthesisService.synthesize_online`.
            custom_dictionary: See :meth:`SpeechSynthesisService.synthesize_online`.
            custom_configuration: See :meth:`SpeechSynthesisService.synthesize_online`.
            enable_word_time_offsets: See :meth:`SpeechSynthesisService.synthesize_online`.

        Yields:
            :obj:`SynthesizeSpeechResponse` objects containing audio chunks.

        Raises:
            :obj:`grpc.RpcError`: If a non-retryable error occurs or the
            maximum number of retries is exceeded for a segment.
        """
        # Normalise input to an iterator of strings.
        if isinstance(text_segments, str):
            segment_iter: Iterator[str] = iter([text_segments])
        else:
            segment_iter = iter(text_segments)

        for segment in segment_iter:
            attempt = 0
            last_exception: Optional[grpc.RpcError] = None

            while True:
                try:
                    responses = self.tts_service.synthesize_online(
                        text=segment,
                        voice_name=voice_name,
                        language_code=language_code,
                        encoding=encoding,
                        sample_rate_hz=sample_rate_hz,
                        zero_shot_audio_prompt_file=zero_shot_audio_prompt_file,
                        audio_prompt_encoding=audio_prompt_encoding,
                        zero_shot_quality=zero_shot_quality,
                        custom_dictionary=custom_dictionary,
                        custom_configuration=custom_configuration,
                        enable_word_time_offsets=enable_word_time_offsets,
                    )
                    for resp in responses:
                        yield resp
                    break  # Segment completed successfully.

                except grpc.RpcError as exc:
                    last_exception = exc
                    if not is_retryable_grpc_error(exc):
                        LOGGER.warning(
                            "Non-retryable gRPC error in streaming TTS: %s – %s",
                            exc.code() if hasattr(exc, "code") else "UNKNOWN",
                            exc.details() if hasattr(exc, "details") else str(exc),
                        )
                        raise
                    if attempt >= self.max_retries:
                        LOGGER.error(
                            "Streaming TTS failed permanently after %d retries for segment %r. "
                            "Last error: %s",
                            self.max_retries,
                            segment,
                            exc.details() if hasattr(exc, "details") else str(exc),
                        )
                        raise
                    delay = exponential_backoff(attempt, self.base_delay, self.max_delay)
                    LOGGER.info(
                        "Streaming TTS connection lost (%s) on segment %r. "
                        "Retrying in %.2f s (attempt %d/%d).",
                        exc.code(),
                        segment,
                        delay,
                        attempt + 1,
                        self.max_retries,
                    )
                    self._retry_count += 1
                    attempt += 1
                    time.sleep(delay)
                    # Loop continues: retry the same segment.
