# Riva App Backend

This is a Node.js proxy server that connects to the Riva API server. It provides API endpoints for automatic speech recognition (ASR) and text-to-speech (TTS) services.

## Features

- Direct connection to Riva server using official proto files
- ASR (Automatic Speech Recognition) endpoint
- TTS (Text-to-Speech) endpoint
- WAV file support with header analysis and proper processing
- Configurable via environment variables
- WebSocket support for real-time streaming recognition

## Setup

1. Ensure you have Node.js installed (v14 or higher recommended)

2. Install dependencies:
   ```
   npm install
   ```

3. Download the proto files:
   ```
   npm run download-protos
   ```
   This script will clone the nvidia-riva/common repository and copy the necessary proto files to the `riva/proto` directory.

## Configuration

Create a `.env` file in the root directory with the following variables:

```
PORT=3002
RIVA_API_URL=localhost:50051
```

- `PORT`: The port on which the proxy server will run
- `RIVA_API_URL`: The URL of the Riva API server

## Running the Server

Start the server:

```
npm start
```

This will automatically run the `download-protos` script before starting the server if the proto files are not already present.

## Testing the Application

### Prerequisites

Before testing:
1. Ensure the Riva API server is running at the configured URL
2. Verify that the proto files have been downloaded successfully
3. Make sure the Node.js server is running (check for "Server listening on port 3002" message)
4. Have sample audio files available for testing

### Testing the API Endpoints Directly

#### Testing the Health Endpoint

```bash
curl http://localhost:3002/health
```

Expected response:
```json
{
  "status": "ok",
  "services": {
    "asr": {
      "available": true
    },
    "tts": {
      "available": true
    }
  }
}
```

#### Testing ASR with a WAV File

You can use the included test script:

```bash
# If you have a sample WAV file
node test-asr.js /path/to/your/audio.wav
```

Or test manually with curl:

```bash
# Convert WAV to base64 first
base64 -w 0 /path/to/your/audio.wav > audio.b64

# Send the request
curl -X POST http://localhost:3002/api/recognize \
  -H "Content-Type: application/json" \
  -d @- << EOF
{
  "audio": "$(cat audio.b64)",
  "config": {
    "encoding": "LINEAR_PCM",
    "sampleRateHertz": 16000,
    "languageCode": "en-US",
    "enableAutomaticPunctuation": true
  }
}
EOF
```

### Testing with the Frontend

The best way to test the complete functionality is using the provided frontend application:

1. Start this backend server
2. Start the Riva frontend application
3. Use the frontend to upload audio files or test streaming recognition

### Debugging and Log Information

The server provides detailed logging for audio processing. When processing WAV files, it will:

1. Log detection of WAV headers
2. Display information about:
   - Sample rate
   - Number of channels
   - Bits per sample
   - Audio format

When issues occur, check the console output for detailed error messages.

## Troubleshooting Proto Files Download

If you encounter issues downloading proto files:

1. Check your internet connection
2. Verify that git is installed and accessible
3. Look for specific errors in the console output
4. Make sure the `riva_common.proto` file is included in the filter (the download script now includes this file)
5. Try running the download script manually:
   ```
   node download-protos.js
   ```
6. If problems persist, you can manually clone the repository and copy the proto files:
   ```
   git clone https://github.com/nvidia-riva/common.git
   mkdir -p riva/proto
   cp common/riva/proto/*.proto riva/proto/
   ```

## API Endpoints

### Status

- **GET** `/health`
  - Returns the status of the ASR and TTS services

### Speech Recognition (ASR)

- **POST** `/api/recognize`
  - Request body:
    ```json
    {
      "audio": "<base64-encoded audio data>",
      "config": {
        "encoding": "LINEAR_PCM",
        "sampleRateHertz": 16000,
        "languageCode": "en-US",
        "maxAlternatives": 1,
        "enableAutomaticPunctuation": true,
        "audioChannelCount": 1
      }
    }
    ```
  - Response:
    ```json
    {
      "results": [
        {
          "alternatives": [
            {
              "transcript": "recognized text",
              "confidence": 0.98
            }
          ]
        }
      ],
      "text": "recognized text",
      "confidence": 0.98
    }
    ```

### WebSocket Streaming (ASR)

- **WebSocket** `/streaming/asr`
  - First message (config):
    ```json
    {
      "sampleRate": 16000,
      "encoding": "LINEAR_PCM",
      "languageCode": "en-US",
      "maxAlternatives": 1,
      "enableAutomaticPunctuation": true
    }
    ```
  - Subsequent messages: Binary audio data (16-bit PCM)
  - Server responses:
    ```json
    {
      "results": [
        {
          "alternatives": [
            {
              "transcript": "recognized text"
            }
          ]
        }
      ],
      "isPartial": true|false
    }
    ```

## Integrating with a New Frontend Application

If you want to create a new frontend application that uses this backend server, follow these guidelines:

### REST API Integration

1. **Server URL Configuration**
   - Configure your frontend to connect to the backend at `http://localhost:3002` (or your custom port)
   - Ensure your application can handle CORS if the frontend is hosted on a different domain/port

2. **Health Check**
   - Implement a health check on application startup:
   ```javascript
   fetch('http://localhost:3002/health')
     .then(response => response.json())
     .then(data => {
       // Check if services are available
       const asrAvailable = data.services.asr.available;
       const ttsAvailable = data.services.tts.available;
       // Update UI accordingly
     });
   ```

3. **File Upload for Speech Recognition**
   - Read the audio file as ArrayBuffer
   - Convert to base64
   - Send to the `/api/recognize` endpoint:
   ```javascript
   // Example in JavaScript
   const fileReader = new FileReader();
   fileReader.onload = async (event) => {
     const arrayBuffer = event.target.result;
     const base64Audio = arrayBufferToBase64(arrayBuffer);
     
     const response = await fetch('http://localhost:3002/api/recognize', {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       body: JSON.stringify({
         audio: base64Audio,
         config: {
           encoding: 'LINEAR_PCM',
           sampleRateHertz: 16000,
           languageCode: 'en-US',
           enableAutomaticPunctuation: true
         }
       })
     });
     
     const result = await response.json();
     // Process transcription result
   };
   fileReader.readAsArrayBuffer(audioFile);
   
   // Helper function to convert ArrayBuffer to base64
   function arrayBufferToBase64(buffer) {
     let binary = '';
     const bytes = new Uint8Array(buffer);
     for (let i = 0; i < bytes.byteLength; i++) {
       binary += String.fromCharCode(bytes[i]);
     }
     return window.btoa(binary);
   }
   ```

### WebSocket Integration for Streaming ASR

1. **Create WebSocket Connection**
   ```javascript
   const ws = new WebSocket('ws://localhost:3002/streaming/asr');
   ```

2. **Send Configuration on Connection**
   ```javascript
   ws.onopen = () => {
     const config = {
       sampleRate: 16000,
       encoding: 'LINEAR_PCM',
       languageCode: 'en-US',
       maxAlternatives: 1,
       enableAutomaticPunctuation: true
     };
     ws.send(JSON.stringify(config));
   };
   ```

3. **Capture and Send Audio**
   ```javascript
   // Assuming you have access to audio data as Int16Array
   // This could be from a microphone input or processed audio data
   function sendAudioChunk(audioData) {
     if (ws.readyState === WebSocket.OPEN) {
       ws.send(audioData.buffer);
     }
   }
   ```

4. **Process Recognition Results**
   ```javascript
   ws.onmessage = (event) => {
     const response = JSON.parse(event.data);
     if (response.results && response.results.length > 0) {
       const result = response.results[0];
       if (result.alternatives && result.alternatives.length > 0) {
         const transcript = result.alternatives[0].transcript;
         const isPartial = response.isPartial;
         // Update UI with transcript
         // Treat partial results differently from final results
       }
     }
   };
   ```

5. **Handle Errors and Connection Close**
   ```javascript
   ws.onerror = (error) => {
     console.error('WebSocket error:', error);
     // Show error in UI
   };
   
   ws.onclose = (event) => {
     console.log(`WebSocket closed with code ${event.code}`);
     // Handle reconnection or update UI
   };
   ```

### CORS Considerations

The backend server is configured to allow cross-origin requests. If you encounter CORS issues:

1. Ensure the backend is properly configured with CORS headers
2. Check that your frontend is using the correct protocol (http/https)
3. Avoid mixing secure and insecure contexts

### Example Implementation

For a complete example of frontend integration, refer to the companion `riva-frontend` repository, which demonstrates both file upload and streaming implementations.