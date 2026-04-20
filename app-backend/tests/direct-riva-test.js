const fs = require('fs');
const path = require('path');
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const { promisify } = require('util');
const tmp = require('tmp');
const { exec } = require('child_process');

// Path to the WAV file to test
const wavFilePath = process.argv[2] || path.join(__dirname, 'samples', 'test.wav');
console.log(`Using WAV file: ${wavFilePath}`);

// Check if file exists
if (!fs.existsSync(wavFilePath)) {
  console.error(`Error: File '${wavFilePath}' does not exist.`);
  process.exit(1);
}

// Create a temporary directory for proto files
const tmpdir = tmp.dirSync({ unsafeCleanup: true });
console.log(`Created temporary directory: ${tmpdir.name}`);

// Write a simple ASR proto definition
const asr_proto = `
syntax = "proto3";

package nvidia.riva.asr;

message RecognitionConfig {
  enum AudioEncoding {
    ENCODING_UNSPECIFIED = 0;
    LINEAR_PCM = 1;
    FLAC = 2;
    MULAW = 3;
    ALAW = 4;
  }
  
  AudioEncoding encoding = 1;
  int32 sample_rate_hertz = 2;
  string language_code = 3;
  int32 max_alternatives = 4;
  bool profanity_filter = 5;
  string model = 7;
  bool enable_automatic_punctuation = 11;
  bool enable_word_time_offsets = 12;
  bool enable_separate_recognition_per_channel = 13;
  int32 audio_channel_count = 14;
  bool enable_word_confidence = 15;
  bool enable_raw_transcript = 16;
  bool enable_speaker_diarization = 17;
  int32 diarization_speaker_count = 18;
}

message RecognitionAudio {
  oneof audio_source {
    bytes content = 1;
    string uri = 2;
  }
}

message SpeechRecognitionAlternative {
  string transcript = 1;
  float confidence = 2;
}

message SpeechRecognitionResult {
  repeated SpeechRecognitionAlternative alternatives = 1;
}

message RecognizeResponse {
  repeated SpeechRecognitionResult results = 1;
}

message RecognizeRequest {
  RecognitionConfig config = 1;
  RecognitionAudio audio = 2;
}

service RivaSpeechRecognition {
  rpc Recognize(RecognizeRequest) returns (RecognizeResponse) {}
}
`;

fs.writeFileSync(path.join(tmpdir.name, 'asr.proto'), asr_proto);
console.log('Wrote ASR proto definition to temporary directory');

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

// Main function
async function main() {
  try {
    // Read the WAV file
    console.log(`Reading WAV file: ${wavFilePath}`);
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
    
    // Load the proto definition
    console.log('Loading proto definition');
    const packageDefinition = protoLoader.loadSync(
      path.join(tmpdir.name, 'asr.proto'),
      {
        keepCase: true,
        longs: String,
        enums: String,
        defaults: true,
        oneofs: true
      }
    );
    
    // Load the package
    const rivaSpeechProto = grpc.loadPackageDefinition(packageDefinition).nvidia.riva.asr;
    
    // Create client
    const rivaServerAddress = process.env.RIVA_SERVER || 'localhost:50051';
    console.log(`Connecting to Riva server at: ${rivaServerAddress}`);
    const client = new rivaSpeechProto.RivaSpeechRecognition(
      rivaServerAddress,
      grpc.credentials.createInsecure()
    );
    
    // Prepare request
    const request = {
      config: {
        encoding: 'LINEAR_PCM',
        sample_rate_hertz: wavInfo.sampleRate,
        language_code: 'en-US',
        max_alternatives: 1,
        enable_automatic_punctuation: true
      },
      audio: {
        content: audioData
      }
    };
    
    console.log('Sending recognition request with config:', request.config);
    
    // Send request
    const recognize = promisify(client.Recognize).bind(client);
    const response = await recognize(request);
    
    console.log('Recognition response:', JSON.stringify(response, null, 2));
    
    // Extract transcription
    if (response.results && response.results.length > 0) {
      if (response.results[0].alternatives && response.results[0].alternatives.length > 0) {
        const transcript = response.results[0].alternatives[0].transcript;
        console.log('Transcription:', transcript);
      } else {
        console.log('No alternatives found in response');
      }
    } else {
      console.log('No results found in response');
    }
    
  } catch (error) {
    console.error('Error:', error);
  } finally {
    // Clean up temporary directory
    tmpdir.removeCallback();
    console.log('Cleaned up temporary directory');
  }
}

// Run the main function
main(); 