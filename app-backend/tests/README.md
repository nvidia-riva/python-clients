# Riva API Test Suite

This directory contains test scripts for the Riva API integration.

## Test Files Overview

- `test-asr.js`: Tests the ASR (Automatic Speech Recognition) endpoint with a WAV file
- `test-streaming.js`: Tests the Streaming ASR WebSocket endpoint with a WAV file
- `test-wav-file.js`: Tests WAV file handling and sends it to the server
- `direct-riva-test.js`: Tests direct communication with the Riva server, bypassing the Node.js API

## Prerequisites

- Node.js 14+ installed
- Required npm packages (`ws`, `axios`, `@grpc/grpc-js`, `@grpc/proto-loader`, `tmp`)
- Sample WAV files in the `samples` directory
- Running server (either local development server or production server)

## Installing Dependencies

```bash
cd app-backend
npm install ws axios @grpc/grpc-js @grpc/proto-loader tmp
```

## Sample Audio Files

Place your sample WAV files in the `samples` directory. The scripts will default to `samples/test.wav` if no file is specified.

## Running the Tests

### Test ASR API

```bash
cd app-backend
node tests/test-asr.js [path/to/audio.wav]
```

### Test Streaming ASR

```bash
cd app-backend
node tests/test-streaming.js [path/to/audio.wav]
```

### Test WAV File Handling

```bash
cd app-backend
node tests/test-wav-file.js [path/to/audio.wav]
```

### Test Direct Riva Communication

```bash
cd app-backend
node tests/direct-riva-test.js [path/to/audio.wav]
```

## Environment Variables

You can customize the behavior of the test scripts using these environment variables:

- `SERVER_URL`: URL of the server API (default: `http://localhost:3002/api/recognize`)
- `WS_URL`: WebSocket URL for streaming (default: `ws://localhost:3002/streaming/asr`)
- `RIVA_SERVER`: Address of the Riva server (default: `localhost:50051`)

Example:
```bash
SERVER_URL=http://production-server/api/recognize node tests/test-asr.js
```

## Troubleshooting

### Common Issues

1. **Connection Refused**: Make sure the server is running at the expected address
2. **File Not Found**: Ensure the WAV file exists at the specified path
3. **Invalid WAV Format**: Verify that your WAV file is correctly formatted (PCM format is recommended)
4. **Riva Server Errors**: Check that the Riva server is running and accessible

### WAV File Requirements

The Riva ASR service works best with these audio specifications:
- Format: PCM (Linear PCM) 
- Sample Rate: 16000 Hz (or 44100 Hz)
- Channels: 1 (mono)
- Bit Depth: 16-bit

## Creating Test WAV Files

You can create test WAV files using tools like Audacity or convert them using FFmpeg:

```bash
# Convert any audio file to a Riva-compatible WAV file
ffmpeg -i input.mp3 -acodec pcm_s16le -ac 1 -ar 16000 output.wav
``` 