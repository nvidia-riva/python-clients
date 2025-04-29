export enum AudioEncoding {
    ENCODING_UNSPECIFIED = 0,
    LINEAR_PCM = 1,
    FLAC = 2,
    MULAW = 3,
    ALAW = 4
}

export interface RecognitionConfig {
    encoding: AudioEncoding;
    sampleRateHertz: number;
    languageCode: string;
    enableAutomaticPunctuation?: boolean;
    enableWordTimeOffsets?: boolean;
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

export interface RecognizeResponse {
    results: SpeechRecognitionResult[];
} 