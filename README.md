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
    - `scripts/asr/riva_streaming_asr_client.py` demonstrates streaming transcription in several threads, can prints time stamps.
    - `scripts/asr/transcribe_file.py` performs streaming transcription,
    - `scripts/asr/transcribe_file_offline.py` performs offline transcription,
    - `scripts/asr/transcribe_mic.py` performs streaming transcription of audio acquired through microphone.
- **Speech Synthesis (TTS)**
    - `scripts/tts/talk.py` synthesizes audio for a text in streaming or offline mode.
- **Natural Language Processing (NLP)**
    - `scripts/nlp/intentslot_client.py` recognizes intents and slots in input sentences,
    - `scripts/nlp/ner_client.py` detects named entities in input sentences,
    - `scripts/nlp/punctuation_client.py` restores punctuation and capitalization in input sentences,
    - `scripts/nlp/qa_client.py` queries a document with natural language query and prints answer from a document,
    - `scripts/nlp/text_classify_client.py` classifies input sentences,
    - `scripts/nlp/eval_intent_slot.py` prints intents and slots classification reports for test data.
  
## Installation

1. Create a ``conda`` environment and activate it
2. Clone ``riva-python-clients`` repo and change to the repo root
3. Run commands

```bash
git submodule init
git submodule update
pip install -r requirements.txt
python3 setup.py bdist_wheel
pip install --force-reinstall dist/*.whl
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

### Server

Before running client part of Riva, please set up a server. The simplest
way to do this is to follow
[quick start guide](https://docs.nvidia.com/deeplearning/riva/user-guide/docs/quick-start-guide.html#local-deployment-using-quick-start-scripts).

### CLI

You may find all CLI scripts in `scripts` directory. Each script has a description of
its purpose and parameters.

### API

See tutorial notebooks in directory `tutorials`.


## Documentation

Additional documentation on the Riva Speech Skills SDK can be found [here](https://docs.nvidia.com/deeplearning/riva/user-guide/docs/).


## License

This client code is MIT-licensed. See LICENSE file for full details.
