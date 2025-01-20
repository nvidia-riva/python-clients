# NVIDIA Riva TypeScript Client

TypeScript implementation of the NVIDIA Riva client, providing a modern, type-safe interface for interacting with NVIDIA Riva services. This client is designed to be fully compatible with the Python implementation while leveraging TypeScript's type system for enhanced developer experience.

## Features

### Automatic Speech Recognition (ASR)
- Real-time streaming transcription with configurable chunk sizes
- Offline transcription with full audio files
- Word boosting and custom vocabulary
- Speaker diarization with configurable speaker count
- Custom endpointing configuration
- Model selection and listing
- Multi-language support
- WAV file handling and audio format utilities

### Text-to-Speech (TTS)
- High-quality speech synthesis
- Streaming and offline synthesis modes
- Custom dictionary support
- Multi-voice and multi-language support
- SSML support
- Audio format conversion utilities
- WAV file output handling

### Natural Language Processing (NLP)
- Text classification with confidence scores
- Token classification with position information
- Entity analysis with type and score
- Intent recognition with slot filling
- Text transformation
- Natural language query processing
- Language code support

### Neural Machine Translation (NMT)
- Text-to-text translation
- Language pair configuration
- Batch translation support

## Prerequisites

- Node.js (v18.x or later)
- npm (v6.x or later)
- Protocol Buffers compiler (protoc)
- TypeScript (v5.x or later)

## Installation

```bash
npm install nvidia-riva-client
```

## Building from Source

```bash
git clone https://github.com/nvidia-riva/python-clients
cd python-clients/riva-ts-client
npm install
npm run build
```

## Quick Start

### ASR Example
```typescript
import { ASRService } from 'nvidia-riva-client';

const asr = new ASRService({
    serverUrl: 'localhost:50051'
});

// Streaming recognition
async function streamingExample() {
    const config = {
        encoding: AudioEncoding.LINEAR_PCL_16,
        sampleRateHz: 16000,
        languageCode: 'en-US',
        audioChannelCount: 1
    };

    for await (const response of asr.streamingRecognize(audioSource, config)) {
        console.log(response.results[0]?.alternatives[0]?.transcript);
    }
}

// Offline recognition
async function offlineExample() {
    const config = {
        encoding: AudioEncoding.LINEAR_PCL_16,
        sampleRateHz: 16000,
        languageCode: 'en-US',
        audioChannelCount: 1,
        enableSpeakerDiarization: true,
        maxSpeakers: 2
    };

    const response = await asr.recognize(audioBuffer, config);
    console.log(response.results[0]?.alternatives[0]?.transcript);
}
```

### TTS Example
```typescript
import { SpeechSynthesisService } from 'nvidia-riva-client';

const tts = new SpeechSynthesisService({
    serverUrl: 'localhost:50051'
});

async function synthesizeExample() {
    const response = await tts.synthesize('Hello, welcome to Riva!', {
        language: 'en-US',
        voice: 'English-US-Female-1',
        sampleRateHz: 44100,
        customDictionary: {
            'Riva': 'R IY V AH'
        }
    });
    
    // Save to WAV file
    await response.writeToFile('output.wav');
}
```

### NLP Example
```typescript
import { NLPService } from 'nvidia-riva-client';

const nlp = new NLPService({
    serverUrl: 'localhost:50051'
});

async function nlpExample() {
    // Text Classification
    const classifyResult = await nlp.classifyText(
        'Great product, highly recommend!',
        'sentiment',
        'en-US'
    );
    console.log(classifyResult.results[0]?.label);

    // Entity Analysis
    const entityResult = await nlp.analyzeEntities(
        'NVIDIA is headquartered in Santa Clara, California.'
    );
    console.log(entityResult.entities);

    // Intent Recognition
    const intentResult = await nlp.analyzeIntent(
        'What is the weather like today?'
    );
    console.log(intentResult.intent, intentResult.confidence);
}
```

### NMT Example
```typescript
import { NMTService } from 'nvidia-riva-client';

const nmt = new NMTService({
    serverUrl: 'localhost:50051'
});

async function translateExample() {
    const result = await nmt.translate(
        'Hello, how are you?',
        'en-US',
        'es-ES'
    );
    console.log(result.translations[0]?.text);
}
```

## API Documentation

For detailed API documentation, please refer to the [API Reference](docs/api.md).

## Testing

```bash
# Run all tests
npm test

# Run tests with coverage
npm run test:coverage

# Run tests in watch mode
npm run test:watch
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## License

This project is licensed under the terms of the [Apache 2.0 License](LICENSE).
