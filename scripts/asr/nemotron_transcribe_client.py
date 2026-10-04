# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT
"""JSONL dataset client for Nemotron Transcribe's chat-completions API.

Uses only the Python standard library. Audio is base64-encoded incrementally,
with Content-Length, not HTTP chunked transfer or a large shell argument.
"""

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from collections import deque
import http.client
import json
import math
import os
from pathlib import Path
import re
import ssl
import sys
import time
from urllib.parse import urlsplit
import wave


DEFAULT_PROMPT = (
    "Transcribe the audio in the same language as spoken. Do not translate."
)
SPEAKER_TAG = re.compile(r"<spk:(\d+)>", re.IGNORECASE)
CHUNK_BYTES = 3 * 16384  # No padding until the last base64 chunk.


def boolean(value):
    if isinstance(value, bool):
        return value
    if value.lower() in ("true", "1", "yes"):
        return True
    if value.lower() in ("false", "0", "no"):
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def positive_int(value):
    value = int(value)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def positive_float(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return value


def add_boolean(parser, name, aliases=()):
    group = parser.add_mutually_exclusive_group()
    flags = list(dict.fromkeys(["--" + name, "--" + name.replace("-", "_"), *aliases]))
    group.add_argument(*flags,
                       dest=name.replace("-", "_"), nargs="?", const=True,
                       default=None, type=boolean)
    group.add_argument("--no-" + name, dest=name.replace("-", "_"), action="store_false")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--input-manifest", "--input_manifest", required=True, type=Path)
    parser.add_argument("--output-manifest", "--output_manifest", required=True, type=Path)
    parser.add_argument("--server", "--server-url", "--server_url", default="http://localhost:9000",
                        help="HTTP(S) origin, /v1 base URL, or full chat-completions URL")
    parser.add_argument("--model-name", "--model", default="nvidia-nemotron-transcribe-hr9a")
    parser.add_argument("--prompt", help="Fallback instruction when a row has no prompt")
    parser.add_argument("--language-code", "--language", help="Language hint; timestamps require English")
    add_boolean(parser, "verbatim-transcripts", ("--verbatim_transcrtipts",))
    add_boolean(parser, "automatic-punctuation")
    add_boolean(parser, "diarization", ("--speaker-diarization", "--speaker_diarization"))
    parser.add_argument("--word-timestamps", "--word_timestamps", "--word-time-offsets",
                        action="store_true", help="Request real aligned words (English only)")
    parser.add_argument("--subtitle-format", choices=("srt", "vtt"),
                        help="Request server subtitles; implies word timestamps")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--num-clients", type=positive_int, default=1,
                        help="Concurrent requests; start with 1 for long recordings")
    parser.add_argument("--connect-timeout", type=positive_float, default=10)
    parser.add_argument("--request-timeout", type=positive_float, default=7200,
                        help="Socket send/read inactivity timeout, seconds (not a total deadline)")
    parser.add_argument("--max-audio-seconds", type=positive_float, default=3600)
    parser.add_argument("--max-request-bytes", type=positive_int, default=256 * 1024 * 1024)
    parser.add_argument("--max-response-bytes", type=positive_int, default=64 * 1024 * 1024)
    parser.add_argument("--api-key-env",
                        help="Explicitly send a bearer token from this environment variable; no auth by default")
    parser.add_argument("--ssl-root-cert", type=Path, help="CA bundle for HTTPS; verification stays enabled")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing output manifest")
    parser.add_argument("--include-raw-response", action="store_true")
    parser.add_argument("--quiet", action="store_true", help="Suppress transcript display, not errors/summary")
    args = parser.parse_args(argv)
    args.word_timestamps = args.word_timestamps or bool(args.subtitle_format)
    if args.word_timestamps and args.language_code:
        if re.split(r"[-_]", args.language_code)[0].lower() != "en":
            parser.error("word timestamps/subtitles currently require an English language hint")
    if args.seed is not None and not -(2 ** 63) <= args.seed < 2 ** 63:
        parser.error("seed must be a signed 64-bit integer")
    try:
        args.endpoint = endpoint_url(args.server)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def endpoint_url(server):
    url = urlsplit(server)
    if url.scheme not in ("http", "https") or not url.hostname:
        raise ValueError("server must be an http:// or https:// URL")
    if url.username or url.password or url.query or url.fragment:
        raise ValueError("server URL must not contain credentials, query parameters, or a fragment")
    url.port  # Validate the port now rather than during a dataset request.
    path = url.path.rstrip("/")
    if path in ("", "/v1"):
        path = "/v1/chat/completions"
    elif not path.endswith("/v1/chat/completions"):
        raise ValueError("server URL must be an origin, /v1, or /v1/chat/completions endpoint")
    return url._replace(path=path).geturl()


def build_prompt(row, args):
    prompt = row.get("prompt", args.prompt)
    if prompt is not None and not isinstance(prompt, str):
        raise ValueError("prompt must be a string")
    prompt = (prompt or DEFAULT_PROMPT).strip()
    if "<|audio|>" in prompt:
        raise ValueError("do not include the internal <|audio|> placeholder in prompts")
    clauses = [prompt]
    if args.verbatim_transcripts is True:
        clauses.append("Produce a verbatim transcript, preserving spoken words, fillers and repetitions.")
    elif args.verbatim_transcripts is False:
        clauses.append("Produce a readable non-verbatim transcript, omitting fillers and false starts.")
    if args.automatic_punctuation is True:
        clauses.append("Use appropriate punctuation and capitalization.")
    elif args.automatic_punctuation is False:
        clauses.append("Do not add punctuation. Output only words separated by spaces, "
                       "without commas or sentence-final periods.")
    if args.diarization is True:
        clauses.append("Put speaker tags <spk:0> <spk:1> on the transcription. "
                       "Include a speaker tag before the first word and at every speaker change, "
                       "using a consistent tag for each speaker.")
    elif args.diarization is False:
        clauses.append("Do not include speaker tags.")
    return " ".join(clauses)


def audio_info(path, max_seconds):
    with wave.open(str(path), "rb") as audio:
        if audio.getsampwidth() != 2 or audio.getcomptype() != "NONE":
            raise ValueError("input must be 16-bit PCM WAV; convert unsupported encodings explicitly first")
        frames = audio.getnframes()
        if frames <= 0:
            raise ValueError("audio is empty")
        duration = frames / audio.getframerate()
        if duration < 0.02:
            raise ValueError("audio must contain at least 20 milliseconds of signal")
        if duration > max_seconds:
            raise ValueError("audio duration {:.3f}s exceeds {:.3f}s limit".format(duration, max_seconds))
        # A valid header is not sufficient: reject a truncated data section before upload.
        bytes_per_frame = audio.getnchannels() * audio.getsampwidth()
        remaining = frames * bytes_per_frame
        while remaining:
            chunk = audio.readframes(min(remaining // bytes_per_frame, max(1, CHUNK_BYTES // bytes_per_frame)))
            if not chunk:
                raise ValueError("WAV data is truncated")
            remaining -= len(chunk)
    return duration


def body_parts(prompt, args):
    options = {"word_timestamps": args.word_timestamps}
    if args.language_code:
        options["language"] = args.language_code
    if args.seed is not None:
        options["seed"] = args.seed
    if args.subtitle_format:
        options["subtitle_format"] = args.subtitle_format
    # Build valid JSON around the only streamed value, the base64 audio string.
    prefix = ('{"model":' + json.dumps(args.model_name) + ',"n3nt":' + json.dumps(options)
              + ',"messages":[{"role":"user","content":[{"type":"text","text":'
              + json.dumps(prompt) + '},{"type":"input_audio","input_audio":{"data":"').encode("utf-8")
    suffix = b'","format":"wav"}}]}]}'
    return prefix, suffix


def streamed_body(audio, size, prefix, suffix):
    yield prefix
    remaining = size
    while remaining:
        chunk = audio.read(min(CHUNK_BYTES, remaining))
        if not chunk or len(chunk) != min(CHUNK_BYTES, remaining):
            raise ValueError("audio changed or was truncated during upload")
        remaining -= len(chunk)
        yield base64.b64encode(chunk)
    if audio.read(1):
        raise ValueError("audio grew during upload")
    yield suffix


def post_audio(path, prompt, args, timings=None):
    timings = timings if timings is not None else {}
    prefix, suffix = body_parts(prompt, args)
    url = urlsplit(args.endpoint)
    if url.scheme == "https":
        context = ssl.create_default_context(cafile=str(args.ssl_root_cert) if args.ssl_root_cert else None)
        connection = http.client.HTTPSConnection(url.hostname, url.port, timeout=args.connect_timeout, context=context)
    else:
        connection = http.client.HTTPConnection(url.hostname, url.port, timeout=args.connect_timeout)
    try:
        with path.open("rb") as audio:
            size = os.fstat(audio.fileno()).st_size
            length = len(prefix) + 4 * ((size + 2) // 3) + len(suffix)
            if length > args.max_request_bytes:
                raise ValueError("encoded request is {} bytes, exceeding {} byte limit".format(length, args.max_request_bytes))
            headers = {"Content-Type": "application/json", "Content-Length": str(length)}
            token = os.environ.get(args.api_key_env) if args.api_key_env else None
            if token:
                headers["Authorization"] = "Bearer " + token
            send_started = time.monotonic()
            connection.connect()
            connection.sock.settimeout(args.request_timeout)
            connection.request("POST", url.path, body=streamed_body(audio, size, prefix, suffix), headers=headers)
            send_finished = time.monotonic()
            timings.update(request_bytes=length, client_send_seconds=send_finished - send_started)
            response = connection.getresponse()
            headers_received = time.monotonic()
            timings["response_headers_wait_seconds"] = headers_received - send_finished
            data = response.read(args.max_response_bytes + 1)
            timings.update(response_bytes=len(data), response_read_seconds=time.monotonic() - headers_received,
                           http_status=response.status)
            if len(data) > args.max_response_bytes:
                raise ValueError("response exceeds configured byte limit")
            if response.status != 200:
                raise ValueError("HTTP {}: {}".format(response.status, data.decode("utf-8", "replace")[:1000]))
            return json.loads(data)
    finally:
        connection.close()


def speaker_turns(text):
    turns, speaker, start = [], "unknown", 0
    for match in SPEAKER_TAG.finditer(text):
        words = text[start:match.start()].strip()
        if words:
            turns.append({"speaker": speaker, "text": words})
        speaker, start = "spk:" + match.group(1), match.end()
    if text[start:].strip():
        turns.append({"speaker": speaker, "text": text[start:].strip()})
    return turns if SPEAKER_TAG.search(text) else []


def parse_response(response, timestamps_requested=False, speakers_requested=False):
    if not isinstance(response, dict) or response.get("error"):
        raise ValueError("invalid success response or API error: {}".format(str(response)[:1000]))
    try:
        choice = response["choices"][0]
        raw_text = choice["message"]["content"]
        if not isinstance(raw_text, str):
            raise ValueError("assistant content must be a string")
        payload = response.get("n3nt", {})
        if not isinstance(payload, dict):
            raise ValueError("n3nt response must be an object")
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("response has no assistant transcript") from exc
    warnings = []
    if speakers_requested and raw_text.strip() and not SPEAKER_TAG.search(raw_text):
        warnings.append("speaker tags were requested but absent from the transcript; "
                        "any aligned speaker labels are retained in words")
    if choice.get("finish_reason") != "stop":
        warnings.append("unexpected finish_reason: {}".format(choice.get("finish_reason")))
    if payload.get("transcript_origin", "llm") != "llm":
        warnings.append("degraded transcript origin: {}".format(payload["transcript_origin"]))
    alignment = payload.get("word_timestamp_alignment", {})
    if not isinstance(alignment, dict):
        raise ValueError("word_timestamp_alignment must be an object")
    words = payload.get("words", [])
    if not isinstance(words, list):
        raise ValueError("words must be an array")
    for word in words:
        if not isinstance(word, dict) or not isinstance(word.get("word"), str):
            raise ValueError("each aligned word must contain a word string")
        start, end = word.get("start"), word.get("end")
        if (isinstance(start, bool) or isinstance(end, bool)
                or not isinstance(start, (int, float)) or not isinstance(end, (int, float))
                or not math.isfinite(start) or not math.isfinite(end) or not 0 <= start <= end):
            raise ValueError("aligned word times must be finite, nonnegative, and ordered")
    if timestamps_requested and alignment.get("status") != "aligned":
        warnings.append("word alignment unavailable: {}".format(alignment.get("failure_reason", "not reported")))
    plausibility = alignment.get("transcript_plausibility") or {}
    if plausibility.get("verdict") not in (None, "plausible"):
        warnings.append("transcript plausibility: {}".format(plausibility["verdict"]))
    text = re.sub(r"\s+", " ", SPEAKER_TAG.sub("", raw_text)).strip()
    return {"text": text, "raw_text": raw_text, "speaker_turns": speaker_turns(raw_text),
            "words": words, "n3nt": payload, "warnings": warnings,
            "finish_reason": choice.get("finish_reason"), "usage": response.get("usage"),
            "response_id": response.get("id")}


def process_row(line_number, line, manifest_dir, args):
    started = time.monotonic()
    output = {"manifest_line": line_number}
    try:
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("manifest row must be a JSON object")
        output["input"] = row  # Preserve reference text, prompt, IDs and all other metadata.
        candidates = [row[key] for key in ("audio_filepath", "audio_path") if key in row]
        if not candidates or any(not isinstance(p, str) or not p for p in candidates):
            raise ValueError("row requires a nonempty audio_filepath (or audio_path) string")
        if len(set(candidates)) != 1:
            raise ValueError("audio_filepath and audio_path disagree")
        path = Path(candidates[0]).expanduser()
        if not path.is_absolute():
            path = manifest_dir / path
        path = path.resolve()
        prompt = build_prompt(row, args)
        output.update(audio_filepath=str(path), effective_prompt=prompt)
        output["audio_duration_seconds"] = audio_info(path, args.max_audio_seconds)
        output["request_started_monotonic"] = time.monotonic()
        output["request_timings"] = {}
        try:
            response = post_audio(path, prompt, args, timings=output["request_timings"])
        finally:
            output["request_finished_monotonic"] = time.monotonic()
            output["request_elapsed_seconds"] = output["request_finished_monotonic"] - output["request_started_monotonic"]
        output["result"] = parse_response(response, args.word_timestamps, args.diarization is True)
        output["request_rtfx"] = output["audio_duration_seconds"] / max(output["request_elapsed_seconds"], 1e-9)
        output["status"] = "warning" if output["result"]["warnings"] else "ok"
        if args.include_raw_response:
            output["raw_response"] = response
    except Exception as exc:
        output.update(status="error", error={"type": type(exc).__name__, "message": str(exc)})
        if "input" not in output:
            output["input_line"] = line.rstrip("\n")
    output["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return output


def manifest_rows(manifest):
    for number, line in enumerate(manifest, 1):
        if line.strip():
            yield number, line


def dataset_results(manifest, manifest_dir, args):
    # Bounded submission and stable output order: never load the dataset in memory.
    rows = iter(manifest_rows(manifest))
    with ThreadPoolExecutor(max_workers=args.num_clients) as executor:
        pending = deque()
        for _ in range(args.num_clients):
            item = next(rows, None)
            if item is not None:
                pending.append(executor.submit(process_row, *item, manifest_dir, args))
        while pending:
            yield pending.popleft().result()
            item = next(rows, None)
            if item is not None:
                pending.append(executor.submit(process_row, *item, manifest_dir, args))


def display(output, quiet=False):
    print("[line {}] {} ({:.2f}s) {}".format(output["manifest_line"], output["status"],
          output["elapsed_seconds"], output.get("audio_filepath", "")), file=sys.stderr)
    if output["status"] == "error":
        print(output["error"]["message"], file=sys.stderr)
        return
    result = output["result"]
    for warning in result["warnings"]:
        print("Warning: " + warning, file=sys.stderr)
    if quiet:
        return
    if result["speaker_turns"]:
        for turn in result["speaker_turns"]:
            print("{}: {}".format(turn["speaker"], turn["text"]))
    else:
        print(result["text"])
    for word in result["words"]:
        print("  [{:.3f}–{:.3f}] {} {}".format(word["start"], word["end"],
              word.get("speaker", ""), word["word"]))


def main(argv=None):
    args = parse_args(argv)
    input_path = args.input_manifest.expanduser().resolve()
    output_path = args.output_manifest.expanduser().resolve()
    if input_path == output_path or (output_path.exists() and input_path.exists() and os.path.samefile(input_path, output_path)):
        print("Input and output manifests must be different files", file=sys.stderr)
        return 2
    counts = {"ok": 0, "warning": 0, "error": 0}
    audio_seconds, request_start, request_end = 0.0, None, None
    try:
        with input_path.open(encoding="utf-8") as manifest, output_path.open(
                "w" if args.overwrite else "x", encoding="utf-8") as output:
            for record in dataset_results(manifest, input_path.parent, args):
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
                output.flush()  # Each completed result survives an interrupted run.
                counts[record["status"]] += 1
                if "request_started_monotonic" in record:
                    start, end = record["request_started_monotonic"], record["request_finished_monotonic"]
                    request_start = start if request_start is None else min(request_start, start)
                    request_end = end if request_end is None else max(request_end, end)
                if record["status"] == "ok":
                    audio_seconds += record["audio_duration_seconds"]
                display(record, args.quiet)
    except (OSError, ValueError) as exc:
        print("Client error: {}".format(exc), file=sys.stderr)
        return 2
    print("Completed: {ok} ok, {warning} warning, {error} error".format(**counts), file=sys.stderr)
    if request_start is not None:
        window = max(request_end - request_start, 1e-9)
        print("Successful audio: {:.3f}s; request window: {:.3f}s; aggregate RTFx: {:.2f}x".format(
              audio_seconds, window, audio_seconds / window), file=sys.stderr)
    if not sum(counts.values()):
        print("Input manifest contains no records", file=sys.stderr)
        return 2
    return 1 if counts["error"] or counts["warning"] else 0


if __name__ == "__main__":
    sys.exit(main())
