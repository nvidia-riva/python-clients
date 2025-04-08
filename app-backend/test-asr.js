const fs = require('fs');
const path = require('path');
const axios = require('axios');

// Path to the sample wav file
const audioFilePath = '/home/shiralal/Projects/python-clients/data/examples/en-US_sample.wav';
const serverUrl = 'http://localhost:3002/api/recognize';

// Read the WAV file as a binary Buffer
const readWavFile = () => {
  console.log(`Reading WAV file: ${audioFilePath}`);
  try {
    // Check if file exists
    if (!fs.existsSync(audioFilePath)) {
      console.error(`File not found: ${audioFilePath}`);
      process.exit(1);
    }
    
    const fileData = fs.readFileSync(audioFilePath);
    console.log(`Successfully read WAV file (${fileData.length} bytes)`);
    return fileData;
  } catch (error) {
    console.error(`Error reading file: ${error.message}`);
    process.exit(1);
  }
};

// Send the audio data to the server
const sendAudioRequest = async (audioData) => {
  try {
    console.log('Sending WAV file to ASR endpoint...');
    
    // Convert the Buffer to an array for JSON serialization
    const audioArray = Array.from(new Uint8Array(audioData));
    
    // Prepare request payload
    const payload = {
      audio: audioArray,
      config: {
        encoding: 'LINEAR_PCM',
        sampleRateHertz: 16000,
        languageCode: 'en-US',
        maxAlternatives: 1,
        enableAutomaticPunctuation: true,
        enableWordTimeOffsets: false
      }
    };
    
    console.log('Request config:', payload.config);
    console.log(`Audio data length: ${audioArray.length} bytes`);
    
    // Send POST request
    const response = await axios.post(serverUrl, payload, {
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    console.log('ASR Response:', JSON.stringify(response.data, null, 2));
    return response.data;
  } catch (error) {
    console.error('Error sending ASR request:');
    if (error.response) {
      // The request was made and the server responded with a status code
      // that falls out of the range of 2xx
      console.error(`Status: ${error.response.status}`);
      console.error('Response data:', error.response.data);
    } else if (error.request) {
      // The request was made but no response was received
      console.error('No response received from server');
    } else {
      // Something happened in setting up the request that triggered an Error
      console.error('Error:', error.message);
    }
    process.exit(1);
  }
};

// Main function
const main = async () => {
  const audioData = readWavFile();
  await sendAudioRequest(audioData);
};

// Run the script
main().catch(error => {
  console.error('Unhandled error:', error);
}); 