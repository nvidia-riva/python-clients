require('dotenv').config();
const express = require('express');
const cors = require('cors');
const morgan = require('morgan');
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const fs = require('fs');
const path = require('path');
const WebSocket = require('ws');
const http = require('http');

const app = express();
const PORT = process.env.PORT || 3002;
const serverUrl = process.env.RIVA_API_URL || 'localhost:50051';

console.log(`Connecting to Riva server at: ${serverUrl}`);

// Define paths to proto files
const PROTO_DIR = path.join(__dirname, 'riva/proto');
const ASR_PROTO_PATH = path.join(PROTO_DIR, 'riva_asr.proto');

// Check if proto files exist
if (!fs.existsSync(ASR_PROTO_PATH)) {
  console.error('ASR proto file is missing! Please run "npm run download-protos" first.');
  process.exit(1);
}

console.log(`Using proto files from: ${PROTO_DIR}`);

// Create gRPC clients from the proto definitions
let asrClient = null;
let serviceStatus = {
  asr: { available: false, error: null }
};

try {
  // Load the ASR proto definition
  console.log('Loading ASR proto from:', ASR_PROTO_PATH);
  const asrProtoDefinition = protoLoader.loadSync(ASR_PROTO_PATH, {
    keepCase: true,
    longs: String,
    enums: String,
    defaults: true,
    oneofs: true,
    includeDirs: [path.join(__dirname, 'proto'), path.join(__dirname, 'common')]
  });
  
  // Create the ASR client
  console.log('Creating ASR client...');
  const asrProto = grpc.loadPackageDefinition(asrProtoDefinition);
  asrClient = new asrProto.nvidia.riva.asr.RivaSpeechRecognition(
    serverUrl,
    grpc.credentials.createInsecure()
  );
  serviceStatus.asr.available = true;
  
  console.log('Successfully connected to Riva server');
} catch (error) {
  console.error(`Failed to initialize Riva client: ${error}`);
  serviceStatus.asr.error = error.message;
}

// Set up Express middleware
app.use(cors({
  origin: '*', // Allow all origins for testing purposes
  methods: ['GET', 'POST'],
  allowedHeaders: ['Content-Type'],
  credentials: true
}));
app.use(express.json({ limit: '50mb' }));
app.use(morgan('dev'));

// API routes
app.get('/', (req, res) => {
  res.json({
    message: 'Riva ASR Proxy Server is running',
    serviceStatus,
    serverUrl: serverUrl,
    mode: 'Direct connection to Riva server using downloaded proto files'
  });
});

// Add health check endpoint
app.get('/health', (req, res) => {
  console.log('Health check request received');
  res.json({
    status: 'ok',
    message: 'Riva ASR Proxy Server is healthy',
    timestamp: new Date().toISOString(),
    serviceStatus
  });
});

// Helper function to examine WAV header
function examineWavHeader(buffer) {
  // Check if buffer is long enough to contain a WAV header
  if (buffer.length < 44) return null;
  
  // Check for RIFF and WAVE headers
  const riff = buffer.slice(0, 4).toString();
  const wave = buffer.slice(8, 12).toString();
  
  if (riff !== 'RIFF' || wave !== 'WAVE') {
    console.log('Not a valid WAV file:', { riff, wave });
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

app.post('/api/recognize', async (req, res) => {
  if (!serviceStatus.asr.available) {
    return res.status(503).json({
      error: 'ASR service unavailable',
      details: serviceStatus.asr.error
    });
  }

  try {
    const { audio, config = {} } = req.body;
    
    if (!audio) {
      return res.status(400).json({ error: 'No audio data provided' });
    }
    
    console.log('Received ASR request:', {
      audioLength: audio.length,
      configParams: Object.keys(config)
    });
    
    // Convert base64 to buffer
    const audioBuffer = Buffer.from(audio, 'base64');
    console.log(`Decoded audio buffer length: ${audioBuffer.length} bytes`);
    
    // Check if it's a WAV file and get its properties
    const wavHeader = examineWavHeader(audioBuffer);
    
    if (wavHeader) {
      console.log('WAV file properties:', {
        formatCode: wavHeader.formatCode,
        sampleRate: wavHeader.sampleRate,
        numChannels: wavHeader.numChannels,
        bitsPerSample: wavHeader.bitsPerSample,
        dataOffset: wavHeader.dataOffset
      });
    } else {
      console.log('Not a WAV file or could not parse header');
    }
    
    // Prepare recognition config
    const recognitionConfig = {
      encoding: config.encoding || (wavHeader ? 'LINEAR_PCM' : 'LINEAR_PCM'),
      sample_rate_hertz: config.sampleRateHertz || (wavHeader ? wavHeader.sampleRate : 16000),
      language_code: config.languageCode || 'en-US',
      max_alternatives: config.maxAlternatives || 1,
      enable_automatic_punctuation: config.enableAutomaticPunctuation !== false,
      audio_channel_count: config.audioChannelCount || (wavHeader ? wavHeader.numChannels : 1)
    };
    
    console.log('Using recognition config:', recognitionConfig);
    
    // Extract audio data from WAV if needed
    let audioData = audioBuffer;
    if (wavHeader && wavHeader.dataOffset > 0) {
      audioData = audioBuffer.slice(wavHeader.dataOffset);
      console.log(`Extracted ${audioData.length} bytes of audio data from WAV file`);
    }
    
    // Send the recognition request
    asrClient.Recognize(
      {
        config: recognitionConfig,
        audio: audioData
      },
      (err, response) => {
        if (err) {
          console.error('ASR recognition error:', err);
          return res.status(500).json({
            error: 'Failed to process audio',
            details: err.message
          });
        }
        
        console.log('Received ASR response');
        
        // Process the results
        const results = response.results || [];
        const alternatives = results.length > 0 ? results[0].alternatives || [] : [];
        const transcript = alternatives.length > 0 ? alternatives[0].transcript : '';
        const confidence = alternatives.length > 0 ? alternatives[0].confidence : 0;
        
        res.json({
          results: results.map(result => ({
            alternatives: result.alternatives.map(alt => ({
              transcript: alt.transcript,
              confidence: alt.confidence
            }))
          })),
          text: transcript,
          confidence
        });
      }
    );
  } catch (error) {
    console.error('Error in ASR endpoint:', error);
    res.status(500).json({
      error: 'Internal server error',
      details: error.message
    });
  }
});

// Create an HTTP server and wrap the Express app
const server = http.createServer(app);

// Create a WebSocket server
// Map the WebSocket path to match client expectation
const wss = new WebSocket.Server({ 
  server, 
  path: '/streaming/asr' 
});

console.log(`WebSocket server initialized at path: /streaming/asr`);

// Set up WebSocket connection for streaming recognition
wss.on('connection', (ws, req) => {
  console.log('Client connected to streaming ASR from:', req.socket.remoteAddress);

  // Create streaming call when client connects
  let call = null;
  let isFirstMessage = true;
  let sampleRate = 16000; // Default sample rate
  let receivedAudioSize = 0;
  let audioChunks = 0;
  let lastLogTime = Date.now();
  
  ws.on('message', async (message) => {
    try {
      // Log occasional processing information
      const now = Date.now();
      if (now - lastLogTime > 5000) {  // Log every 5 seconds
        console.log(`Streaming stats: ${audioChunks} chunks, total ${receivedAudioSize} bytes, avg chunk size: ${audioChunks > 0 ? Math.round(receivedAudioSize/audioChunks) : 0} bytes`);
        lastLogTime = now;
      }
      
      // Check if ASR service is available
      if (!serviceStatus.asr.available) {
        console.error('ASR service unavailable during streaming');
        ws.send(JSON.stringify({ error: 'ASR service unavailable' }));
        ws.close();
        return;
      }

      // If this is a configuration message (first message)
      if (isFirstMessage) {
        try {
          const config = JSON.parse(message.toString());
          console.log('Received config for streaming recognition:', config);
          
          sampleRate = config.sampleRate || 16000;
          const encoding = config.encoding || 'LINEAR_PCM';
          
          // Initialize streaming call
          console.log('Initializing streaming recognition call to Riva server');
          call = asrClient.StreamingRecognize();
          
          // Handle responses from the server
          call.on('data', (response) => {
            console.log('Streaming recognition response:', 
              response.results ? 
              `${response.results.length} results, is_final: ${response.results[0]?.is_final}` : 
              'No results');
            
            if (response.results && response.results.length > 0 && 
                response.results[0].alternatives && 
                response.results[0].alternatives.length > 0) {
              console.log('Transcript:', response.results[0].alternatives[0].transcript);
            }
            
            // Format the response for the frontend
            // Make sure each result has an alternatives array with transcript
            const formattedResults = response.results?.map(result => {
              // Log the structure of the incoming result
              console.log('Raw Riva result structure:', JSON.stringify(result));
              
              // Create a properly formatted result with alternatives array
              return {
                alternatives: result.alternatives?.map(alt => ({
                  transcript: alt.transcript || '',
                  confidence: alt.confidence || 0
                })) || [],
                is_final: result.is_final
              };
            }) || [];
            
            // Send response to client
            if (ws.readyState === ws.OPEN) {
              ws.send(JSON.stringify({
                results: formattedResults,
                isPartial: response.results && response.results.length > 0 ? 
                  !response.results[0].is_final : true
              }));
            }
          });
          
          call.on('error', (err) => {
            console.error('Streaming recognition error:', err);
            if (ws.readyState === ws.OPEN) {
              ws.send(JSON.stringify({ error: err.message }));
            }
          });
          
          call.on('end', () => {
            console.log('Streaming recognition ended');
          });
          
          // Send initial configuration message
          console.log('Sending streaming config to Riva server', {
            encoding,
            sampleRate,
            languageCode: "en-US"
          });
          
          call.write({
            streaming_config: {
              config: {
                encoding: encoding,
                sample_rate_hertz: sampleRate,
                language_code: "en-US",
                max_alternatives: 1,
                enable_automatic_punctuation: true
              },
              interim_results: true
            }
          });
          
          isFirstMessage = false;
          console.log('Configuration complete, ready to process audio');
        } catch (err) {
          console.error('Error processing config message:', err);
          ws.send(JSON.stringify({ error: 'Invalid configuration message' }));
          ws.close();
        }
      } else {
        // This is an audio data message
        if (call) {
          // Check message type and convert to appropriate buffer
          let audioData;
          
          // Handle different message types for maximum compatibility
          if (Buffer.isBuffer(message)) {
            audioData = message;
            console.log(`Received audio buffer, size: ${message.length} bytes`);
          } else if (message instanceof ArrayBuffer || ArrayBuffer.isView(message)) {
            // Handle ArrayBuffer or typed array view (Int16Array, etc.)
            audioData = Buffer.from(message);
            console.log(`Received ArrayBuffer, size: ${audioData.length} bytes`);
          } else if (typeof message === 'string') {
            // Try to parse as JSON if it's a string
            try {
              const parsedMessage = JSON.parse(message);
              if (parsedMessage.audio) {
                audioData = Buffer.from(parsedMessage.audio, 'base64');
                console.log(`Received JSON with base64 audio, decoded size: ${audioData.length} bytes`);
              } else {
                audioData = Buffer.from(message, 'base64');
                console.log(`Received base64 string, decoded size: ${audioData.length} bytes`);
              }
            } catch (e) {
              // If not valid JSON, assume it's a base64 string
              audioData = Buffer.from(message, 'base64');
              console.log(`Received base64 string (not JSON), decoded size: ${audioData.length} bytes`);
            }
          } else {
            // If we can't determine the type, log and skip
            console.warn(`Received unknown message type: ${typeof message}, skipping`);
            return;
          }

          // Update tracking stats
          receivedAudioSize += audioData.length;
          audioChunks++;
          
          // Log audio data details occasionally
          if (audioChunks === 1 || audioChunks % 100 === 0) {
            console.log(`Received ${audioChunks} audio chunks, total size: ${receivedAudioSize} bytes`);
          }

          // Send audio data to the streaming recognition call
          try {
            call.write({
              audio_content: audioData
            });
          } catch (err) {
            console.error('Error sending audio to Riva:', err);
          }
        } else {
          console.warn('Received audio data but no active streaming call exists');
        }
      }
    } catch (error) {
      console.error('Error in WebSocket message handling:', error);
      ws.send(JSON.stringify({ error: 'Server error processing audio' }));
    }
  });

  // Handle client disconnect
  ws.on('close', () => {
    console.log('Client disconnected from streaming ASR');
    if (call) {
      try {
        console.log(`Streaming session ended: processed ${audioChunks} chunks, total ${receivedAudioSize} bytes`);
        call.end();
      } catch (err) {
        console.error('Error ending streaming call:', err);
      }
    }
  });

  // Handle errors
  ws.on('error', (error) => {
    console.error('WebSocket error:', error);
    if (call) {
      try {
        call.end();
      } catch (err) {
        console.error('Error ending streaming call:', err);
      }
    }
  });
});

// Start the server
server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
