import * as grpc from '@grpc/grpc-js';

export enum AudioEncoding {
    ENCODING_UNSPECIFIED = 0,
    LINEAR_PCM = 1,
    FLAC = 2,
    MULAW = 3,
    ALAW = 4
}

export interface SpeechContext {
    phrases: string[];
    boost: number;
}

export interface EndpointingConfig {
    startHistory?: number;
    startThreshold?: number;
    stopHistory?: number;
    stopHistoryEou?: number;
    stopThreshold?: number;
    stopThresholdEou?: number;
}

export interface SpeakerDiarizationConfig {
    enableSpeakerDiarization: boolean;
    minSpeakerCount?: number;
    maxSpeakerCount?: number;
}

export interface RecognitionConfig {
    encoding: AudioEncoding;
    sampleRateHertz: number;
    languageCode: string;
    audioChannelCount?: number;
    maxAlternatives?: number;
    profanityFilter?: boolean;
    enableAutomaticPunctuation?: boolean;
    enableWordTimeOffsets?: boolean;
    enableWordConfidence?: boolean;
    enableRawTranscript?: boolean;
    enableSpeakerDiarization?: boolean;
    diarizationConfig?: SpeakerDiarizationConfig;
    endpointingConfig?: EndpointingConfig;
    speechContexts?: SpeechContext[];
    customConfiguration?: Record<string, string>;
    model?: string;
}

export interface StreamingRecognitionConfig {
    config: RecognitionConfig;
    interimResults?: boolean;
    singleUtterance?: boolean;
}

export interface WordInfo {
    startTime: number;
    endTime: number;
    word: string;
    confidence: number;
    speakerTag?: string;
}

export interface SpeechRecognitionAlternative {
    transcript: string;
    confidence: number;
    words: WordInfo[];
}

export interface SpeechRecognitionResult {
    alternatives: SpeechRecognitionAlternative[];
    channelTag: number;
    languageCode: string;
    isPartial?: boolean;
}

export interface StreamingRecognizeResponse {
    results: SpeechRecognitionResult[];
    speechEventType?: 'END_OF_SINGLE_UTTERANCE' | 'SPEECH_ACTIVITY_BEGIN' | 'SPEECH_ACTIVITY_END';
    timeOffset?: number;
    audioContent?: Buffer;
}

export interface RecognizeResponse {
    results: SpeechRecognitionResult[];
}

export interface AudioChunk {
    audioContent: Uint8Array;
    timeOffset?: number;
}

export interface WavFileParameters {
    nframes: number;
    framerate: number;
    duration: number;
    nchannels: number;
    sampwidth: number;
    dataOffset: number;
}

export interface AudioSource {
    content?: Uint8Array;
    [Symbol.asyncIterator]?(): AsyncIterator<AudioChunk>;
    [Symbol.iterator]?(): Iterator<AudioChunk>;
}

export interface AudioContentSource {
    content: Uint8Array;
}

export interface ASRModel {
    name: string;
    languages: string[];
    sample_rate: number;
    streaming_supported: boolean;
}

export interface ListModelsResponse {
    models: ASRModel[];
}

export interface ASRServiceClient {
    config: RecognitionConfig;
    streamingRecognize(metadata?: grpc.Metadata): grpc.ClientDuplexStream<any, StreamingRecognizeResponse>;
    recognize(request: { config: RecognitionConfig; audio: { content: Uint8Array } }): Promise<RecognizeResponse>;
    listModels(request: {}): Promise<ListModelsResponse>;
}
