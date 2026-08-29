const fs = require('fs');
const path = require('path');
const axios = require('axios');

// Path to the WAV file
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

// Send the WAV file to the server
async function sendWavFile() {
  try {
    // Convert audio buffer to base64
    const base64Audio = audioBuffer.toString('base64');
    console.log(`Converted audio to base64 (${base64Audio.length} characters)`);
    
    // Prepare the request
    const requestBody = {
      audio: base64Audio,
      config: {
        encoding: 'LINEAR_PCM',
        sampleRateHertz: wavInfo.sampleRate,
        languageCode: 'en-US',
        maxAlternatives: 1,
        enableAutomaticPunctuation: true
      }
    };
    
    console.log('Sending recognition request with config:', requestBody.config);
    
    // Send the request
    const serverUrl = process.env.SERVER_URL || 'http://localhost:3002/api/recognize';
    console.log(`Sending request to: ${serverUrl}`);
    
    const response = await axios.post(serverUrl, requestBody);
    
    console.log('Response status:', response.status);
    console.log('Response data:', JSON.stringify(response.data, null, 2));
    
    if (response.data.results && response.data.results.length > 0) {
      const transcript = response.data.results[0].alternatives[0].transcript;
      console.log('Transcription:', transcript);
    } else {
      console.log('No transcription in response');
    }
    
  } catch (error) {
    console.error('Error sending request:', error.message);
    if (error.response) {
      console.error('Response status:', error.response.status);
      console.error('Response data:', error.response.data);
    }
  }
}

// Execute the function
sendWavFile(); 