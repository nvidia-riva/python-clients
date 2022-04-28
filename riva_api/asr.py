import copy
import io
import os
import sys
import time
import warnings
from pathlib import Path
from typing import Callable, Dict, Generator, Iterable, List, Optional, TextIO, Union

import wave

import riva_api.proto.riva_asr_pb2 as rasr
import riva_api.proto.riva_asr_pb2_grpc as rasr_srv
from riva_api.auth import Auth
from riva_api.proto.riva_asr_pb2 import StreamingRecognizeResponse, RecognizeResponse


def get_wav_file_parameters(input_file: os.PathLike) -> Dict[str, Union[int, float]]:
    with wave.open(str(input_file), 'rb') as wf:
        nframes = wf.getnframes()
        rate = wf.getframerate()
        parameters = {
            'nframes': nframes,
            'framerate': rate,
            'duration': nframes / rate,
            'nchannels': wf.getnchannels(),
            'sampwidth': wf.getsampwidth(),
        }
    return parameters


def sleep_audio_length(audio_chunk: bytes, time_to_sleep: float) -> None:
    time.sleep(time_to_sleep)


class AudioChunkFileIterator:
    def __init__(
        self,
        input_file: os.PathLike,
        chunk_n_frames: int,
        delay_callback: Optional[Callable[[bytes, float], None]] = None,
        num_iterations: Optional[int] = 1,
    ) -> None:
        self.input_file: Path = Path(input_file).expanduser()
        self.chunk_n_frames = chunk_n_frames
        self.delay_callback = delay_callback
        self.file_parameters = get_wav_file_parameters(self.input_file)
        self.file_object: Optional[wave.Wave_read] = wave.open(str(self.input_file), 'rb')
        self.num_iterations = num_iterations

    def close(self) -> None:
        self.file_object.close()
        self.file_object = None

    def __enter__(self):
        return self

    def __exit__(self, type_, value, traceback) -> None:
        self.file_object.close()

    def __iter__(self):
        return self

    def __next__(self) -> bytes:
        data = self.file_object.readframes(self.chunk_n_frames)
        if not data:
            raise StopIteration
        if self.delay_callback is not None:
            self.delay_callback(
                data,
                len(data) / self.file_parameters['sampwidth'] / self.file_parameters['framerate']
            )
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
    audio_file: os.PathLike,
) -> None:
    inner_config: rasr.RecognitionConfig = config if isinstance(config, rasr.RecognitionConfig) else config.config
    wav_parameters = get_wav_file_parameters(audio_file)
    inner_config.sample_rate_hertz = wav_parameters['framerate']
    inner_config.audio_channel_count = wav_parameters['nchannels']


PRINT_STREAMING_MODES = ['no', 'time', 'confidence']


def print_streaming(
    response_generator: Iterable[StreamingRecognizeResponse],
    output_file: Optional[Union[Union[os.PathLike, TextIO], List[Union[os.PathLike, TextIO]]]] = None,
    additional_info: str = 'no',
    word_time_offsets: bool = False,
    show_intermediate: bool = False,
    file_mode: str = 'w',
) -> None:
    if additional_info not in PRINT_STREAMING_MODES:
        raise ValueError(
            f"Not allowed value '{additional_info}' of parameter `additional_info`. "
            f"Allowed values are {PRINT_STREAMING_MODES}"
        )
    if additional_info != PRINT_STREAMING_MODES[0] and show_intermediate:
        warnings.warn(
            f"`show_intermediate=True` will not work if `additional_info != {PRINT_STREAMING_MODES[0]}`. "
            f"`additional_info={additional_info}`"
        )
    if additional_info != PRINT_STREAMING_MODES[1] and word_time_offsets:
        warnings.warn(
            f"`word_time_offsets=True` will not work if `additional_info != {PRINT_STREAMING_MODES[1]}`. "
            f"`additional_info={additional_info}"
        )
    if output_file is None:
        output_file = [sys.stdout]
    elif not isinstance(output_file, list):
        output_file = [output_file]
    file_opened = [False] * len(output_file)
    try:
        for i, elem in enumerate(output_file):
            if isinstance(elem, (io.TextIOWrapper, io.TextIOBase)):
                file_opened[i] = False
            else:
                file_opened[i] = True
                output_file[i] = Path(elem).expanduser().open(file_mode)
        start_time = time.time()  # used in 'time` additional_info
        num_chars_printed = 0  # used in 'no' additional_info
        for response in response_generator:
            if not response.results:
                continue
            partial_transcript = ""
            for result in response.results:
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
                                f.write('{: <40s}{: <16s}{: <16s}'.format('Word', 'Start (ms)', 'End (ms)'))
                                for word_info in result.alternatives.words:
                                    f.write(
                                        f'{word_info.word: <40s}{word_info.start_time: <16.0f}'
                                        f'{word_info.end_time: <16.0f}'
                                    )
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
    except Exception:
        for elem in output_file:
            if isinstance(elem, io.TextIOWrapper):
                elem.close()
        raise


def print_offline(response: rasr.RecognizeResponse) -> None:
    print(response)
    if len(response.results) > 0 and len(response.results[0].alternatives) > 0:
        print("Final transcript: ", response.results[0].alternatives[0].transcript)


def streaming_request_generator(
    audio_chunks: Iterable[bytes], streaming_config: rasr.StreamingRecognitionConfig
) -> Generator[rasr.StreamingRecognizeRequest, None, None]:
    yield rasr.StreamingRecognizeRequest(streaming_config=streaming_config)
    for chunk in audio_chunks:
        yield rasr.StreamingRecognizeRequest(audio_content=chunk)


class ASRService:
    def __init__(self, auth: Auth) -> None:
        self.auth = auth
        self.stub = rasr_srv.RivaSpeechRecognitionStub(self.auth.channel)

    def streaming_response_generator(
        self, audio_chunks: Iterable[bytes], streaming_config: rasr.StreamingRecognitionConfig
    ):
        generator = streaming_request_generator(audio_chunks, streaming_config)
        for response in self.stub.StreamingRecognize(generator, metadata=self.auth.get_auth_metadata()):
            yield response

    def offline_recognize(self, audio_bytes: bytes, config: rasr.RecognitionConfig) -> RecognizeResponse:
        request = rasr.RecognizeRequest(config=config, audio=audio_bytes)
        response = self.stub.Recognize(request, metadata=self.auth.get_auth_metadata())
        return response
