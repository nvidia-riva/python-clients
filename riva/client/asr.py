# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import io
import os
import sys
import time
import warnings
import wave
from pathlib import Path
from typing import Callable, Dict, Generator, Iterable, List, Optional, TextIO, Union

from grpc._channel import _MultiThreadedRendezvous

import riva.client
import riva.client.proto.riva_asr_pb2 as rasr
import riva.client.proto.riva_asr_pb2_grpc as rasr_srv
from riva.client.auth import Auth


def get_wav_file_parameters(input_file: Union[str, os.PathLike]) -> Dict[str, Union[int, float]]:
    try:
        input_file = Path(input_file).expanduser()
        with wave.open(str(input_file), 'rb') as wf:
            nframes = wf.getnframes()
            rate = wf.getframerate()
            parameters = {
                'nframes': nframes,
                'framerate': rate,
                'duration': nframes / rate,
                'nchannels': wf.getnchannels(),
                'sampwidth': wf.getsampwidth(),
                'data_offset': wf.getfp().size_read + wf.getfp().offset
            }
    except:
        # Not a WAV file
        return None
    return parameters


def sleep_audio_length(audio_chunk: bytes, time_to_sleep: float) -> None:
    time.sleep(time_to_sleep)


class AudioChunkFileIterator:
    def __init__(
        self,
        input_file: Union[str, os.PathLike],
        chunk_n_frames: int,
        delay_callback: Optional[Callable[[bytes, float], None]] = None,
    ) -> None:
        self.input_file: Path = Path(input_file).expanduser()
        self.chunk_n_frames = chunk_n_frames
        self.delay_callback = delay_callback
        self.file_parameters = get_wav_file_parameters(self.input_file)
        self.file_object: Optional[typing.BinaryIO] = open(str(self.input_file), 'rb')
        if self.delay_callback and self.file_parameters is None:
            warnings.warn(f"delay_callback not supported for encoding other than LINEAR_PCM")
            self.delay_callback = None
        self.first_buffer = True

    def close(self) -> None:
        self.file_object.close()
        self.file_object = None

    def __enter__(self):
        return self

    def __exit__(self, type_, value, traceback) -> None:
        if self.file_object is not None:
            self.file_object.close()

    def __iter__(self):
        return self

    def __next__(self) -> bytes:
        if self.file_parameters:
            data = self.file_object.read(self.chunk_n_frames * self.file_parameters['sampwidth'] * self.file_parameters['nchannels'])
        else:
            data = self.file_object.read(self.chunk_n_frames)
        if not data:
            self.close()
            raise StopIteration
        if self.delay_callback is not None:
            offset = self.file_parameters['data_offset'] if self.first_buffer else 0
            self.delay_callback(
                data[offset:], (len(data) - offset) / self.file_parameters['sampwidth'] / self.file_parameters['framerate']
            )
            self.first_buffer = False
        return data


def add_word_boosting_to_config(
    config: Union[rasr.StreamingRecognitionConfig, rasr.RecognitionConfig],
    boosted_lm_words: Optional[List[str]],
    boosted_lm_score: float,
) -> None:
    inner_config: rasr.RecognitionConfig = config if isinstance(config, rasr.RecognitionConfig) else config.config
    if boosted_lm_words is not None:
        speech_context = rasr.SpeechContext()
        speech_context.phrases.extend(boosted_lm_words)
        speech_context.boost = boosted_lm_score
        inner_config.speech_contexts.append(speech_context)


def add_audio_file_specs_to_config(
    config: Union[rasr.StreamingRecognitionConfig, rasr.RecognitionConfig],
    audio_file: Union[str, os.PathLike],
) -> None:
    inner_config: rasr.RecognitionConfig = config if isinstance(config, rasr.RecognitionConfig) else config.config
    wav_parameters = get_wav_file_parameters(audio_file)
    if wav_parameters is not None:
        inner_config.sample_rate_hertz = wav_parameters['framerate']
        inner_config.audio_channel_count = wav_parameters['nchannels']


def add_speaker_diarization_to_config(
    config: Union[rasr.RecognitionConfig],
    diarization_enable: bool,
    diarization_max_speakers: int,
) -> None:
    inner_config: rasr.RecognitionConfig = config if isinstance(config, rasr.RecognitionConfig) else config.config
    if diarization_enable:
        diarization_config = rasr.SpeakerDiarizationConfig(
            enable_speaker_diarization=True,
            max_speaker_count=diarization_max_speakers,
        )
        inner_config.diarization_config.CopyFrom(diarization_config)


def add_endpoint_parameters_to_config(
    config: Union[rasr.StreamingRecognitionConfig, rasr.RecognitionConfig],
    start_history: int,
    start_threshold: float,
    stop_history: int,
    stop_history_eou: int,
    stop_threshold: float,
    stop_threshold_eou: float,
) -> None:
    if not (start_history > 0 or start_threshold > 0 or stop_history > 0 or stop_history_eou > 0 or stop_threshold > 0 or stop_threshold_eou > 0):
        return 
         
    inner_config: rasr.RecognitionConfig = config if isinstance(config, rasr.RecognitionConfig) else config.config
    endpointing_config = rasr.EndpointingConfig()
    if start_history > 0:
        endpointing_config.start_history = start_history
    if start_threshold > 0:
        endpointing_config.start_threshold = start_threshold
    if stop_history > 0:
        endpointing_config.stop_history = stop_history
    if stop_history_eou > 0:
        endpointing_config.stop_history_eou = stop_history_eou
    if stop_threshold > 0:
        endpointing_config.stop_threshold = stop_threshold
    if stop_threshold_eou > 0:
        endpointing_config.stop_threshold_eou = stop_threshold_eou
    inner_config.endpointing_config.CopyFrom(endpointing_config)


def add_custom_configuration_to_config(
    config: Union[rasr.StreamingRecognitionConfig, rasr.RecognitionConfig],
    custom_configuration: str,
) -> None:
    custom_configuration = custom_configuration.strip().replace(" ", "")
    if not custom_configuration:
        return
    inner_config: rasr.RecognitionConfig = config if isinstance(config, rasr.RecognitionConfig) else config.config
    for pair in custom_configuration.split(","):
        key_value = pair.split(":")
        if len(key_value) == 2:
            inner_config.custom_configuration[key_value[0]] = key_value[1]
        else:
            raise ValueError(f"Invalid key:value pair {key_value}")


PRINT_STREAMING_ADDITIONAL_INFO_MODES = ['no', 'time', 'confidence']


def print_streaming(
    responses: Iterable[rasr.StreamingRecognizeResponse],
    output_file: Optional[Union[Union[os.PathLike, str, TextIO], List[Union[os.PathLike, str, TextIO]]]] = None,
    additional_info: str = 'no',
    word_time_offsets: bool = False,
    show_intermediate: bool = False,
    file_mode: str = 'w',
    speaker_diarization: bool = False,
) -> None:
    """
    Prints streaming speech recognition results to provided files or streams.

    Args:
        responses (:obj:`Iterable[riva.client.proto.riva_asr_pb2.StreamingRecognizeResponse]`): responses acquired during
            streaming speech recognition.
        output_file (:obj:`Union[Union[os.PathLike, str, TextIO], List[Union[os.PathLike, str, TextIO]]]`, `optional`):
            a path to an output file or a text stream or a list of paths/streams. If contains several elements, then
            output will be written to all destinations. If :obj:`None`, then output will be written to STDOUT.
        additional_info (:obj:`str`, defaults to :obj:`"no"`): a string which can take one of three values:
            :obj:`"no"`, :obj:`"time"`, :obj:`"confidence"`.

            If :obj:`"no"`, then partial transcript is prefixed by ">>", and final transcript is prefixed with "##".
            An option :param:`show_intermediate` can be used.

            If :obj:`"time"`, then transcripts are prefixed by time when they were printed. An option
            :param:`word_time_offsets` can be used.

            If :obj:`"confidence"`, then transcript stability and confidence are printed. Finished and updating
            parts of a transcript are shown separately.
        word_time_offsets (:obj:`bool`, defaults to :obj:`False`): If :obj:`True`, then word time stamps are printed.
            Available only if ``additional_info="time"``.
        show_intermediate (:obj:`bool`, defaults to :obj:`False`): If :obj:`True`, then partial transcripts are
            printed. If printing is performed to a stream (e.g. :obj:`sys.stdout`), then partial transcript is updated
            on same line of a console. Available only if ``additional_info="no"``.
        file_mode (:obj:`str`, defaults to :obj:`"w"`): a mode in which files are opened.

    Raises:
        :obj:`ValueError`: if wrong :param:`additional_info` value is passed to this function.
    """
    if additional_info not in PRINT_STREAMING_ADDITIONAL_INFO_MODES:
        raise ValueError(
            f"Not allowed value '{additional_info}' of parameter `additional_info`. "
            f"Allowed values are {PRINT_STREAMING_ADDITIONAL_INFO_MODES}"
        )
    if additional_info != PRINT_STREAMING_ADDITIONAL_INFO_MODES[0] and show_intermediate:
        warnings.warn(
            f"`show_intermediate=True` will not work if "
            f"`additional_info != {PRINT_STREAMING_ADDITIONAL_INFO_MODES[0]}`. `additional_info={additional_info}`"
        )
    if additional_info != PRINT_STREAMING_ADDITIONAL_INFO_MODES[1] and word_time_offsets:
        warnings.warn(
            f"`word_time_offsets=True` will not work if "
            f"`additional_info != {PRINT_STREAMING_ADDITIONAL_INFO_MODES[1]}`. `additional_info={additional_info}"
        )
    if output_file is None:
        output_file = [sys.stdout]
    elif not isinstance(output_file, list):
        output_file = [output_file]
    file_opened = [False] * len(output_file)
    try:
        for i, elem in enumerate(output_file):
            if isinstance(elem, io.TextIOBase):
                file_opened[i] = False
            else:
                file_opened[i] = True
                output_file[i] = Path(elem).expanduser().open(file_mode)
        start_time = time.time()  # used in 'time` additional_info
        num_chars_printed = 0  # used in 'no' additional_info
        for response in responses:
            if not response.results:
                continue
            partial_transcript = ""
            for result in response.results:
                if result.pipeline_states and len(result.pipeline_states.vad_probabilities) > 0:
                    vad_prob_logs = "VAD States: "
                    for vad_state in result.pipeline_states.vad_probabilities:
                            vad_prob_logs += str(vad_state) + " "
                    for i, f in enumerate(output_file):
                        f.write(vad_prob_logs + "\n")
                if not result.alternatives:
                    continue
                transcript = result.alternatives[0].transcript
                if additional_info == 'no':
                    if result.is_final:
                        if show_intermediate:
                            overwrite_chars = ' ' * (num_chars_printed - len(transcript))
                            for i, f in enumerate(output_file):
                                f.write("## " + transcript + (overwrite_chars if not file_opened[i] else '') + "\n")
                            num_chars_printed = 0
                        else:
                            for i, alternative in enumerate(result.alternatives):
                                for f in output_file:
                                    f.write(
                                        f'##'
                                        + (f'(alternative {i + 1})' if i > 0 else '')
                                        + f' {alternative.transcript}\n'
                                    )
                    else:
                        partial_transcript += transcript
                elif additional_info == 'time':
                    if result.is_final:
                        for i, alternative in enumerate(result.alternatives):
                            for f in output_file:
                                f.write(
                                    f"Time {time.time() - start_time:.2f}s: Transcript {i}: {alternative.transcript}\n"
                                )
                        if word_time_offsets:
                            for f in output_file:
                                f.write("Timestamps:\n")
                                temp = '{: <40s}{: <16s}{: <16s}'
                                value = ['Word', 'Start (ms)', 'End (ms)']
                                if speaker_diarization:
                                    temp += '{: <16s}'
                                    value.append('Speaker')
                                temp += '\n'
                                f.write(temp.format(*value))
                                for word_info in result.alternatives[0].words:
                                    f.write(
                                        f'{word_info.word: <40s}{word_info.start_time: <16.0f}'
                                        f'{word_info.end_time: <16.0f}'
                                    )
                                    if speaker_diarization:
                                        f.write(f'{word_info.speaker_tag: <16d}')
                                    f.write('\n')
                    else:
                        partial_transcript += transcript
                else:  # additional_info == 'confidence'
                    if result.is_final:
                        for f in output_file:
                            f.write(f'## {transcript}\n')
                            f.write(f'Confidence: {result.alternatives[0].confidence:9.4f}\n')
                    else:
                        for f in output_file:
                            f.write(f'>> {transcript}\n')
                            f.write(f'Stability: {result.stability:9.4f}\n')
            if additional_info == 'no':
                if show_intermediate and partial_transcript != '':
                    overwrite_chars = ' ' * (num_chars_printed - len(partial_transcript))
                    for i, f in enumerate(output_file):
                        f.write(">> " + partial_transcript + ('\n' if file_opened[i] else overwrite_chars + '\r'))
                    num_chars_printed = len(partial_transcript) + 3
            elif additional_info == 'time':
                for f in output_file:
                    if partial_transcript:
                        f.write(f">>>Time {time.time():.2f}s: {partial_transcript}\n")
            else:
                for f in output_file:
                    f.write('----\n')
    finally:
        for fo, elem in zip(file_opened, output_file):
            if fo:
                elem.close()


def print_offline(response: rasr.RecognizeResponse) -> None:
    print(response)
    if len(response.results) > 0 and len(response.results[0].alternatives) > 0:
        final_transcript = ""
        for res in response.results:
            final_transcript += res.alternatives[0].transcript
        print("Final transcript:", final_transcript)


def streaming_request_generator(
    audio_chunks: Iterable[bytes], streaming_config: rasr.StreamingRecognitionConfig
) -> Generator[rasr.StreamingRecognizeRequest, None, None]:
    yield rasr.StreamingRecognizeRequest(streaming_config=streaming_config)
    for chunk in audio_chunks:
        yield rasr.StreamingRecognizeRequest(audio_content=chunk)


class ASRService:
    """Provides streaming and offline recognition services. Calls gRPC stubs with authentication metadata."""
    def __init__(self, auth: Auth) -> None:
        """
        Initializes an instance of the class.

        Args:
            auth (:obj:`riva.client.auth.Auth`): an instance of :class:`riva.client.auth.Auth` which is used for
                authentication metadata generation.
        """
        self.auth = auth
        self.stub = rasr_srv.RivaSpeechRecognitionStub(self.auth.channel)

    def streaming_response_generator(
        self, audio_chunks: Iterable[bytes], streaming_config: rasr.StreamingRecognitionConfig
    ) -> Generator[rasr.StreamingRecognizeResponse, None, None]:
        """
        Generates speech recognition responses for fragments of speech audio in :param:`audio_chunks`.
        The purpose of the method is to perform speech recognition "online" - as soon as
        audio is acquired on small chunks of audio.

        All available audio chunks will be sent to a server on first ``next()`` call.

        Args:
            audio_chunks (:obj:`Iterable[bytes]`): an iterable object which contains raw audio fragments
                of speech. For example, such raw audio can be obtained with

                .. code-block:: python

                    import wave
                    with wave.open(file_name, 'rb') as wav_f:
                        raw_audio = wav_f.readframes(n_frames)

            streaming_config (:obj:`riva.client.proto.riva_asr_pb2.StreamingRecognitionConfig`): a config for streaming.
                You may find description of config fields in message ``StreamingRecognitionConfig`` in
                `common repo
                <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-asr-proto>`_.
                An example of creation of streaming config:

                .. code-style:: python

                    from riva.client import RecognitionConfig, StreamingRecognitionConfig
                    config = RecognitionConfig(enable_automatic_punctuation=True)
                    streaming_config = StreamingRecognitionConfig(config, interim_results=True)

        Yields:
            :obj:`riva.client.proto.riva_asr_pb2.StreamingRecognizeResponse`: responses for audio chunks in
            :param:`audio_chunks`. You may find description of response fields in declaration of
            ``StreamingRecognizeResponse``
            message `here
            <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-asr-proto>`_.
        """
        generator = streaming_request_generator(audio_chunks, streaming_config)
        for response in self.stub.StreamingRecognize(generator, metadata=self.auth.get_auth_metadata()):
            yield response

    def offline_recognize(
        self, audio_bytes: bytes, config: rasr.RecognitionConfig, future: bool = False
    ) -> Union[rasr.RecognizeResponse, _MultiThreadedRendezvous]:
        """
        Performs speech recognition for raw audio in :param:`audio_bytes`. This method is for processing of
        huge audio at once - not as it is being generated.

        Args:
            audio_bytes (:obj:`bytes`): a raw audio. For example it can be obtained with

                .. code-block:: python

                    import wave
                    with wave.open(file_name, 'rb') as wav_f:
                        raw_audio = wav_f.readframes(n_frames)

            config (:obj:`riva.client.proto.riva_asr_pb2.RecognitionConfig`): a config for offline speech recognition.
                You may find description of config fields in message ``RecognitionConfig`` in
                `common repo
                <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-asr-proto>`_.
                An example of creation of config:

                .. code-style:: python

                    from riva.client import RecognitionConfig
                    config = RecognitionConfig(enable_automatic_punctuation=True)
            future (:obj:`bool`, defaults to :obj:`False`): whether to return an async result instead of usual
                response. You can get a response by calling ``result()`` method of the future object.

        Returns:
            :obj:`Union[riva.client.proto.riva_asr_pb2.RecognizeResponse, grpc._channel._MultiThreadedRendezvous]``: a
            response with results of :param:`audio_bytes` processing. You may find description of response fields in
            declaration of ``RecognizeResponse`` message `here
            <https://docs.nvidia.com/deeplearning/riva/user-guide/docs/reference/protos/protos.html#riva-proto-riva-asr-proto>`_.
            If :param:`future` is :obj:`True`, then a future object is returned. You may retrieve a response from a
            future object by calling ``result()`` method.
        """
        request = rasr.RecognizeRequest(config=config, audio=audio_bytes)
        func = self.stub.Recognize.future if future else self.stub.Recognize
        return func(request, metadata=self.auth.get_auth_metadata())
