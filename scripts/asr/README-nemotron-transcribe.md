# Nemotron Transcribe dataset client

`nemotron_transcribe_client.py` sends one complete WAV, FLAC or Ogg Opus recording per
request to `/v1/chat/completions`. It uses only the Python standard library; no Riva gRPC,
OpenAI SDK, or additional packages are required. This is an offline client,
not a streaming-audio client. It does not split, resample, or otherwise modify audio.

## Manifest and usage

Input is JSONL, with one object per recording:

```jsonl
{"audio_filepath":"audio/example.wav","prompt":"Transcribe the audio verbatim.","id":"sample-1","text":"optional reference transcript"}
{"audio_path":"/absolute/path/meeting.wav","prompt":"Transcribe this meeting."}
```

`audio_filepath` is the preferred key; `audio_path` is an alias. Relative paths
are resolved against the input manifest's directory, not the working directory.
Additional metadata is preserved under `input` in the output. A row's `prompt`
takes precedence over `--prompt`; missing/empty prompts use the built-in instruction
to transcribe in the original language without translation. Blank lines are skipped.

```bash
python3 scripts/asr/nemotron_transcribe_client.py \
  --input-manifest /path/to/input.jsonl \
  --output-manifest /path/to/transcripts.jsonl \
  --server http://localhost:9000 \
  --language-code en \
  --verbatim-transcripts \
  --automatic-punctuation \
  --diarization \
  --word-timestamps
```

The server argument accepts an HTTP(S) origin, a `/v1` base URL, or the full
`/v1/chat/completions` endpoint. Use `--model-name` if the served model ID differs
from `nvidia-nemotron-3p5-transcribe` (listed by `GET /v1/models`). Run `--help` for all options.

## Controls

| Flag | Request behavior |
| --- | --- |
| `--verbatim-transcripts` | Adds an instruction to retain fillers, repetitions and spoken words. |
| `--no-verbatim-transcripts` | Requests readable text without fillers and false starts. |
| `--automatic-punctuation` | Requests punctuation and capitalization. |
| `--no-automatic-punctuation` | Requests no added punctuation. |
| `--diarization` / `--speaker-diarization` | Requests consistent `<spk:N>` speaker tags. |
| `--no-diarization` | Requests no speaker tags. |
| `--word-timestamps` / `--word-time-offsets` | Sets the top-level `word_timestamps: true` for real CTC-aligned words. |
| `--language-code en` | Sets the top-level `language` hint; the server refuses codes outside `/v1/models` `supported_languages` with `400`. |
| `--subtitle-format srt` / `vtt` | Requests server-generated subtitles; implies word timestamps. |
| `--seed` | Sets the API's signed 64-bit seed. |
| `--num-clients N` | Runs up to N simultaneous requests, preserving manifest order. |

Prompt controls are omitted unless explicitly selected, so custom row prompts
are not silently overridden. Selected clauses are appended to each effective
prompt; keep row prompts consistent with them. Boolean prompt flags also accept
`true`/`false`, for example `--automatic_punctuation false`. Underscore spellings
are supported for the prompt flags and word timestamps. The requested typo
`--verbatim_transcrtipts` is accepted as an alias; prefer `--verbatim-transcripts`.

Diarization and text formatting are **model instructions**, not hard-enforced
gRPC configuration fields. Do not assume exact speaker counts, punctuation, or
ITN behavior. Diarization alone does not request timing; add `--word-timestamps`
for timed speaker words. Word alignment/subtitles currently require English
transcription; an omitted language hint defaults to English on the timestamp
path. No fabricated timestamps are produced if alignment is unavailable.
Native diarization activity intervals and LLM speaker labels are different
views; both are retained in the API payload rather than conflated.

## Output

One result is flushed to the output JSONL per nonblank input row:

```json
{"manifest_line":1,"input":{"audio_filepath":"audio/example.wav","prompt":"Transcribe."},"audio_filepath":"/absolute/audio/example.wav","effective_prompt":"Transcribe.","audio_duration_seconds":1.0,"result":{"text":"Hello.","raw_text":"<spk:0> Hello.","speaker_turns":[{"speaker":"spk:0","text":"Hello."}],"words":[],"transcription":{},"warnings":[],"finish_reason":"stop","usage":null,"response_id":"chatcmpl-example"},"status":"ok","elapsed_seconds":0.5}
```

`result.text` removes valid speaker tags; `raw_text` preserves the assistant
transcript. `words` contains the actual server timings and speaker labels.
The complete `transcription` payload (the response's top-level `transcription` object) retains alignment availability, native segments,
speaker-grouped words, diarization intervals, subtitles, and provenance.
`--include-raw-response` additionally stores the entire chat-completions envelope.
Console output shows speaker turns and, when present, aligned word times.
Each completed request also records `request_elapsed_seconds` and per-request
`request_rtfx` (audio duration / latency), separately from total row processing
`elapsed_seconds`. Request timing includes connection, incremental JSON/base64
upload and response reading/JSON decoding, but excludes local audio validation and
queueing before a client worker starts. Monotonic start/end fields define the
first-request-to-last-completion serving window. The final aggregate RTFx uses
audio seconds from `ok` rows divided by this window, including failed/warning
request time; warning rows are excluded from its numerator. This conservative
metric is not a maximum steady-state throughput claim. Warmups are not
automatically excluded: run a separate warmup manifest before a timed trial.
`request_timings` additionally separates client send (connection + JSON/base64
stream upload), waiting for response headers, and reading the response, with
byte counts and HTTP status. Client send completion is not proof that the
server consumed the whole upload. Header-wait time includes server processing
and network effects; it is neither TTFT nor isolated GPU execution time.
`--quiet` suppresses transcript display, but still prints progress/errors.

Invalid JSON, missing files, HTTP errors and timeouts generate `status:error`
rows and do not prevent processing later records. Degraded transcript origins,
unavailable requested alignments and suspect plausibility checks generate
`status:warning` rows. Missing requested speaker tags also produce a warning,
even when aligned speaker labels exist; these labels do not establish that the
model honored the speaker-tag prompt. Exit codes: `0` all successful, `1` any row error/warning,
`2` setup/input/output failure or empty dataset. Existing output files are
protected unless `--overwrite` is given. Input and output cannot be the same file.
There is no automatic resume or retry; select unfinished rows for a new run.

## Long audio and safety

- Qualified input: mono 16 kHz, 16-bit PCM WAV. The client also sends 16-bit
  PCM WAV at other sample rates/channel counts, FLAC and Ogg Opus: the server
  decodes, downmixes and resamples them. The container is identified from the
  file's bytes (not its extension) and sent as `input_audio.format`; the duration
  is read from the WAV header, FLAC STREAMINFO or the last Ogg page. Original bytes
  are uploaded unchanged. MP3, Ogg Vorbis, AAC, M4A and other formats are refused
  before upload (the server answers them with `422`); convert them to WAV or FLAC
  first. Recordings shorter than 20 ms are rejected.
- Default audio limit is 3,600 seconds and JSON request limit is 256 MiB,
  matching the current stack. Base64 adds about one third to audio size.
  One hour in this WAV format is about 154 MB as an encoded JSON request.
  Adjust `--max-audio-seconds` / `--max-request-bytes` only if the server allows it.
- Audio is validated and then base64-uploaded in bounded chunks with an exact
  Content-Length. There is no full-audio/base64 copy in RAM. Response memory is
  bounded by `--max-response-bytes` (64 MiB per active client by default).
- `--request-timeout` defaults to 7,200 seconds of socket inactivity; connect
  timeout defaults to 10 seconds. These are not a total wall-clock deadline.
  Reverse proxies/server timeouts may be shorter. Start long-audio tests with
  `--num-clients 1`; success depends on server capacity and decoding limits.
- Requests are never automatically retried or redirected: a timeout may occur
  after the server accepted the audio. HTTP proxy environment variables are not
  used by this direct-connection client.
- HTTPS always verifies certificates. `--ssl-root-cert` supplies an approved CA
  bundle; there is no insecure TLS mode. Authentication is opt-in: pass
  `--api-key-env NVIDIA_API_KEY` to send the value as a bearer token to the
  selected server. Without this flag, no environment token is read or sent.
  An empty/unset selected variable also omits authentication.

Run the dependency-free tests, including a synthetic-audio loopback HTTP test:

```bash
python3 -m unittest discover -s tests/unit -p test_nemotron_transcribe_client.py -v
```
