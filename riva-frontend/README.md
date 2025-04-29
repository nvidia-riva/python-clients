# Riva Speech Recognition Frontend

This React application provides a user interface for Nvidia Riva's speech recognition services.

## Features

- Real-time speech recognition via microphone streaming
- Batch recognition by uploading audio files
- Support for WAV file format
- Visual audio level indicator
- Server connectivity status monitoring

## Setup and Installation

1. Ensure you have Node.js installed (v14 or higher recommended)

2. Install dependencies:
   ```
   npm install
   ```

3. Configure the backend connection:
   - The application is configured to connect to a backend server at `http://localhost:3002`
   - You can modify the server URL in the `getServerUrl` function in `src/App.tsx`

## Running the Application

Start the development server:

```
npm start
```

The application will be available at [http://localhost:3000](http://localhost:3000).

## Testing the Application

### Prerequisites

Before testing, ensure:
1. The Riva backend server is running (see app-backend README for instructions)
2. Your browser has permission to access the microphone
3. You have sample audio files available for testing (preferably WAV format)

### Testing File Upload Speech Recognition

1. Launch the application and wait for the server connection check to complete
2. Verify that the server connection is successful (no red error messages)
3. Click the "Upload Audio File" button
4. Select an audio file from your computer
   - Supported formats include WAV, MP3, and other browser-supported audio formats
   - For best results, use WAV files with 16kHz sample rate, 16-bit PCM encoding
5. The application will automatically process the file and display the transcription result
6. The transcription will appear in the "Transcription" section below the buttons

**Note:** WAV files no longer automatically download back to your device when uploading.

### Testing Real-time Speech Recognition

1. Launch the application and verify server connection
2. Click the "Start Streaming" button
3. When prompted, allow microphone access in your browser
4. Speak clearly into your microphone
5. Observe the volume indicator to ensure your audio is being picked up
6. Partial transcription results will appear in gray text
7. Final transcription results will appear in black text and be added to the complete transcription
8. Click "Stop Streaming" when finished

### Troubleshooting

If you encounter issues:

1. **Server Connection Problems**
   - Ensure the backend server is running at the expected URL
   - Check browser console for CORS or network-related errors
   - Use the "Retry Connection" button to attempt reconnection

2. **Microphone Issues**
   - Verify microphone permissions in your browser settings
   - Check that your microphone is working in other applications
   - Ensure no other application is using the microphone

3. **File Upload Problems**
   - Check the file format is supported
   - Verify the file isn't corrupted
   - Try a different audio file

4. **Transcription Quality Issues**
   - Ensure clear audio with minimal background noise
   - For real-time streaming, speak clearly and at a moderate pace
   - Position your microphone properly for optimal audio capture
