import io
import os
import queue
import sys
import time
import warnings
from typing import Dict, Generator, List, Optional, TextIO, Union

import pyaudio
import wave

import riva_api.proto.riva_asr_pb2 as rasr
import riva_api.proto.riva_asr_pb2_grpc as rasr_srv
from riva_api.auth import Auth
from riva_api.proto.riva_asr_pb2 import StreamingRecognizeResponse, RecognizeResponse

ALLOWED_PREFIXES_FOR_TRANSCRIPTS = ['time', 'partial vs final', '>> vs ##']


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


def audio_requests_from_file_generator(
    input_file: os.PathLike,
    config: rasr.StreamingRecognitionConfig,
    num_iterations: int,
    simulate_realtime: bool,
    rate: int,
    file_streaming_chunk: int,
    output_audio_stream: Optional[pyaudio.Stream],
) -> Generator[rasr.StreamingRecognizeRequest, None, None]:
    if simulate_realtime and output_audio_stream is not None:
        raise ValueError(f"It is not possible to set `simulate_realtime=True` and provide `output_audio_stream`.")
    try:
        for i in range(num_iterations):
            with wave.open(str(input_file), 'rb') as w:
                start_time = time.time()
                yield rasr.StreamingRecognizeRequest(streaming_config=config)
                num_requests = 0
                while True:
                    d = w.readframes(file_streaming_chunk)
                    if len(d) <= 0:
                        break
                    num_requests += 1
                    if simulate_realtime:
                        time_to_sleep = max(
                            0.0, file_streaming_chunk / rate * num_requests - (time.time() - start_time)
                        )
                        time.sleep(time_to_sleep)
                    elif output_audio_stream is not None:
                        output_audio_stream.write(d)
                    yield rasr.StreamingRecognizeRequest(audio_content=d)
    except Exception as e:
        print(e)


class OutputAudioStream:
    def __init__(
        self, output_device_index: Optional[int], sampwidth: int, nchannels: int, framerate: int,
    ) -> None:
        self.pa = pyaudio.PyAudio()
        self.stream = self.pa.open(
            output_device_index=output_device_index,
            format=self.pa.get_format_from_width(sampwidth),
            channels=nchannels,
            rate=framerate,
            output=True,
        )

    def __enter__(self) -> pyaudio.Stream:
        return self.stream

    def __exit__(self, type_, value, traceback) -> None:
        self.stream.close()
        self.pa.terminate()


class MicrophoneStream:
    """Opens a recording stream as a generator yielding the audio chunks."""

    def __init__(self, rate, chunk, device=None):
        self._rate = rate
        self._chunk = chunk
        self._device = device

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            input_device_index=self._device,
            channels=1,
            rate=self._rate,
            input=True,
            frames_per_buffer=self._chunk,
            stream_callback=self._fill_buffer,
        )

        self.closed = False

        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b''.join(data)


PRINT_STREAMING_MODES = ['simple', 'show_time', 'show_confidence']


def print_streaming(
    generator: Generator[StreamingRecognizeResponse, None, None],
    output_file: Optional[Union[Union[os.PathLike, TextIO], List[Union[os.PathLike, TextIO]]]] = None,
    mode: str = 'simple',
    word_time_offsets: bool = False,
    show_intermediate: bool = False,
):
    if mode not in PRINT_STREAMING_MODES:
        raise ValueError(f"Not allowed value '{mode}' of parameter `mode`. Allowed values are {PRINT_STREAMING_MODES}")
    if mode != PRINT_STREAMING_MODES[0] and show_intermediate:
        warnings.warn(f"`show_intermediate=True` will not work if `mode != {PRINT_STREAMING_MODES[0]}`. `mode={mode}`")
    if mode != PRINT_STREAMING_MODES[1] and word_time_offsets:
        warnings.warn(f"`word_time_offsets=True` will not work if `mode != {PRINT_STREAMING_MODES[1]}`. `mode={mode}")
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
                output_file[i] = open(elem, 'w')
        start_time = time.time()  # used in 'show_time` mode
        num_chars_printed = 0  # used in 'simple' mode
        for response in generator:
            if not response.results:
                continue
            partial_transcript = ""
            for result in response.results:
                if not result.alternatives:
                    continue
                transcript = result.alternatives[0].transcript
                if mode == 'simple':
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
                elif mode == 'show_time':
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
                else:  # mode == 'show_confidence'
                    if result.is_final:
                        for f in output_file:
                            f.write(f'## {transcript}\n')
                            f.write(f'Confidence: {result.alternatives[0].confidence:9.4f}\n')
                    else:
                        for f in output_file:
                            f.write(f'>> {transcript}\n')
                            f.write(f'Stability: {result.stability:9.4f}\n')
            if mode == 'simple':
                if show_intermediate and partial_transcript != '':
                    overwrite_chars = ' ' * (num_chars_printed - len(partial_transcript))
                    for i, f in enumerate(output_file):
                        f.write(">> " + partial_transcript + ('\n' if file_opened[i] else overwrite_chars + '\r'))
                    num_chars_printed = len(partial_transcript) + 3
            elif mode == 'show_time':
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


class ASR_Client:
    def __init__(self, auth: Auth) -> None:
        self.auth = auth
        self.stub = rasr_srv.RivaSpeechRecognitionStub(self.auth.channel)

    @staticmethod
    def _update_recognition_config(
        config: Union[rasr.StreamingRecognitionConfig, rasr.RecognitionConfig],
        rate: Optional[int],
        boosted_lm_words: Optional[List[str]],
        boosted_lm_score: float,
    ) -> None:
        inner_config: rasr.RecognitionConfig = config if isinstance(config, rasr.RecognitionConfig) else config.config
        if rate is not None:
            inner_config.sample_rate_hertz = rate
        if boosted_lm_words is not None:
            speech_context = rasr.SpeechContext()
            speech_context.phrases.extend(boosted_lm_words)
            speech_context.boost = boosted_lm_score
            inner_config.speech_contexts.append(speech_context)

    def streaming_recognize_file_generator(
        self,
        input_file: os.PathLike,
        simulate_realtime: bool,
        streaming_config: rasr.StreamingRecognitionConfig,
        boosted_lm_words: Optional[List[str]] = None,
        boosted_lm_score: float = 4.0,
        num_iterations: int = 1,
        file_streaming_chunk: int = 1600,
        output_device_index: Optional[int] = None,
        sound: bool = False,
    ) -> Generator[StreamingRecognizeResponse, None, None]:
        if simulate_realtime and sound:
            raise ValueError(f"It is not possible to set `simulate_realtime` and `sound` parameters to `True`.")
        wav_parameters = get_wav_file_parameters(input_file)
        self._update_recognition_config(
            config=streaming_config,
            rate=wav_parameters['framerate'],
            boosted_lm_words=boosted_lm_words,
            boosted_lm_score=boosted_lm_score,
        )
        if sound:
            with OutputAudioStream(
                output_device_index,
                wav_parameters['sampwidth'],
                wav_parameters['nchannels'],
                wav_parameters['framerate'],
            ) as output_audio_stream:
                for response in self.stub.StreamingRecognize(
                    audio_requests_from_file_generator(
                        input_file,
                        streaming_config,
                        num_iterations,
                        simulate_realtime,
                        wav_parameters['framerate'],
                        file_streaming_chunk,
                        output_audio_stream,
                    ),
                    metadata=self.auth.get_auth_metadata(),
                ):
                    yield response
        else:
            for response in self.stub.StreamingRecognize(
                audio_requests_from_file_generator(
                    input_file,
                    streaming_config,
                    num_iterations,
                    simulate_realtime,
                    wav_parameters['framerate'],
                    file_streaming_chunk,
                    None,
                ),
                metadata=self.auth.get_auth_metadata(),
            ):
                yield response

    def streaming_recognize_microphone_generator(
        self,
        input_device: int,
        streaming_config: rasr.StreamingRecognitionConfig,
        boosted_lm_words: Optional[List[str]] = None,
        boosted_lm_score: float = 4.0,
        file_streaming_chunk: int = 1600,
        audio_frame_rate: Optional[int] = None,
    ) -> Generator[StreamingRecognizeResponse, None, None]:
        self._update_recognition_config(
            config=streaming_config,
            rate=audio_frame_rate,
            boosted_lm_words=boosted_lm_words,
            boosted_lm_score=boosted_lm_score,
        )
        with MicrophoneStream(audio_frame_rate, file_streaming_chunk, device=input_device) as stream:
            audio_generator = stream.generator()
            requests = (rasr.StreamingRecognizeRequest(audio_content=content) for content in audio_generator)

            def build_generator(cfg, gen):
                yield rasr.StreamingRecognizeRequest(streaming_config=cfg)
                for x in gen:
                    yield x

            for response in self.stub.StreamingRecognize(
                build_generator(streaming_config, requests), metadata=self.auth.get_auth_metadata(),
            ):
                yield response

    def offline_recognize(
        self,
        input_file: os.PathLike,
        config: rasr.RecognitionConfig,
        boosted_lm_words: Optional[List[str]] = None,
        boosted_lm_score: float = 4.0,
    ) -> RecognizeResponse:
        wav_parameters = get_wav_file_parameters(input_file)
        self._update_recognition_config(
            config=config,
            rate=wav_parameters['framerate'],
            boosted_lm_words=boosted_lm_words,
            boosted_lm_score=boosted_lm_score,
        )
        with open(input_file, 'rb') as fh:
            data = fh.read()
        request = rasr.RecognizeRequest(config=config, audio=data)
        response = self.stub.Recognize(request, metadata=self.auth.get_auth_metadata())
        return response
