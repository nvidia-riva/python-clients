# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

"""Normalized ASR transcripts and file export helpers."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

import riva.client.proto.riva_asr_pb2 as rasr


TRANSCRIPT_OUTPUT_FORMATS = ("json", "srt", "vtt")


@dataclass
class TranscriptWord:
    word: str
    start_time_ms: int
    end_time_ms: int
    confidence: float = 0.0
    speaker_tag: int = 0
    language_code: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "word": self.word,
            "start_time_ms": self.start_time_ms,
            "end_time_ms": self.end_time_ms,
            "confidence": self.confidence,
            "speaker_tag": self.speaker_tag,
            "language_code": self.language_code,
        }


@dataclass
class TranscriptAlternative:
    transcript: str
    confidence: float = 0.0
    words: List[TranscriptWord] = field(default_factory=list)
    language_codes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transcript": self.transcript,
            "confidence": self.confidence,
            "words": [word.to_dict() for word in self.words],
            "language_codes": self.language_codes,
        }


@dataclass
class TranscriptSegment:
    transcript: str
    start_time_ms: Optional[int] = None
    end_time_ms: Optional[int] = None
    confidence: float = 0.0
    speaker_tag: Optional[int] = None
    language_code: str = ""
    words: List[TranscriptWord] = field(default_factory=list)
    alternatives: List[TranscriptAlternative] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transcript": self.transcript,
            "start_time_ms": self.start_time_ms,
            "end_time_ms": self.end_time_ms,
            "confidence": self.confidence,
            "speaker_tag": self.speaker_tag,
            "language_code": self.language_code,
            "words": [word.to_dict() for word in self.words],
            "alternatives": [
                alternative.to_dict() for alternative in self.alternatives
            ],
        }


@dataclass
class Transcript:
    segments: List[TranscriptSegment] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(
            segment.transcript.strip()
            for segment in self.segments
            if segment.transcript.strip()
        )

    def add_grpc_result(
        self,
        result: Union[rasr.SpeechRecognitionResult, rasr.StreamingRecognitionResult],
    ) -> None:
        if not result.alternatives:
            return
        alternatives = [
            _grpc_alternative(alternative) for alternative in result.alternatives
        ]
        top_alternative = alternatives[0]
        self.segments.append(_segment_from_alternative(top_alternative, alternatives))

    def add_realtime_event(self, event: Dict[str, Any]) -> None:
        transcript = event.get("transcript", "")
        words = [
            _realtime_word(word)
            for word in event.get("words_info", {}).get("words", [])
        ]
        alternative = TranscriptAlternative(transcript=transcript, words=words)
        segment = _segment_from_alternative(alternative, [alternative])

        # Some servers repeat the final completed event with is_last_result=true.
        # Avoid emitting an identical subtitle cue twice.
        if self.segments and self.segments[-1].to_dict() == segment.to_dict():
            return
        self.segments.append(segment)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": "1.0",
            "transcript": self.text,
            "segments": [segment.to_dict() for segment in self.segments],
        }


def collect_streaming_transcript(
    responses: Iterable[rasr.StreamingRecognizeResponse],
    transcript: Transcript,
) -> Iterable[rasr.StreamingRecognizeResponse]:
    """Collect final results while yielding every response unchanged."""
    for response in responses:
        for result in response.results:
            if result.is_final:
                transcript.add_grpc_result(result)
        yield response


def transcript_from_offline_response(response: rasr.RecognizeResponse) -> Transcript:
    transcript = Transcript()
    for result in response.results:
        transcript.add_grpc_result(result)
    return transcript


def resolve_output_format(
    output_file: Union[str, os.PathLike],
    output_format: Optional[str] = None,
) -> str:
    if output_format:
        normalized_format = output_format.lower()
    else:
        normalized_format = Path(output_file).suffix.lower().lstrip(".")
    if normalized_format not in TRANSCRIPT_OUTPUT_FORMATS:
        raise ValueError(
            "Unable to determine transcript output format. Use a .json, .srt, or .vtt "
            "file extension, or pass --output-format."
        )
    return normalized_format


def write_transcript(
    transcript: Transcript,
    output_file: Union[str, os.PathLike],
    output_format: Optional[str] = None,
) -> None:
    output_format = resolve_output_format(output_file, output_format)
    output_path = Path(output_file).expanduser()
    if output_format == "json":
        rendered = json.dumps(transcript.to_dict(), ensure_ascii=False, indent=2) + "\n"
    elif output_format == "srt":
        rendered = _render_subtitles(transcript, webvtt=False)
    else:
        rendered = _render_subtitles(transcript, webvtt=True)
    output_path.write_text(rendered, encoding="utf-8")


def _grpc_word(word: rasr.WordInfo) -> TranscriptWord:
    return TranscriptWord(
        word=word.word,
        start_time_ms=word.start_time,
        end_time_ms=word.end_time,
        confidence=word.confidence,
        speaker_tag=word.speaker_tag,
        language_code=word.language_code,
    )


def _grpc_alternative(
    alternative: rasr.SpeechRecognitionAlternative,
) -> TranscriptAlternative:
    return TranscriptAlternative(
        transcript=alternative.transcript,
        confidence=alternative.confidence,
        words=[_grpc_word(word) for word in alternative.words],
        language_codes=list(alternative.language_code),
    )


def _realtime_word(word: Dict[str, Any]) -> TranscriptWord:
    # Realtime ASR word offsets are seconds; gRPC word offsets are milliseconds.
    return TranscriptWord(
        word=word.get("word", ""),
        start_time_ms=round(float(word.get("start_time", 0.0)) * 1000),
        end_time_ms=round(float(word.get("end_time", 0.0)) * 1000),
        confidence=float(word.get("confidence", 0.0)),
        speaker_tag=int(word.get("speaker_tag", 0)),
        language_code=word.get("language_code", ""),
    )


def _segment_from_alternative(
    alternative: TranscriptAlternative,
    alternatives: List[TranscriptAlternative],
) -> TranscriptSegment:
    words = alternative.words
    speaker_tags = {word.speaker_tag for word in words}
    language_codes = {word.language_code for word in words if word.language_code}
    return TranscriptSegment(
        transcript=alternative.transcript,
        start_time_ms=words[0].start_time_ms if words else None,
        end_time_ms=words[-1].end_time_ms if words else None,
        confidence=alternative.confidence,
        speaker_tag=next(iter(speaker_tags)) if len(speaker_tags) == 1 else None,
        language_code=next(iter(language_codes)) if len(language_codes) == 1 else "",
        words=words,
        alternatives=alternatives,
    )


def _render_subtitles(transcript: Transcript, webvtt: bool) -> str:
    lines = ["WEBVTT", ""] if webvtt else []
    cue_index = 1
    for segment in transcript.segments:
        text = " ".join(segment.transcript.split())
        if not text:
            continue
        if segment.start_time_ms is None or segment.end_time_ms is None:
            raise ValueError(
                "SRT and VTT export require word time offsets, but a finalized transcript "
                "segment did not contain them."
            )
        if segment.start_time_ms < 0 or segment.end_time_ms < segment.start_time_ms:
            raise ValueError(
                "SRT and VTT export require non-negative, ordered timestamps."
            )

        # Transducer models can return equal word timestamps. Keep such cues valid
        # without inventing a perceptible duration.
        end_time_ms = max(segment.end_time_ms, segment.start_time_ms + 1)
        lines.append(str(cue_index))
        lines.append(
            "{} --> {}".format(
                _format_timestamp(segment.start_time_ms, webvtt),
                _format_timestamp(end_time_ms, webvtt),
            )
        )
        lines.append(text)
        lines.append("")
        cue_index += 1
    return "\n".join(lines)


def _format_timestamp(timestamp_ms: int, webvtt: bool) -> str:
    hours, remainder = divmod(timestamp_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1_000)
    separator = "." if webvtt else ","
    return "{:02d}:{:02d}:{:02d}{}{:03d}".format(
        hours, minutes, seconds, separator, milliseconds
    )
