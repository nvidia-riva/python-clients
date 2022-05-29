[![License](https://img.shields.io/badge/license-MIT-green)](https://opensource.org/licenses/MIT)
# NVIDIA Riva Clients

NVIDIA Riva is a GPU-accelerated SDK for building Speech AI applications that are customized for your use 
case and deliver real-time performance. This repo provides performant client example command-line clients.

## Main API

- `riva_api.ASRService` is a class for speech recognition,
- `riva_api.TTSService` is a class for speech synthesis,
- `riva_api.NLPService` is a class for natural language processing.

## CLI interface

- **Automatic Speech Recognition (ASR)**
    - `riva_streaming_asr_client.py` demonstrates streaming transcription in several threads, prints time stamps.
    - `transcribe_file.py` performs streaming transcription,
    - `transcribe_file_offline.py` performs offline transcription,
    - `transcribe_file_rt.py` performs streaming transcription and simultaneously plays audio,
    - `transcribe_file_verbose.py` performs streaming transcription and prints confidence,
    - `transcribe_mic.py` performs streaming transcription of audio acquired through microphone.
- **Speech Synthesis (TTS)**
    - `talk.py` synthesizes audio for a text in streaming or offline mode.
- **Natural Language Processing (NLP)**
    - `intentslot_client.py` recognizes intents and slots in input sentences,
    - `ner_client.py` detects named entities for input sentences,
    - `punctuation_client.py` restores punctuation and capitalization in input sentences,
    - `qa_client.py` queries a document with natural language query and prints answer from a document,
    - `text_classify_client.py` classifies input sentences,
    - `eval_intent_slot.py` prints intents and slots classification reports for test data.
  
## Installation

1. Create a ``conda`` environment and activate it
2. Clone ``riva-python-clients`` repo and change to the repo root
3. Run commands

```bash
git submodule init
git submodule update
pip install -r requirements.txt
python3 setup.py bdist_wheel
pip install dist/*.whl
```

If you would like to use output and input audio devices 
(scripts `scripts/asr/transcribe_file_rt.py`, `scripts/asr/transcribe_mic.py`, `scripts/tts/talk.py` or module 
`riva_api/audio_io.py`), you will need to install `PyAudio`.
```bash
conda install -c anaconda pyaudio
```

For NLP evaluation you will need `transformers` and `sklearn` libraries.
```bash
pip install -U scikit-learn
pip install -U transformers
```

## Before using microphone and audio output devices on Unix
you may need to run commands
```
adduser $USER audio
adduser $USER pulse-access
```
and restart.

## Usage

### Speech Recognition (ASR) Clients
Riva comes with 2 ASR clients:
1. `riva_asr_client` for offline usage. Using this client, the server will wait until it receives the full audio file before transcribing it and sending it back to the client.
2. `riva_streaming_asr_client` for online usage. Using this client, the server will start transcribing after it receives a sufficient amount of audio data, "streaming" intermediate transcripts as it goes on back to the client. By default, it is set to transcribe after every `100ms`, this can be changed using the `--chunk_duration_ms` command line flag.

To use the clients, simply pass in a folder containing audio files or an individual audio file name with the `audio_file` flag:
```
$ riva_streaming_asr_client --audio_file individual_audio_file.wav
```
or
```
$ riva_asr_client --audio_file audio_folder
```
 
Note that only single-channel audio files in the `.wav` format are currently supported.

Other options and information can be found by running the clients with `-help`

### Speech Synthesis (TTS) Client
Riva comes with 2 TTS clients:
1. `riva_tts_client` 
2. `riva_tts_perf_client`

Both clients support an `online` flag, which is similar to the `streaming` ASR client. Enabling the flag will stream the audio back to the client as soon as it is generated on the server, otherwise will send the entire batch at once.

Language can also be specified using a BCP-47 language tag, which is default to `en-US`

To use the `riva_tts_client` simply run the client passing in text with the `--text` flag:
```
$ riva_tts_client --text="Text to be synthesized"
```

The `riva_tts_perf_client` performs the same as the `riva_tts_client` however provides additional information about latency and throughput. Run the client passing in a file containing the text input using the `--text_file` flag.
```
$ riva_tts_perf_client --text_file=/text_files/input.txt
```

Other options and information can be found by running the clients with `-help` 

### NLP Client

Riva comes with 3 NLP clients.
1. `riva_nlp_classify_tokens` for Token Classification (NER)
2. `riva_nlp_punct` for Punctuation
3. `riva_nlp_qa` for Question and Answering

The `examples` folder contains example queries to test out all 3 API's.

To run the NER or Punctuation clients, simply pass in a text file containing queries using the `--queries` flag

```
$ riva_nlp_classify_tokens --queries=examples/token_queries.txt
Done sending 1 requests
0: jensen huang [PER (0.997211)], nvidia corporation [ORG (0.970043)], santa clara [LOC (0.997773)], california [LOC (0.996258)],
```

```
$ riva_nlp_punct --queries=examples/punctuation_queries.txt      Done sending 3 requests
1: Punct text: Do you have any red Nvidia shirts?
0: Punct text: Add punctuation to this sentence.
2: Punct text: I need one cpu, four gpus and lots of memory for my new computer. It's going to be very cool.
```

To run the QA client, pass in a text file containing the contexts (1 per line) using the `--contexts` flag, and pass in the corresponding questions (1 per line) using the `--questions` flag
```
$ riva_nlp_qa --contexts=examples/qa_contexts.txt --questions=/work/examples/qa_questions.txt
Done sending 2 requests
0: Answer: northern Kazakhstan
Score: 0.736824
1: Answer: Chris Malachowsky,
Score: 0.90164
```

Other options and information can be found by running the clients with `-help` 

## Documentation

Additional documentation on the Riva Speech Skills SDK can be found [here](https://docs.nvidia.com/deeplearning/riva/user-guide/docs/).


## License

This client code is MIT-licensed. See LICENSE file for full details.
