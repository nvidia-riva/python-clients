from typing import Generator

import riva_api.proto.riva_tts_pb2 as rtts
import riva_api.proto.riva_tts_pb2_grpc as rtts_srv
from riva_api import Auth
from riva_api.proto.riva_audio_pb2 import AudioEncoding


class SpeechSynthesisService:
    def __init__(self, auth: Auth) -> None:
        self.auth = auth
        self.stub = rtts_srv.RivaSpeechSynthesisStub(self.auth.channel)

    def synthesize(
        self,
        text: str,
        voice_name: str,
        language_code: str = 'en-US',
        encoding: AudioEncoding = AudioEncoding.LINEAR_PCM,
        sample_rate_hz: int = 44100,
    ) -> rtts.SynthesizeSpeechResponse:
        req = rtts.SynthesizeSpeechRequest(
            text=text,
            voice_name=voice_name,
            language_code=language_code,
            sample_rate_hz=sample_rate_hz,
            encoding=encoding,
        )
        return self.stub.Synthesize(req)

    def synthesize_online(
        self,
        text: str,
        voice_name: str,
        language_code: str = 'en-US',
        encoding: AudioEncoding = AudioEncoding.LINEAR_PCM,
        sample_rate_hz: int = 44100,
    ) -> Generator[rtts.SynthesizeSpeechResponse, None, None]:
        req = rtts.SynthesizeSpeechRequest(
            text=text,
            voice_name=voice_name,
            language_code=language_code,
            sample_rate_hz=sample_rate_hz,
            encoding=encoding,
        )
        return self.stub.SynthesizeOnline(req)
