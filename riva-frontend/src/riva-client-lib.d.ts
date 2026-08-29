declare module 'riva-client-lib' {
  export enum AudioEncoding {
    ENCODING_UNSPECIFIED = 'ENCODING_UNSPECIFIED',
    LINEAR_PCM = 'LINEAR_PCM',
    FLAC = 'FLAC',
    MULAW = 'MULAW',
    ALAW = 'ALAW'
  }
  
  export interface ClientConfig {
    serverUrl: string;
    auth?: {
      ssl?: boolean;
      sslCert?: string;
      apiKey?: string;
      metadata?: Record<string, string>;
    };
    rest?: {
      baseUrl?: string;
      timeout?: number;
      headers?: Record<string, string>;
      retry?: boolean;
      maxRetries?: number;
    };
  }
  
  export interface AsrConfig {
    encoding: AudioEncoding;
    sampleRateHertz: number;
    languageCode: string;
    maxAlternatives?: number;
    enableAutomaticPunctuation?: boolean;
    enableWordTimeOffsets?: boolean;
    enableWordConfidence?: boolean;
    profanityFilter?: boolean;
    audioChannelCount?: number;
    enableSpeakerDiarization?: boolean;
    diarizationSpeakerCount?: number;
    model?: string;
  }
  
  export interface TtsConfig {
    text: string;
    voiceName?: string;
    languageCode?: string;
    encoding?: AudioEncoding;
    sampleRateHertz?: number;
    pitch?: number;
    speakingRate?: number;
    quality?: number;
    customDictionary?: Record<string, string>;
  }
  
  export interface WavFileParams {
    numFrames: number;
    frameRate: number;
    duration: number;
    numChannels: number;
    sampleWidth: number;
    dataOffset: number;
  }
  
  export interface SpeechRecognitionAlternative {
    transcript: string;
    confidence?: number;
    words?: {
      word: string;
      startTime?: number;
      endTime?: number;
      confidence?: number;
    }[];
  }
  
  export interface SpeechRecognitionResult {
    alternatives: SpeechRecognitionAlternative[];
    isFinal?: boolean;
    stability?: number;
    speakerTag?: number;
  }
  
  export interface AsrResponse {
    results: SpeechRecognitionResult[];
    isPartial?: boolean;
  }
  
  export interface TtsResponse {
    audio: {
      audioContent: string | Uint8Array;
      sampleRateHertz: number;
    };
    success: boolean;
    error?: string;
  }
  
  export interface VoiceInfo {
    name: string;
    languages: string[];
    gender?: string;
    sampleRate?: number;
  }
  
  export interface VoicesResponse {
    voices: VoiceInfo[];
  }
  
  export class AsrClient {
    constructor(config: ClientConfig);
    recognize(audioData: ArrayBuffer | ArrayBufferLike | string, config?: Partial<AsrConfig>): Promise<AsrResponse>;
    createStreamingConnection(config?: Partial<AsrConfig>): WebSocket;
  }
  
  export class TtsClient {
    constructor(config: ClientConfig);
    synthesize(text: string, config?: Partial<Omit<TtsConfig, 'text'>>): Promise<TtsResponse>;
    getVoices(): Promise<VoicesResponse>;
  }
  
  export function examineWavHeader(buffer: Uint8Array): WavFileParams | null;
  
  export function createWavFile(
    audioData: ArrayBuffer | ArrayBufferLike,
    options: { 
      numChannels?: number;
      sampleRate?: number;
      bitsPerSample?: number;
    }
  ): ArrayBuffer;
  
  export function arrayBufferToBase64(buffer: ArrayBuffer | ArrayBufferLike): string;
  export function base64ToArrayBuffer(base64: string): ArrayBuffer;
  export function stringToArrayBuffer(str: string): ArrayBuffer;
  export function arrayBufferToString(buffer: ArrayBuffer | ArrayBufferLike): string;
} 