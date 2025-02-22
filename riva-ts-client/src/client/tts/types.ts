import * as grpc from '@grpc/grpc-js';
import { AudioEncoding } from '../asr/types';

export interface WaveFmt {
    sampleRate: number;
}

export interface WaveFile {
    fmt: WaveFmt;
    getSamples(): Float64Array | Float64Array[];
}

export interface ZeroShotData {
    audioPrompt: Uint8Array;
    encoding: AudioEncoding;
    sampleRateHz: number;
    quality: number;
}

export interface SynthesizeSpeechRequest {
    text: string;
    languageCode: string;
    sampleRateHz: number;
    encoding: AudioEncoding;
    voiceName?: string;
    zeroShotData?: ZeroShotData;
    customDictionary?: string;
}

export interface SynthesizeSpeechResponse {
    audio: Uint8Array;
    audioConfig: {
        encoding: AudioEncoding;
        sampleRateHz: number;
    };
}

export interface RivaSynthesisConfigRequest {
    // Empty request
}

export interface VoiceParameters {
    languageCode: string;
    voiceName: string;
    subvoices: string;
}

export interface ModelConfig {
    parameters: VoiceParameters;
}

export interface RivaSynthesisConfigResponse {
    modelConfig: ModelConfig[];
}

export interface RivaSpeechSynthesisStub extends grpc.Client {
    /**
     * Synthesizes speech synchronously
     */
    Synthesize(
        request: SynthesizeSpeechRequest,
        metadata: grpc.Metadata,
        callback: (error: grpc.ServiceError | null, response: SynthesizeSpeechResponse) => void
    ): grpc.ClientUnaryCall;

    Synthesize(
        request: SynthesizeSpeechRequest,
        metadata: grpc.Metadata
    ): Promise<SynthesizeSpeechResponse>;

    /**
     * Synthesizes speech in streaming mode, returning chunks as they become available
     */
    SynthesizeOnline(
        request: SynthesizeSpeechRequest,
        metadata: grpc.Metadata
    ): grpc.ClientReadableStream<SynthesizeSpeechResponse>;

    /**
     * Gets available voice configurations
     */
    GetRivaSynthesisConfig(
        request: RivaSynthesisConfigRequest,
        metadata: grpc.Metadata
    ): Promise<RivaSynthesisConfigResponse>;
}
