const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');

// Path to the WAV file to stream
const wavFilePath = process.argv[2] || path.join(__dirname, 'samples', 'test.wav');
console.log(`Using WAV file: ${wavFilePath}`);

// Check if file exists
if (!fs.existsSync(wavFilePath)) {
  console.error(`Error: File '${wavFilePath}' does not exist.`);
  process.exit(1);
}

// Function to examine WAV header
function examineWavHeader(buffer) {
  if (buffer.length < 44) {
    console.error('Buffer too small to be a WAV file');
    return null;
  }
  
  // Check for RIFF and WAVE headers
  const riff = buffer.slice(0, 4).toString();
  const wave = buffer.slice(8, 12).toString();
  
  if (riff !== 'RIFF' || wave !== 'WAVE') {
    console.error('Not a valid WAV file:', { riff, wave });
    return null;
  }
  
  // Get format code
  const formatCode = buffer.readUInt16LE(20);
  
  // Get sample rate
  const sampleRate = buffer.readUInt32LE(24);
  
  // Get number of channels
  const numChannels = buffer.readUInt16LE(22);
  
  // Get bits per sample
  const bitsPerSample = buffer.readUInt16LE(34);
  
  // Find data chunk
  let dataOffset = -1;
  for (let i = 36; i < buffer.length - 4; i++) {
    if (buffer.slice(i, i + 4).toString() === 'data') {
      dataOffset = i + 8; // data + 4 bytes size
      break;
    }
  }
  
  return {
    formatCode,
    sampleRate,
    numChannels,
    bitsPerSample,
    dataOffset
  };
}

// Read the WAV file
const audioBuffer = fs.readFileSync(wavFilePath);
console.log(`Read ${audioBuffer.length} bytes from file`);

// Examine the WAV header
const wavInfo = examineWavHeader(audioBuffer);
if (!wavInfo) {
  console.error('Could not parse WAV header');
  process.exit(1);
}

console.log('WAV file info:', wavInfo);

// Extract audio data (after WAV header)
let audioData;
if (wavInfo.dataOffset > 0) {
  audioData = audioBuffer.slice(wavInfo.dataOffset);
  console.log(`Extracted ${audioData.length} bytes of audio data`);
} else {
  console.error('Could not find data chunk in WAV file');
  process.exit(1);
}

// Connect to WebSocket server
const wsUrl = process.env.WS_URL || 'ws://localhost:3002/streaming/asr';
console.log(`Connecting to WebSocket server at: ${wsUrl}`);
const ws = new WebSocket(wsUrl);

// Track transcription
let finalTranscript = '';
let interimTranscript = '';

// Handle WebSocket events
ws.on('open', () => {
  console.log('WebSocket connection established');
  
  // Send configuration
  const config = {
    sampleRate: wavInfo.sampleRate,
    encoding: 'LINEAR_PCM',
    languageCode: 'en-US',
    maxAlternatives: 1,
    enableAutomaticPunctuation: true
  };
  
  console.log('Sending configuration:', config);
  ws.send(JSON.stringify(config));
  
  // Simulate streaming by sending chunks of audio data
  console.log('Starting to stream audio data...');
  
  const CHUNK_SIZE = 1024; // Size of each chunk in bytes
  const INTERVAL = 50;    // Time between chunks in milliseconds
  
  let offset = 0;
  
  const streamInterval = setInterval(() => {
    if (offset >= audioData.length) {
      clearInterval(streamInterval);
      console.log('Finished streaming audio data');
      
      // Wait for final results before closing
      setTimeout(() => {
        ws.close();
        console.log('WebSocket connection closed');
        console.log('Final transcript:', finalTranscript);
      }, 2000);
      
      return;
    }
    
    const chunk = audioData.slice(offset, offset + CHUNK_SIZE);
    offset += CHUNK_SIZE;
    
    // Send audio chunk
    ws.send(chunk);
    
    // Log progress occasionally
    if (offset % (CHUNK_SIZE * 20) === 0) {
      console.log(`Streamed ${offset} of ${audioData.length} bytes (${Math.round(offset / audioData.length * 100)}%)`);
    }
  }, INTERVAL);
});

ws.on('message', (data) => {
  try {
    const response = JSON.parse(data.toString());
    
    if (response.error) {
      console.error('Streaming error:', response.error);
      return;
    }
    
    if (response.results && response.results.length > 0) {
      const result = response.results[0];
      
      if (result.alternatives && result.alternatives.length > 0) {
        const transcript = result.alternatives[0].transcript || '';
        
        if (!response.isPartial) {
          finalTranscript = transcript;
          console.log('Final transcript:', finalTranscript);
        } else {
          interimTranscript = transcript;
          console.log('Interim transcript:', interimTranscript);
        }
      }
    }
  } catch (error) {
    console.error('Error parsing WebSocket message:', error);
  }
});

ws.on('error', (error) => {
  console.error('WebSocket error:', error);
});

ws.on('close', (code, reason) => {
  console.log(`WebSocket closed with code ${code}${reason ? ': ' + reason : ''}`);
}); 