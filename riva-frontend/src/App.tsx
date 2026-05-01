import React, { useState, useRef, useEffect } from 'react';
import './App.css';

interface AudioConfig {
  encoding: string;
  sampleRateHertz: number;
  languageCode: string;
  enableAutomaticPunctuation?: boolean;
  enableWordTimeOffsets?: boolean;
  maxAlternatives?: number;
}

interface WavHeader {
  chunkId: string;
  chunkSize: number;
  format: string;
  subchunk1Id: string;
  subchunk1Size: number;
  audioFormat: number;
  numChannels: number;
  sampleRate: number;
  byteRate: number;
  blockAlign: number;
  bitsPerSample: number;
  subchunk2Id: string;
  subchunk2Size: number;
}

class RivaProxyClient {
  public serverUrl: string;
  
  constructor(serverUrl: string = 'http://localhost:3002') {
    this.serverUrl = serverUrl;
    console.log(`RivaProxyClient initialized with server URL: ${this.serverUrl}`);
  }
  
  async recognize(audio: string, config: any = {}): Promise<any> {
    console.log(`Recognize request to ${this.serverUrl}/api/recognize with config:`, config);
    console.log(`Audio data length: ${audio.length} characters`);
    
    try {
      console.log("Preparing fetch request...");
      
      const response = await fetch(`${this.serverUrl}/api/recognize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({
          audio,
          config,
        }),
      });

      console.log("Response status:", response.status);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error(`Server error (${response.status}):`, errorText);
        throw new Error(`Server error: ${response.status} ${errorText}`);
      }

      const result = await response.json();
      console.log("Recognition response received:", result);
      return result;
    } catch (error) {
      console.error('Error recognizing speech:', error);
      // Try to determine if it's a CORS error
      if (error instanceof TypeError && (error as any).message.includes('NetworkError')) {
        console.error('Possible CORS issue - check server CORS configuration');
      }
      throw error;
    }
  }
}

// Add WAV file creation utilities
interface WavHeader {
  numChannels: number;
  sampleRate: number;
  bitsPerSample: number;
}

// Function to create a WAV file from audio data
const createWavFile = (audioData: ArrayBuffer, options: WavHeader): ArrayBuffer => {
  const numChannels = options.numChannels || 1;
  const sampleRate = options.sampleRate || 16000;
  const bitsPerSample = options.bitsPerSample || 16;
  
  // Calculate sizes based on the audio data
  const dataSize = audioData.byteLength;
  const byteRate = (sampleRate * numChannels * bitsPerSample) / 8;
  const blockAlign = (numChannels * bitsPerSample) / 8;
  const headerSize = 44; // Standard WAV header size
  const totalSize = headerSize + dataSize;
  
  // Create the WAV buffer including header
  const wavBuffer = new ArrayBuffer(totalSize);
  const view = new DataView(wavBuffer);
  
  // Write WAV header
  // "RIFF" chunk descriptor
  writeString(view, 0, 'RIFF');
  view.setUint32(4, 36 + dataSize, true); // File size minus RIFF and size field
  writeString(view, 8, 'WAVE');
  
  // "fmt " sub-chunk
  writeString(view, 12, 'fmt ');
  view.setUint32(16, 16, true); // Size of fmt chunk (16 bytes)
  view.setUint16(20, 1, true); // Format code: 1 = PCM
  view.setUint16(22, numChannels, true); // Number of channels
  view.setUint32(24, sampleRate, true); // Sample rate
  view.setUint32(28, byteRate, true); // Byte rate
  view.setUint16(32, blockAlign, true); // Block align
  view.setUint16(34, bitsPerSample, true); // Bits per sample
  
  // "data" sub-chunk
  writeString(view, 36, 'data');
  view.setUint32(40, dataSize, true); // Size of the data chunk
  
  // Copy audio data after header
  new Uint8Array(wavBuffer).set(new Uint8Array(audioData), 44);
  
  return wavBuffer;
};

// Helper function to write a string into a DataView at a specific offset
const writeString = (view: DataView, offset: number, string: string) => {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i));
  }
};

function App() {
  const [text, setText] = useState('');
  const [recognitionError, setRecognitionError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [isFinalResult, setIsFinalResult] = useState(true);
  const [serverConnected, setServerConnected] = useState<boolean | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [isCheckingServer, setIsCheckingServer] = useState(false);
  
  // Determine server URL based on environment
  const getServerUrl = (): string => {
    // Always connect directly to the server at port 3002
    const serverUrl = 'http://localhost:3002';
    console.log(`Using direct server connection to ${serverUrl}`);
    return serverUrl;
  };
  
  const audioChunksRef = useRef<Blob[]>([]);
  const rivaClient = useRef<RivaProxyClient>(new RivaProxyClient(getServerUrl()));
  const fileInputRef = useRef<HTMLInputElement>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const streamProcessorRef = useRef<ScriptProcessorNode | null>(null);
  
  // Initialize Audio Context and check server connectivity
  useEffect(() => {
    const init = async () => {
      try {
        console.log("App initializing...");
        
        // Check audio context
        audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
        console.log("Audio context initialized with sample rate:", audioContextRef.current.sampleRate);
        
        // Check server connectivity - add retry logic
        await checkServerConnectivity();
        
        // If initial connectivity check failed, retry after a delay
        if (!serverConnected) {
          console.log("Initial server connectivity check failed, retrying in 2 seconds...");
          setTimeout(async () => {
            await checkServerConnectivity();
          }, 2000);
        }
      } catch (error) {
        console.error("Error during initialization:", error);
        setServerConnected(false);
        setServerError((error as Error).message || "Unknown initialization error");
      }
    };
    
    init();
    
    return () => {
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
      
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Function to check server connectivity
  const checkServerConnectivity = async () => {
    setIsCheckingServer(true);
    
    const healthEndpoint = `${rivaClient.current.serverUrl}/health`;
    console.log(`Checking server connectivity at ${healthEndpoint}...`);
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout
      
      try {
        const response = await fetch(healthEndpoint, {
          method: 'GET',
          headers: {
            'Accept': 'application/json'
          },
          signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        // Log full response details for debugging
        console.log(`Server responded with status: ${response.status}`);
        
        if (response.ok) {
          const data = await response.json();
          console.log(`Server health check successful:`, data);
          setServerConnected(true);
          setServerError(null);
          return true;
        } else {
          const errorText = await response.text();
          console.error(`Server returned error status: ${response.status}`, errorText);
          setServerConnected(false);
          setServerError(`Server error: ${response.status} - ${errorText}`);
          return false;
        }
      } catch (fetchError: any) {
        clearTimeout(timeoutId);
        if (fetchError.name === 'AbortError') {
          console.error('Server health check timed out after 5 seconds');
          setServerConnected(false);
          setServerError("Connection timed out. Please check if the server is running and accessible.");
        } else if (fetchError.message && fetchError.message.includes('NetworkError')) {
          // Specifically handle CORS errors
          console.error('Possible CORS issue:', fetchError);
          setServerConnected(false);
          setServerError("Network error - possibly due to CORS restrictions. Please check server configuration.");
        } else {
          console.error('Server connectivity check failed:', fetchError);
          setServerConnected(false);
          setServerError(fetchError.message || "Unknown connection error");
        }
        return false;
      }
    } catch (error) {
      console.error('Server connectivity check error:', error);
      setServerConnected(false);
      setServerError((error as Error).message || "Unknown server connection error");
      return false;
    } finally {
      setIsCheckingServer(false);
    }
  };

  // Helper function to convert ArrayBuffer to base64
  const arrayBufferToBase64 = (buffer: ArrayBuffer): string => {
    let binary = '';
    const bytes = new Uint8Array(buffer);
    const len = bytes.byteLength;
    
    for (let i = 0; i < len; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    
    return window.btoa(binary);
  };

  const startStreaming = async () => {
    try {
      setIsStreaming(true);
      setStreamingText('');
      setRecognitionError(null);
      
      console.log("Starting streaming recognition...");
      
      // Use more permissive audio constraints - browser's default processing often works better
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: { 
          // Less restrictive constraints to let the browser optimize
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
          // Don't force channelCount or sampleRate as browser defaults often work better
        } 
      });
      
      console.log("Audio stream obtained with constraints:", stream.getAudioTracks()[0].getSettings());
      
      // Create audio context
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      
      console.log("Audio context sample rate:", audioContextRef.current.sampleRate);
      
      // Create WebSocket connection
      console.log("Creating WebSocket connection for streaming...");
      
      // Construct WebSocket URL from server URL
      const wsUrl = rivaClient.current.serverUrl.replace('http', 'ws') + '/streaming/asr';
      console.log("WebSocket URL:", wsUrl);
      
      wsRef.current = new WebSocket(wsUrl);
      
      // Debug connection state
      console.log("Initial WebSocket state:", wsRef.current.readyState);
      
      // Add more detailed WebSocket event handlers for debugging
      wsRef.current.onopen = () => {
        console.log("WebSocket connection established, sending config...");
        
        // Send configuration once connection is open
        const config = {
          sampleRate: 16000, // Always use 16kHz for Riva
          encoding: 'LINEAR_PCM',
          languageCode: 'en-US',
          maxAlternatives: 1,
          enableAutomaticPunctuation: true
        };
        
        console.log("Sending streaming config:", config);
        
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify(config));
          console.log("Config sent successfully");
        } else {
          console.error("WebSocket is not open, cannot send config", wsRef.current?.readyState);
          setRecognitionError("WebSocket connection failed. Please try again.");
          stopStreaming();
        }
      };
      
      wsRef.current.onmessage = (event) => {
        try {
          const response = JSON.parse(event.data);
          if (response.error) {
            console.error("Streaming recognition error:", response.error);
            setRecognitionError(`Streaming error: ${response.error}`);
            stopStreaming();
            return;
          }
          
          console.log("Received streaming response:", response);
          
          if (response.results && response.results.length > 0) {
            const result = response.results[0];
            // Log the full result structure to debug
            console.log("Streaming result structure:", JSON.stringify(result));
            
            // Check if alternatives exists directly in the result object
            if (result.alternatives && result.alternatives.length > 0) {
              const transcript = result.alternatives[0].transcript || '';
              console.log(`Transcript [${response.isPartial ? 'interim' : 'final'}]: ${transcript}`);
              
              setStreamingText(transcript);
              setIsFinalResult(!response.isPartial);
              
              // If we have a final result, append it to the text area automatically
              if (!response.isPartial && transcript) {
                setText((prevText) => {
                  const newText = prevText ? 
                    `${prevText} ${transcript}` : 
                    transcript;
                  return newText;
                });
              }
            } 
            // If no alternatives directly in result, try the standard Riva structure
            else if (result && result.alternatives && result.alternatives.length > 0) {
              const transcript = result.alternatives[0].transcript || '';
              console.log(`Transcript [${response.isPartial ? 'interim' : 'final'}]: ${transcript}`);
              
              setStreamingText(transcript);
              setIsFinalResult(!response.isPartial);
              
              // If we have a final result, append it to the text area automatically
              if (!response.isPartial && transcript) {
                setText((prevText) => {
                  const newText = prevText ? 
                    `${prevText} ${transcript}` : 
                    transcript;
                  return newText;
                });
              }
            }
            // Debug if we couldn't find transcript
            else {
              console.warn("Could not find alternatives in the streaming result:", result);
            }
          } else {
            console.log("No results in streaming response");
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
      
      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setRecognitionError('WebSocket connection error. Check the server connection.');
        stopStreaming();
      };
      
      wsRef.current.onclose = (event) => {
        console.log(`WebSocket connection closed with code ${event.code}: ${event.reason || 'No reason provided'}`);
        
        // Show appropriate error message based on the close code
        if (event.code !== 1000) { // 1000 is normal closure
          let errorMessage = "Connection to speech recognition server lost.";
          
          if (event.code === 1006) {
            errorMessage = "Abnormal connection closure. The server might be down.";
          } else if (event.code === 1008 || event.code === 1011) {
            errorMessage = "Server error: " + (event.reason || "Unknown error");
          }
          
          setRecognitionError(errorMessage);
        }
        
        if (isStreaming) {
          stopStreaming();
        }
      };
      
      // Create audio processing pipeline
      console.log("Setting up audio processing pipeline...");
      const source = audioContextRef.current.createMediaStreamSource(stream);
      
      // Create a gain node to boost the audio signal
      const gainNode = audioContextRef.current.createGain();
      gainNode.gain.value = 2.0; // Boost the volume more significantly
      
      // Use smaller buffer size for lower latency
      // Try to use a power of 2 buffer size for better performance 
      const bufferSize = 4096; // Larger buffer might be more stable
      const processor = audioContextRef.current.createScriptProcessor(bufferSize, 1, 1);
      streamProcessorRef.current = processor;
      
      // Log important audio context info
      console.log(`Audio context state: ${audioContextRef.current.state}`);
      console.log(`Audio context sample rate: ${audioContextRef.current.sampleRate}Hz`);
      console.log(`ScriptProcessor buffer size: ${bufferSize}`);
      
      // If audio context is suspended (happens in some browsers), resume it
      if (audioContextRef.current.state === 'suspended') {
        console.log("Resuming suspended audio context...");
        audioContextRef.current.resume().then(() => {
          console.log("Audio context resumed successfully");
        }).catch(err => {
          console.error("Failed to resume audio context:", err);
          setRecognitionError("Failed to access microphone. Please check permissions.");
          stopStreaming();
        });
      }
      
      // Add visualization if the audio context exists
      if (audioContextRef.current) {
        try {
          const analyser = audioContextRef.current.createAnalyser();
          analyser.fftSize = 256;
          source.connect(analyser);
          
          // Store the analyser for visualization updates
          const bufferLength = analyser.frequencyBinCount;
          const dataArray = new Uint8Array(bufferLength);
          
          // Update visualization every 50ms
          const updateVisualization = () => {
            if (!isStreaming) return;
            
            analyser.getByteFrequencyData(dataArray);
            
            // Calculate average volume level (simple approach)
            let sum = 0;
            for (let i = 0; i < bufferLength; i++) {
              sum += dataArray[i];
            }
            const average = sum / bufferLength;
            
            // Update volume indicator
            const volumeIndicator = document.getElementById('volume-indicator');
            if (volumeIndicator) {
              volumeIndicator.style.width = `${Math.min(100, average * 2)}%`;
              
              // Change color based on volume level
              if (average < 5) {
                volumeIndicator.style.backgroundColor = '#cccccc'; // Gray for silence
              } else if (average < 20) {
                volumeIndicator.style.backgroundColor = '#ff9800'; // Orange for low volume
              } else {
                volumeIndicator.style.backgroundColor = '#4CAF50'; // Green for good volume
              }
            }
            
            // Continue animation if still streaming
            if (isStreaming) {
              requestAnimationFrame(updateVisualization);
            }
          };
          
          // Start visualization
          updateVisualization();
        } catch (vizError) {
          console.error('Could not initialize audio visualization:', vizError);
          // Continue without visualization
        }
      }
      
      // Need to resample if browser's sample rate is not 16kHz
      const browserSampleRate = audioContextRef.current.sampleRate;
      const targetSampleRate = 16000;
      const resample = browserSampleRate !== targetSampleRate;
      
      console.log(`Audio will ${resample ? 'be resampled from ' + browserSampleRate + 'Hz to ' + targetSampleRate + 'Hz' : 'not be resampled'}`);
      
      // Connect nodes: source -> gain -> processor -> destination
      source.connect(gainNode);
      gainNode.connect(processor);
      processor.connect(audioContextRef.current.destination);
      
      console.log("Audio processing pipeline connected");
      
      // Add a simple diagnostic timer to check if audio is being processed
      let frameCount = 0;
      const diagnosticInterval = setInterval(() => {
        if (isStreaming) {
          console.log(`Audio diagnostic: processed ${frameCount} frames since last check`);
          
          if (frameCount === 0) {
            console.warn("No audio frames processed! Check microphone permissions and connections.");
            // Update UI to show a warning
            setRecognitionError(prev => prev || "No audio detected. Please check your microphone.");
          }
          
          // Reset counter for next interval
          frameCount = 0;
        } else {
          clearInterval(diagnosticInterval);
        }
      }, 5000); // Check every 5 seconds
      
      // Audio processing function - convert and send audio data
      processor.onaudioprocess = (e) => {
        // Increment frame counter for diagnostics
        frameCount++;
        
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          // Get raw audio data
          const inputData = e.inputBuffer.getChannelData(0);
          
          // Log occasionally to debug audio data
          if (Math.random() < 0.01) {  // ~1% of frames
            // Calculate RMS to check audio level
            let sum = 0;
            for (let i = 0; i < inputData.length; i++) {
              sum += inputData[i] * inputData[i];
            }
            const rms = Math.sqrt(sum / inputData.length);
            console.log(`Audio frame: length=${inputData.length}, rms=${rms.toFixed(6)}`);
            
            if (rms < 0.001) {
              console.warn("Very low audio level detected. Check your microphone.");
            }
          }
          
          // Resample to 16kHz if needed
          const browserSampleRate = audioContextRef.current!.sampleRate;
          const targetSampleRate = 16000;
          let audioToSend = inputData;
          
          if (browserSampleRate !== targetSampleRate) {
            // Simple linear resampling
            const ratio = browserSampleRate / targetSampleRate;
            const newLength = Math.floor(inputData.length / ratio);
            const resampled = new Float32Array(newLength);
            
            for (let i = 0; i < newLength; i++) {
              const originalIndex = Math.floor(i * ratio);
              resampled[i] = inputData[originalIndex];
            }
            
            audioToSend = resampled;
            
            // Log resampling occasionally
            if (Math.random() < 0.01) {
              console.log(`Resampled audio: ${browserSampleRate}Hz → ${targetSampleRate}Hz, 
                          ${inputData.length} → ${resampled.length} samples`);
            }
          }
          
          // Convert to Int16 PCM (what Riva expects)
          const pcmData = new Int16Array(audioToSend.length);
          for (let i = 0; i < audioToSend.length; i++) {
            // Scale to int16 range (-32768 to 32767)
            // Apply a gain multiplier to boost the audio signal
            const gain = 1.5; // Boost by 50%
            const sample = Math.max(-1, Math.min(1, audioToSend[i] * gain));
            pcmData[i] = Math.floor(sample * 32767);
          }
          
          // Send the audio data as binary
          wsRef.current.send(pcmData.buffer);
        } else if (wsRef.current) {
          console.warn("WebSocket not open, state:", wsRef.current.readyState);
        }
      };
      
      console.log("Streaming recognition started successfully");
      
    } catch (error) {
      console.error('Error starting streaming:', error);
      setRecognitionError(`Error starting streaming: ${(error as Error).message}`);
      setIsStreaming(false);
    }
  };

  const stopStreaming = () => {
    console.log("Stopping streaming recognition...");
    
    // Disconnect audio processing
    if (streamProcessorRef.current && audioContextRef.current) {
      console.log("Disconnecting audio processor");
      try {
        streamProcessorRef.current.disconnect();
        console.log("Audio processor disconnected");
      } catch (e) {
        console.error("Error disconnecting audio processor:", e);
      }
      streamProcessorRef.current = null;
    }
    
    // Close WebSocket properly
    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
        console.log(`Closing WebSocket connection (state: ${wsRef.current.readyState})`);
        try {
          // Send a clean close frame
          wsRef.current.close(1000, "Client ended streaming session");
          console.log("WebSocket closed cleanly");
        } catch (e) {
          console.error("Error closing WebSocket:", e);
        }
      } else {
        console.log(`WebSocket already closing/closed (state: ${wsRef.current.readyState})`);
      }
      wsRef.current = null;
    }
    
    setIsStreaming(false);
    setIsFinalResult(true);
    console.log("Streaming recognition stopped");
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files && event.target.files[0];
    
    console.log("File upload initiated:", file ? `${file.name} (${file.type}, ${file.size} bytes)` : "No file selected");
    
    if (file) {
      // Check if it's an audio file
      if (!file.type.startsWith('audio/')) {
        console.error("Not an audio file:", file.type);
        setRecognitionError('Please upload an audio file.');
        return;
      }
      
      const reader = new FileReader();
      
      reader.onload = async (e) => {
        try {
          console.log("File read complete, processing audio...");
          
          if (e.target && e.target.result) {
            const arrayBuffer = e.target.result as ArrayBuffer;
            console.log("Audio file loaded, size:", arrayBuffer.byteLength, "bytes");
            
            if (file.type === 'audio/wav' || file.type === 'audio/x-wav' || file.name.endsWith('.wav')) {
              console.log("WAV file detected, saving locally for verification");
            }
            
            // Convert to base64 for sending to the server
            console.log("Converting audio to base64...");
            const base64Audio = arrayBufferToBase64(arrayBuffer);
            console.log("Base64 conversion complete, length:", base64Audio.length);
            
            // Check server URL before sending
            console.log("Using server URL:", rivaClient.current.serverUrl);
            
            // Recognize speech
            console.log("Sending audio to server for recognition...");
            const result = await rivaClient.current.recognize(base64Audio, {
              encoding: 'LINEAR_PCM',
              sampleRateHertz: 16000,
              languageCode: 'en-US',
              enableAutomaticPunctuation: true
            });
            
            console.log("Recognition result received:", result);
            
            if (result && result.results && result.results.length > 0) {
              const transcript = result.results[0]?.alternatives?.[0]?.transcript || 'No transcription available';
              console.log("Setting transcript:", transcript);
              setText(transcript);
            } else {
              console.log("No valid transcription in results");
              setText('No transcription available');
            }
          }
        } catch (error) {
          console.error('Error processing uploaded file:', error);
          setRecognitionError(`Error processing file: ${(error as Error).message}`);
        }
      };
      
      reader.onerror = (event) => {
        console.error('Error reading the file:', event);
        setRecognitionError('Error reading the file.');
      };
      
      console.log("Starting file read as ArrayBuffer...");
      reader.readAsArrayBuffer(file);
    }
  };

  const handleUploadButtonClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Riva AI Voice Services</h1>
      </header>
      
      <main>
        <section className="recognition-section">
          <h2>Speech Recognition</h2>
          
          {serverConnected === false && (
            <div className="server-status error-message">
              <p>⚠️ {serverError || "Could not connect to the backend server. Please ensure the server is running on port 3002."}</p>
              <button 
                onClick={checkServerConnectivity} 
                disabled={isCheckingServer}
                className="retry-button"
              >
                {isCheckingServer ? 'Checking...' : 'Retry Connection'}
              </button>
            </div>
          )}
          
          <div className="card">
            <h3>Speech Recognition</h3>
            <div className="button-group">
              <button onClick={handleUploadButtonClick}>
                Upload Audio File
              </button>
              
              <button 
                onClick={isStreaming ? stopStreaming : startStreaming}
                className={isStreaming ? 'recording' : ''}
              >
                {isStreaming ? 'Stop Streaming' : 'Start Streaming'}
              </button>
              
              <input 
                type="file" 
                ref={fileInputRef}
                onChange={handleFileUpload}
                accept="audio/*"
                style={{ display: 'none' }}
              />
            </div>
            
            {recognitionError && (
              <div className="error-message">
                {recognitionError}
              </div>
            )}
            
            {isStreaming && (
              <div className="volume-container">
                <div id="volume-indicator" className="volume-indicator"></div>
              </div>
            )}
            
            {isStreaming && (
              <div className="result-container">
                <h4>Real-time Transcription:</h4>
                {streamingText ? (
                  <p className={isFinalResult ? 'final' : 'interim'}>
                    {streamingText}
                  </p>
                ) : (
                  <p className="interim">Waiting for speech...</p>
                )}
              </div>
            )}
            
            {text && (
              <div className="result-container">
                <h4>Transcription:</h4>
                <p>{text}</p>
              </div>
            )}
            
            <div className="info-box">
              <h4>Instructions:</h4>
              <ul>
                <li>Click "Upload Audio File" to transcribe pre-recorded audio</li>
                <li>Or click "Start Streaming" to begin real-time speech recognition using your microphone</li>
                <li>When streaming, partial results will appear in gray, final results in black</li>
                <li>Click "Stop Streaming" when you are finished</li>
              </ul>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;

