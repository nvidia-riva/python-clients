[![License](https://img.shields.io/badge/license-MIT-green)](https://opensource.org/licenses/MIT)
# NVIDIA Riva Clients

NVIDIA Riva is a GPU-accelerated SDK for building Speech AI applications that are customized for your use 
case and deliver real-time performance. This repo provides performant client example command-line clients.

## Main API

- `riva.client.ASRService` is a class for speech recognition,
- `riva.client.TTSService` is a class for speech synthesis,
- `riva.client.NLPService` is a class for natural language processing.

## CLI interface

- **Automatic Speech Recognition (ASR)**
    - `scripts/asr/riva_streaming_asr_client.py` demonstrates streaming transcription in several threads, can prints time stamps.
    - `scripts/asr/transcribe_file.py` performs streaming transcription,
    - `scripts/asr/transcribe_file_offline.py` performs offline transcription,
    - `scripts/asr/transcribe_mic.py` performs streaming transcription of audio acquired through microphone.
    - `scripts/asr/realtime_asr_client.py` performs realtime transcription of audio via WebSocket connection.
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
2. From source: 
    - Clone ``riva-python-clients`` repo and change to the repo root
    - Run commands

```bash
git clone https://github.com/nvidia-riva/python-clients.git
cd python-clients
git submodule init
git submodule update --remote --recursive
pip install -r requirements.txt
python3 setup.py bdist_wheel
pip install --force-reinstall dist/*.whl
```
3. `pip`:
```bash
pip install nvidia-riva-client
```

If you would like to use output and input audio devices 
(scripts `scripts/asr/transcribe_file_rt.py`, `scripts/asr/transcribe_mic.py`, `scripts/tts/talk.py`, `scripts/asr/realtime_asr_client.py` or module 
`riva.client/audio_io.py`), you will need to install `PyAudio`.
```bash
conda install -c anaconda pyaudio
```

If you would like to use Realtime ASR (WebSocket-based real-time transcription) script `scripts/asr/realtime_asr_client.py`, you will need the following dependencies:
```bash
conda install -c anaconda numpy 
conda install -c anaconda requests
conda install -c anaconda websockets
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

#### ASR

You may find a detailed documentation [here](https://docs.nvidia.com/deeplearning/riva/user-guide/docs/apis/cli.html).

For transcribing in streaming mode you may use `scripts/asr/transcribe_file.py`.
```bash
python scripts/asr/transcribe_file.py \
    --input-file data/examples/en-US_AntiBERTa_for_word_boosting_testing.wav
```

You may watch how a transcript grows if you set `--simulate-realtime` and `--show-intermediate`.
```bash
python scripts/asr/transcribe_file.py \
    --input-file data/examples/en-US_AntiBERTa_for_word_boosting_testing.wav \
    --simulate-realtime \
    --show-intermediate
```

You may listen audio simultaneously with transcribing (you will need installed PyAudio and access to audio devices).
```bash
python scripts/asr/transcribe_file.py \
    --input-file data/examples/en-US_AntiBERTa_for_word_boosting_testing.wav \
    --play-audio \
    --show-intermediate
```

Offline transcription is performed this way.
```bash
python scripts/asr/transcribe_file_offline.py \
    --input-file data/examples/en-US_AntiBERTa_for_word_boosting_testing.wav
```

You can improve transcription of this audio by word boosting.
```bash
python scripts/asr/transcribe_file_offline.py \
  --input-file data/examples/en-US_AntiBERTa_for_word_boosting_testing.wav \
  --boosted-lm-words AntiBERTa \
  --boosted-lm-words ABlooper \
  --boosted-lm-score 20.0
```

For transcribing in realtime mode you may use `scripts/asr/realtime_asr_client.py`.

**From audio file:**
```bash
python scripts/asr/realtime_asr_client.py \
  --input-file data/examples/en-US_AntiBERTa_for_word_boosting_testing.wav
```

**From microphone:**
```bash
python scripts/asr/realtime_asr_client.py \
  --mic \
  --duration 30 \
  --output-text transcript.txt
```

**List available audio devices:**
```bash
python scripts/asr/realtime_asr_client.py --list-devices
```

**Use specific audio device:**
```bash
python scripts/asr/realtime_asr_client.py \
  --mic \
  --input-device 1 \
  --duration 30 \
  --output-text transcript.txt
```

For **WebSocket-based Realtime ASR** (using `riva.client.realtime.RealtimeASRClient`), you can transcribe audio files or microphone input with real-time results:

**From audio file:**
```python
from riva.client.realtime import RealtimeASRClient
from riva.client.asr import AudioChunkFileIterator
import asyncio
import argparse

async def transcribe_file():
    # Create arguments namespace
    args = argparse.Namespace()
    args.input_file = "path/to/audio.wav"  # Required for file input
    args.mic = False  # Set to True for microphone input
    args.server = "localhost:9090"
    args.endpoint = "/v1/realtime"
    args.query_params = "intent=transcription"
    args.sample_rate_hz = 16000
    args.num_channels = 1
    args.file_streaming_chunk = 1600
    args.output_text = "transcript.txt"
    args.prompt = ""
    args.language_code = "en-US"
    args.model_name = ""
    args.automatic_punctuation = False
    args.no_verbatim_transcripts = False
    args.profanity_filter = False
    args.word_time_offsets = False
    args.max_alternatives = 1
    args.boosted_lm_words = []
    args.boosted_lm_score = 4.0
    args.speaker_diarization = False
    args.diarization_max_speakers = 3
    args.start_history = -1
    args.start_threshold = -1.0
    args.stop_history = -1
    args.stop_threshold = -1.0
    args.stop_history_eou = -1
    args.stop_threshold_eou = -1.0
    args.custom_configuration = ""
    
    client = RealtimeASRClient(args=args)
    
    await client.connect()
    
    # Create audio iterator
    audio_chunk_iterator = AudioChunkFileIterator(
        args.input_file, 
        args.file_streaming_chunk, 
        delay_callback=None
    )
    
    # Send audio and receive responses concurrently
    await asyncio.gather(
        client.send_audio_chunks(audio_chunk_iterator),
        client.receive_responses()
    )
    
    client.save_responses("transcript.txt")
    await client.disconnect()

asyncio.run(transcribe_file())
```

**From microphone:**
```python
from riva.client.realtime import RealtimeASRClient
from riva.client.audio_io import MicrophoneStream
import asyncio
import argparse

async def transcribe_microphone():
    # Create arguments namespace
    args = argparse.Namespace()
    args.input_file = None  # Not needed for microphone input
    args.mic = True
    args.duration = 30  # 30 seconds
    args.input_device = None  # Use default device
    args.server = "localhost:9090"
    args.endpoint = "/v1/realtime"
    args.query_params = "intent=transcription"
    args.sample_rate_hz = 16000
    args.num_channels = 1
    args.file_streaming_chunk = 1600
    args.output_text = "transcript.txt"
    args.prompt = ""
    args.language_code = "en-US"
    args.model_name = ""
    args.automatic_punctuation = False
    args.no_verbatim_transcripts = False
    args.profanity_filter = False
    args.word_time_offsets = False
    args.max_alternatives = 1
    args.boosted_lm_words = []
    args.boosted_lm_score = 4.0
    args.speaker_diarization = False
    args.diarization_max_speakers = 3
    args.start_history = -1
    args.start_threshold = -1.0
    args.stop_history = -1
    args.stop_threshold = -1.0
    args.stop_history_eou = -1
    args.stop_threshold_eou = -1.0
    args.custom_configuration = ""
    
    client = RealtimeASRClient(args=args)
    
    await client.connect()
    
    # Create microphone stream
    mic_chunks = MicrophoneStream(
        args.sample_rate_hz, 
        args.file_streaming_chunk, 
        device=None
    )
    
    await asyncio.gather(
        client.send_audio_chunks(mic_chunks),
        client.receive_responses()
    )
    
    await client.disconnect()

asyncio.run(transcribe_microphone())
```

#### NLP

You can provide inputs to `scripts/nlp/intentslot_client.py`, `scripts/nlp/punctuation_client.py`
both through command line arguments and interactively.
```bash
python scripts/nlp/intentslot_client.py --query "What is the weather tomorrow?"
```
or
```bash
python scripts/nlp/intentslot_client.py --interactive
```
For punctuation client the commands look similar.
```bash
python scripts/nlp/punctuation_client.py --query "can you prove that you are self aware"
```
or
```bash
python scripts/nlp/punctuation_client.py --interactive
```

**NER** client can output 1 of the following: label name, span start, span end
```bash
python scripts/nlp/ner_client.py \
  --query "Where is San Francisco?" "Jensen Huang is the CEO of NVIDIA Corporation." \
  --test label
```
or
```bash
python scripts/nlp/ner_client.py \
  --query "Where is San Francisco?" "Jensen Huang is the CEO of NVIDIA Corporation." \
  --test span_start
```
or
```bash
python scripts/nlp/ner_client.py \
  --query "Where is San Francisco?" "Jensen Huang is the CEO of NVIDIA Corporation." \
  --test span_end
```

Provide query and context to **QA** client.
```bash
python scripts/nlp/qa_client.py \
  --query "How many gigatons of carbon dioxide was released in 2005?" \
  --context "In 2010 the Amazon rainforest experienced another severe drought, in some ways "\
"more extreme than the 2005 drought. The affected region was approximate 1,160,000 square "\
"miles (3,000,000 km2) of rainforest, compared to 734,000 square miles (1,900,000 km2) in "\
"2005. The 2010 drought had three epicenters where vegetation died off, whereas in 2005 the "\
"drought was focused on the southwestern part. The findings were published in the journal "\
"Science. In a typical year the Amazon absorbs 1.5 gigatons of carbon dioxide; during 2005 "\
"instead 5 gigatons were released and in 2010 8 gigatons were released."
```

**Text classification** requires only a query.
```bash
python scripts/nlp/text_classify_client.py --query "How much sun does california get?"
```

#### TTS

Call ``scripts/tts/talk.py`` script, and you will be prompted to enter a text for speech
synthesis. Set `--play-audio` option, and a synthesized speech will be played.
```bash
python scripts/tts/talk.py --play-audio
```

You can write output to file.
```bash
python scripts/tts/talk.py --output 'my_synth_speech.wav'
```

You can use streaming mode (audio fragments returned to client as soon as they are ready).
```bash
python scripts/tts/talk.py --stream --play-audio
```

### API

See tutorial notebooks in directory `tutorials`.


## Documentation

Additional documentation on the Riva Speech Skills SDK can be found [here](https://docs.nvidia.com/deeplearning/riva/user-guide/docs/).


## License

This client code is MIT-licensed. See LICENSE file for full details.
