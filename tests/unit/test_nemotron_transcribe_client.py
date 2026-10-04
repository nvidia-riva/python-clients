# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import base64
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/asr/nemotron_transcribe_client.py"
SPEC = importlib.util.spec_from_file_location("nemotron_transcribe_client", SCRIPT)
client = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(client)


def response(text="Hello world.", **payload):
    return {"id": "chatcmpl-test", "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
            "n3nt": dict({"text": text, "language": "en", "duration": 1, "transcript_origin": "llm"}, **payload)}


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.audio = self.root / "audio.wav"
        self.manifest = self.root / "input.jsonl"
        self.output = self.root / "output.jsonl"
        with wave.open(str(self.audio), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\0\0" * 16000)
        self.args = self.arguments()

    def tearDown(self):
        self.directory.cleanup()

    def arguments(self, *extra):
        return client.parse_args(["--input-manifest", str(self.manifest),
                                  "--output-manifest", str(self.output), *extra])

    def write_manifest(self, rows):
        self.manifest.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    def test_endpoint_forms(self):
        for url in ("http://localhost:9000", "http://localhost:9000/", "http://localhost:9000/v1/",
                    "http://localhost:9000/v1/chat/completions"):
            self.assertEqual(client.endpoint_url(url), "http://localhost:9000/v1/chat/completions")
        self.assertEqual(client.endpoint_url("https://host/prefix/v1/chat/completions"),
                         "https://host/prefix/v1/chat/completions")

    def test_reject_unsafe_or_wrong_urls(self):
        for url in ("localhost:9000", "ftp://host", "http://user:password@host", "http://host?token=x",
                    "http://host/#fragment", "http://host/v1/responses", "http://host:invalid"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                client.endpoint_url(url)

    def test_prompt_precedence(self):
        args = self.arguments("--prompt", "Global instruction.")
        self.assertEqual(client.build_prompt({"prompt": "Row instruction."}, args), "Row instruction.")
        self.assertEqual(client.build_prompt({}, args), "Global instruction.")
        self.assertEqual(client.build_prompt({}, self.args), client.DEFAULT_PROMPT)

    def test_prompt_flags_and_requested_typo(self):
        args = self.arguments("--verbatim_transcrtipts", "--automatic_punctuation", "--speaker-diarization")
        prompt = client.build_prompt({"prompt": "Recognize names."}, args)
        for text in ("Recognize names.", "verbatim", "fillers", "punctuation", "<spk:0>"):
            self.assertIn(text, prompt)

    def test_false_prompt_flags(self):
        args = self.arguments("--verbatim-transcripts", "false", "--no-automatic-punctuation", "--no-diarization")
        prompt = client.build_prompt({}, args)
        self.assertIn("non-verbatim", prompt)
        self.assertIn("Do not add punctuation", prompt)
        self.assertIn("Do not include speaker tags", prompt)

    def test_reject_invalid_prompts(self):
        for prompt in (123, ["text"], "Transcribe <|audio|>"):
            with self.assertRaises(ValueError):
                client.build_prompt({"prompt": prompt}, self.args)

    def test_boolean_and_numeric_validation(self):
        for flags in (("--automatic-punctuation", "maybe"), ("--num-clients", "0"),
                      ("--request-timeout", "nan"), ("--max-audio-seconds", "-1"),
                      ("--seed", str(2 ** 63))):
            with self.subTest(flags=flags), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.arguments(*flags)

    def test_timestamps_require_english(self):
        for language in ("en", "en-US", "EN", "en_GB"):
            self.assertTrue(self.arguments("--word-timestamps", "--language", language).word_timestamps)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.arguments("--word-timestamps", "--language", "es")
        self.assertTrue(self.arguments("--subtitle-format", "srt").word_timestamps)

    def test_stream_body_padding_and_json_escaping(self):
        prompt = 'Names "quoted"\nहैलो'
        prefix, suffix = client.body_parts(prompt, self.arguments("--word-timestamps", "--seed", "42"))
        for size in (1, 2, 3, client.CHUNK_BYTES - 1, client.CHUNK_BYTES, client.CHUNK_BYTES + 1, 2 * client.CHUNK_BYTES + 2):
            raw = b"x" * size
            body = b"".join(client.streamed_body(io.BytesIO(raw), size, prefix, suffix))
            request = json.loads(body)
            self.assertEqual(len(body), len(prefix) + 4 * ((size + 2) // 3) + len(suffix))
            parts = request["messages"][0]["content"]
            self.assertEqual(parts[0]["text"], prompt)
            self.assertEqual(base64.b64decode(parts[1]["input_audio"]["data"]), raw)
            self.assertEqual(request["n3nt"], {"word_timestamps": True, "seed": 42})

    def test_changed_file_rejected(self):
        for actual, expected in ((b"x", 2), (b"xx", 1)):
            with self.assertRaises(ValueError):
                list(client.streamed_body(io.BytesIO(actual), expected, b"", b""))

    def test_audio_validation(self):
        self.assertEqual(client.audio_info(self.audio, 3600), 1)
        with self.assertRaises(ValueError):
            client.audio_info(self.audio, 0.5)
        with wave.open(str(self.audio), "wb") as audio:
            audio.setnchannels(2)
            audio.setsampwidth(1)
            audio.setframerate(16000)
            audio.writeframes(b"\0" * 64000)
        with self.assertRaises(ValueError):
            client.audio_info(self.audio, 3600)

    def test_server_resampled_wav_allowed(self):
        with wave.open(str(self.audio), "wb") as audio:
            audio.setnchannels(2)
            audio.setsampwidth(2)
            audio.setframerate(48000)
            audio.writeframes(b"\0" * 192000)
        self.assertEqual(client.audio_info(self.audio, 3600), 1)

    def test_truncated_wav(self):
        with self.audio.open("r+b") as audio:
            audio.truncate(100)
        with self.assertRaisesRegex(ValueError, "truncated"):
            client.audio_info(self.audio, 3600)

    def test_response_speakers_and_alignment(self):
        words = [{"word": "Hello", "word_index": 0, "start": 0.1, "end": 0.3, "speaker": "spk:0"}]
        parsed = client.parse_response(response("<spk:0> Hello <spk:1> world.", words=words,
                    word_timestamp_alignment={"status": "aligned"}), True)
        self.assertEqual(parsed["text"], "Hello world.")
        self.assertEqual(parsed["speaker_turns"], [{"speaker": "spk:0", "text": "Hello"},
                                                  {"speaker": "spk:1", "text": "world."}])
        self.assertEqual(parsed["words"], words)
        self.assertFalse(parsed["warnings"])

    def test_alignment_and_fallback_warnings(self):
        parsed = client.parse_response(response(transcript_origin="ctc_fallback",
                    word_timestamp_alignment={"status": "unavailable", "failure_reason": "no_speech_evidence"}), True)
        self.assertEqual(len(parsed["warnings"]), 2)
        self.assertEqual(parsed["words"], [])  # Never manufacture word times.

    def test_empty_transcript_is_valid(self):
        self.assertEqual(client.parse_response(response(""))["text"], "")

    def test_missing_requested_speaker_tags_warns(self):
        parsed = client.parse_response(response(), speakers_requested=True)
        self.assertIn("speaker tags were requested", parsed["warnings"][0])
        self.assertEqual(client.parse_response(response(""), speakers_requested=True)["warnings"], [])

    def test_malformed_words_rejected_before_display(self):
        for words in (None, {}, ["bad"], [{"word": "Hi", "start": -1, "end": 2}],
                      [{"word": "Hi", "start": float("nan"), "end": 2}],
                      [{"word": "Hi", "start": 2, "end": 1}]):
            with self.subTest(words=words), self.assertRaises(ValueError):
                client.parse_response(response(words=words))

    def test_rtfx_and_request_window_fields(self):
        with patch.object(client, "post_audio", return_value=response()):
            output = client.process_row(1, json.dumps({"audio_filepath": str(self.audio)}), self.root, self.args)
        self.assertEqual(output["request_elapsed_seconds"],
                         output["request_finished_monotonic"] - output["request_started_monotonic"])
        self.assertGreater(output["request_rtfx"], 0)
        self.assertAlmostEqual(output["request_rtfx"] * output["request_elapsed_seconds"], 1)

    def test_environment_token_not_sent_by_default(self):
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "must-not-send"}), patch.object(client.http.client, "HTTPConnection") as constructor:
            connection = constructor.return_value
            connection.getresponse.return_value.status = 200
            connection.getresponse.return_value.read.return_value = json.dumps(response()).encode()
            client.post_audio(self.audio, "Transcribe.", self.args)
        headers = connection.request.call_args[1]["headers"]
        self.assertNotIn("Authorization", headers)

    def test_malformed_response_rejected(self):
        for body in ({}, {"choices": []}, {"error": {"message": "bad"}}, {"choices": [{"message": {"content": None}}]}):
            with self.assertRaises(ValueError):
                client.parse_response(body)

    def test_manifest_metadata_and_relative_path(self):
        row = {"audio_filepath": "audio.wav", "prompt": "Custom.", "text": "reference", "id": 9}
        with patch.object(client, "post_audio", return_value=response()) as post:
            output = client.process_row(7, json.dumps(row), self.root, self.args)
        self.assertEqual(output["input"], row)
        self.assertEqual(output["result"]["text"], "Hello world.")
        self.assertEqual(output["manifest_line"], 7)
        self.assertEqual(post.call_args[0][:2], (self.audio, "Custom."))

    def test_bad_rows_record_errors(self):
        for line in ("not json", "[]", "{}", '{"audio_path":42}',
                     '{"audio_path":"x","audio_filepath":"y"}', '{"audio_path":"missing.wav"}'):
            with self.subTest(line=line):
                self.assertEqual(client.process_row(1, line, self.root, self.args)["status"], "error")

    def test_output_errors_continue_and_exit_nonzero(self):
        self.write_manifest([{"audio_path": "missing.wav"}, {"audio_filepath": "audio.wav", "text": "reference"}])
        with patch.object(client, "post_audio", return_value=response()), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = client.main(["--input-manifest", str(self.manifest), "--output-manifest", str(self.output)])
        records = [json.loads(line) for line in self.output.read_text().splitlines()]
        self.assertEqual(code, 1)
        self.assertEqual([row["status"] for row in records], ["error", "ok"])
        self.assertEqual(records[1]["input"]["text"], "reference")

    def test_refuse_overwriting_input_or_existing_output(self):
        self.write_manifest([{"audio_filepath": "audio.wav"}])
        original = self.manifest.read_text()
        self.output.write_text("existing output")
        with redirect_stderr(io.StringIO()):
            self.assertEqual(client.main(["--input-manifest", str(self.manifest), "--output-manifest", str(self.manifest), "--overwrite"]), 2)
            self.assertEqual(client.main(["--input-manifest", str(self.manifest), "--output-manifest", str(self.output)]), 2)
        self.assertEqual(self.manifest.read_text(), original)
        self.assertEqual(self.output.read_text(), "existing output")

    def test_empty_manifest(self):
        self.manifest.write_text("\n")
        with redirect_stderr(io.StringIO()):
            self.assertEqual(client.main(["--input-manifest", str(self.manifest), "--output-manifest", str(self.output)]), 2)

    def test_concurrency_preserves_order_and_bounds_submission(self):
        calls = []
        def process(number, line, directory, args):
            calls.append(number)
            time.sleep(0.02 if number == 1 else 0)
            return {"manifest_line": number}
        args = self.arguments("--num-clients", "2")
        with patch.object(client, "process_row", side_effect=process):
            results = client.dataset_results(io.StringIO("{}\n{}\n{}\n"), self.root, args)
            self.assertEqual(next(results)["manifest_line"], 1)
            self.assertEqual(sorted(calls), [1, 2])
            self.assertEqual([r["manifest_line"] for r in results], [2, 3])

    def test_http_wire_contract_and_errors(self):
        captured = []
        class Handler(BaseHTTPRequestHandler):
            status = 200
            data = json.dumps(response()).encode()
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                captured.append((self.path, dict(self.headers), body))
                self.send_response(self.status)
                self.send_header("Content-Length", str(len(self.data)))
                self.end_headers()
                self.wfile.write(self.data)
            def log_message(self, *args):
                pass
        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            args = self.arguments("--server", "http://127.0.0.1:{}".format(server.server_port),
                                  "--api-key-env", "NVIDIA_API_KEY")
            with patch.dict(os.environ, {"NVIDIA_API_KEY": "test-token"}):
                timings = {}
                self.assertEqual(client.post_audio(self.audio, "Transcribe.", args, timings)["id"], "chatcmpl-test")
                self.assertEqual(timings["http_status"], 200)
                self.assertGreater(timings["client_send_seconds"], 0)
                self.assertGreater(timings["response_bytes"], 0)
            path, headers, body = captured[0]
            self.assertEqual(path, "/v1/chat/completions")
            self.assertEqual(headers["Authorization"], "Bearer test-token")
            self.assertNotIn("Transfer-Encoding", headers)
            self.assertEqual(int(headers["Content-Length"]), len(body))
            request = json.loads(body)
            self.assertEqual(base64.b64decode(request["messages"][0]["content"][1]["input_audio"]["data"]), self.audio.read_bytes())
            args.max_request_bytes = 1
            with self.assertRaisesRegex(ValueError, "encoded request"):
                client.post_audio(self.audio, "Transcribe.", args)
            self.assertEqual(len(captured), 1)
            args.max_request_bytes = 256 * 1024 * 1024
            Handler.status, Handler.data = 429, b'{"error":{"message":"busy"}}'
            with self.assertRaisesRegex(ValueError, "HTTP 429"):
                client.post_audio(self.audio, "Transcribe.", args)
            self.assertEqual(len(captured), 2)  # No implicit retries.
            Handler.status, Handler.data = 200, b"x" * 100
            args.max_response_bytes = 5
            with self.assertRaisesRegex(ValueError, "response exceeds"):
                client.post_audio(self.audio, "Transcribe.", args)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
