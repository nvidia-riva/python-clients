# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import json

import pytest

import riva.client.proto.riva_asr_pb2 as rasr
from riva.client.transcript import (
    Transcript,
    collect_streaming_transcript,
    resolve_output_format,
    transcript_from_offline_response,
    write_transcript,
)


def make_alternative(text="hello", start_time=1000, end_time=1500):
    return rasr.SpeechRecognitionAlternative(
        transcript=text,
        confidence=0.9,
        words=[
            rasr.WordInfo(
                word=text,
                start_time=start_time,
                end_time=end_time,
                confidence=0.8,
                speaker_tag=1,
                language_code="en-US",
            )
        ],
        language_code=["en-US"],
    )


def test_collect_streaming_transcript_ignores_interim_results():
    transcript = Transcript()
    responses = [
        rasr.StreamingRecognizeResponse(
            results=[
                rasr.StreamingRecognitionResult(
                    alternatives=[make_alternative("partial")]
                )
            ]
        ),
        rasr.StreamingRecognizeResponse(
            results=[
                rasr.StreamingRecognitionResult(
                    alternatives=[make_alternative("final")],
                    is_final=True,
                )
            ]
        ),
    ]

    assert list(collect_streaming_transcript(responses, transcript)) == responses
    assert transcript.text == "final"
    assert len(transcript.segments) == 1


def test_offline_response_preserves_alternatives():
    response = rasr.RecognizeResponse(
        results=[
            rasr.SpeechRecognitionResult(
                alternatives=[make_alternative(), make_alternative("yellow")]
            )
        ]
    )

    transcript = transcript_from_offline_response(response)

    assert transcript.text == "hello"
    assert [
        alternative.transcript for alternative in transcript.segments[0].alternatives
    ] == ["hello", "yellow"]


def test_realtime_event_converts_seconds_to_milliseconds_and_accumulates():
    transcript = Transcript()
    transcript.add_realtime_event(
        {
            "transcript": "hello",
            "words_info": {
                "words": [
                    {
                        "word": "hello",
                        "start_time": 1.25,
                        "end_time": 1.75,
                        "confidence": 0.9,
                        "speaker_tag": 2,
                    }
                ]
            },
        }
    )
    transcript.add_realtime_event({"transcript": "world", "words_info": {"words": []}})

    assert transcript.text == "hello world"
    assert transcript.segments[0].start_time_ms == 1250
    assert transcript.segments[0].end_time_ms == 1750


def test_realtime_event_deduplicates_repeated_final_event():
    transcript = Transcript()
    event = {"transcript": "hello", "words_info": {"words": []}}

    transcript.add_realtime_event(event)
    transcript.add_realtime_event(event)

    assert len(transcript.segments) == 1


def test_json_export_is_one_valid_document(tmp_path):
    transcript = transcript_from_offline_response(
        rasr.RecognizeResponse(
            results=[rasr.SpeechRecognitionResult(alternatives=[make_alternative()])]
        )
    )
    output_file = tmp_path / "transcript.json"

    write_transcript(transcript, output_file)

    exported = json.loads(output_file.read_text(encoding="utf-8"))
    assert exported["schema_version"] == "1.0"
    assert exported["transcript"] == "hello"
    assert exported["segments"][0]["words"][0]["start_time_ms"] == 1000


@pytest.mark.parametrize(
    "extension, expected_timestamp, expected_prefix",
    [
        ("srt", "00:00:01,000 --> 00:00:01,500", "1\n"),
        ("vtt", "00:00:01.000 --> 00:00:01.500", "WEBVTT\n\n1\n"),
    ],
)
def test_subtitle_export(extension, expected_timestamp, expected_prefix, tmp_path):
    transcript = transcript_from_offline_response(
        rasr.RecognizeResponse(
            results=[rasr.SpeechRecognitionResult(alternatives=[make_alternative()])]
        )
    )
    output_file = tmp_path / ("transcript." + extension)

    write_transcript(transcript, output_file)

    rendered = output_file.read_text(encoding="utf-8")
    assert rendered.startswith(expected_prefix)
    assert expected_timestamp in rendered
    assert rendered.endswith("hello\n")


def test_subtitle_export_rejects_missing_word_timestamps(tmp_path):
    transcript = Transcript()
    transcript.add_realtime_event({"transcript": "hello"})

    with pytest.raises(ValueError, match="require word time offsets"):
        write_transcript(transcript, tmp_path / "transcript.srt")


def test_resolve_output_format_requires_supported_extension():
    assert resolve_output_format("transcript.SRT") == "srt"
    assert resolve_output_format("transcript.data", "vtt") == "vtt"
    with pytest.raises(ValueError, match="Unable to determine"):
        resolve_output_format("transcript.txt")
