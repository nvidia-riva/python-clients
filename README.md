[![CircleCI](https://circleci.com/gh/nvidia-riva/cpp-clients.svg?style=shield)](https://circleci.com/gh/nvidia-riva/cpp-clients) [![License](https://img.shields.io/badge/license-MIT-green)](https://opensource.org/licenses/MIT)
# NVIDIA Riva Clients

NVIDIA Riva is a GPU-accelerated SDK for building Speech AI applications that are customized for your use case and deliver real-time performance. This repo provides performant client example command-line clients.

## Features

- **Automatic Speech Recognition (ASR)**
    - `riva_streaming_asr_client`
    - `riva_asr_client`
- **Speech Synthesis (TTS)**
    - `riva_tts_client`
    - `riva_tts_perf_client`
- **Natural Language Processing (NLP)**
    - `riva_nlp_classify_tokens`
    - `riva_nlp_punct`
    - `riva_nlp_qa`

## Requirements

1. Meet the Quick Start [prerequisites](https://docs.nvidia.com/deeplearning/riva/user-guide/docs/quick-start-guide.html#prerequisites)
2. A NVIDIA Riva Server (Set one up using the [quick start guide](https://docs.nvidia.com/deeplearning/riva/user-guide/docs/quick-start-guide.html#local-deployment-using-quick-start-scripts))
3. Docker (for Docker build)
4. Bazel 5.0.0 (for local build)

## Build

### Docker

To avoid needing to manually build the clients yourself, Riva comes with a ready to use client docker image. This allows you to run the clients through an interactive docker container.

The clients will need access to a Riva Server. If your server is running locally all you need to do is allow the client container access to your local network. 
If your server is not running locally, all clients come with a command line option `--riva_uri`. This defaults to `localhost:50051`, which is also the default server configuration. As the server is not local, run the client using `--riva_uri [IP]:[PORT]` with your configuration. 

To build the docker image simply run
```
DOCKER_BUILDKIT=1 docker build . --tag riva-client
```
To start an interactive docker container, with access to your local network, you can then run
```
docker run -it --net=host riva-client
```

Then you can run the clients as command line programs


### Local
Local builds are currently only supported through `bazel 3.7.2`. 

First install the dependencies with:
```
sudo apt-get install libasound2-dev
```

Then, to build all clients, from the project's root directory run:
```
bazel build ...
```

To build a specific client, you can run:
```
bazel build //riva/clients/[asr/tts/nlp]:[CLIENT_NAME]
```

For example, to build the `riva_streaming_asr_client` you would run:
```
bazel build //riva/clients/asr:riva_streaming_asr_client
```

You can find the built binaries in `bazel-bin/riva/clients`

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
