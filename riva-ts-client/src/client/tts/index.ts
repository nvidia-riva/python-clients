import * as grpc from '@grpc/grpc-js';
import * as fs from 'fs';
import { WaveFile } from 'wavefile';
import { BaseClient } from '../base';
import { RivaError, handleGrpcError } from '../errors';
import { AudioEncoding } from '../asr/types';
import { RivaConfig } from '../types';
import { getProtoClient } from '../utils/proto';
import {
    SynthesizeSpeechRequest,
    SynthesizeSpeechResponse,
    ZeroShotData,
    RivaSpeechSynthesisStub,
    WaveFile as WaveFileType,
    RivaSynthesisConfigResponse
} from './types';

function convertSamplesToBuffer(samples: Float64Array | Float64Array[]): Buffer {
    if (Array.isArray(samples)) {
        // Multi-channel audio
        const flatSamples = new Float64Array(samples.reduce((acc: number[], channel) => {
            channel.forEach(sample => acc.push(sample));
            return acc;
        }, []));
        return Buffer.from(flatSamples.buffer);
    } else {
        // Single channel audio
        return Buffer.from(samples.buffer);
    }
}

/**
 * Add custom dictionary to synthesis request config
 */
function addCustomDictionaryToConfig(
    req: SynthesizeSpeechRequest,
    customDictionary?: Record<string, string>
): void {
    if (customDictionary) {
        const resultList = Object.entries(customDictionary).map(([key, value]) => `${key}  ${value}`);
        if (resultList.length > 0) {
            req.customDictionary = resultList.join(',');
        }
    }
}

/**
 * A class for synthesizing speech from text. Provides synthesize which returns entire audio for a text
 * and synthesizeOnline which returns audio in small chunks as it is becoming available.
 */
export class SpeechSynthesisService extends BaseClient {
    private readonly stub: RivaSpeechSynthesisStub;

    /**
     * Initializes an instance of the class.
     * @param config Configuration for the service
     */
    constructor(config: RivaConfig) {
        super(config);
        const { RivaSpeechSynthesisStub } = getProtoClient('riva_services');
        this.stub = new RivaSpeechSynthesisStub(
            config.serverUrl,
            config.auth?.credentials || grpc.credentials.createInsecure()
        );
    }

    /**
     * Gets the available voices and their configurations
     * @returns Promise with the synthesis configuration response
     */
    async getRivaSynthesisConfig(): Promise<RivaSynthesisConfigResponse> {
        try {
            return await this.stub.GetRivaSynthesisConfig({}, this.getCallMetadata());
        } catch (error: unknown) {
            if (error instanceof Error) {
                throw error;
            }
            throw new RivaError('Unknown error occurred');
        }
    }

    /**
     * Synthesizes an entire audio for text.
     * @param text An input text.
     * @param voiceName A name of the voice, e.g. "English-US-Female-1". If null, server will select first available model.
     * @param languageCode A language to use.
     * @param encoding An output audio encoding, e.g. AudioEncoding.LINEAR_PCM.
     * @param sampleRateHz Number of frames per second in output audio.
     * @param audioPromptFile An audio prompt file location for zero shot model.
     * @param audioPromptEncoding Encoding of audio prompt file, e.g. AudioEncoding.LINEAR_PCM.
     * @param quality This defines the number of times decoder is run. Higher number improves quality but takes longer.
     * @param future Whether to return an async result instead of usual response.
     * @param customDictionary Dictionary with key-value pair containing grapheme and corresponding phoneme
     */
    async synthesize(
        text: string,
        voiceName?: string,
        languageCode: string = 'en-US',
        encoding: AudioEncoding = AudioEncoding.LINEAR_PCM,
        sampleRateHz: number = 44100,
        audioPromptFile?: string,
        audioPromptEncoding: AudioEncoding = AudioEncoding.LINEAR_PCM,
        quality: number = 20,
        future: boolean = false,
        customDictionary?: Record<string, string>
    ): Promise<SynthesizeSpeechResponse> {
        const req: SynthesizeSpeechRequest = {
            text,
            languageCode,
            sampleRateHz,
            encoding
        };

        if (voiceName) {
            req.voiceName = voiceName;
        }

        if (audioPromptFile) {
            const wavFile = new WaveFile(fs.readFileSync(audioPromptFile)) as WaveFileType;
            const samples = wavFile.getSamples();
            if (!samples || (Array.isArray(samples) && !samples.length)) {
                throw new RivaError('Invalid WAV file: no samples found');
            }
            if (!wavFile.fmt?.sampleRate) {
                throw new RivaError('Invalid WAV file: no sample rate found');
            }

            const zeroShotData: ZeroShotData = {
                audioPrompt: convertSamplesToBuffer(samples),
                encoding: audioPromptEncoding,
                sampleRateHz: wavFile.fmt.sampleRate,
                quality
            };
            req.zeroShotData = zeroShotData;
        }

        addCustomDictionaryToConfig(req, customDictionary);

        try {
            return await this.stub.Synthesize(req, this.getCallMetadata());
        } catch (error) {
            if (error instanceof Error) {
                throw handleGrpcError(error);
            }
            throw new RivaError('Unknown error during synthesis');
        }
    }

    /**
     * Synthesizes and yields output audio chunks for text as the chunks becoming available.
     * @param text An input text.
     * @param voiceName A name of the voice, e.g. "English-US-Female-1". If null, server will select first available model.
     * @param languageCode A language to use.
     * @param encoding An output audio encoding, e.g. AudioEncoding.LINEAR_PCM.
     * @param sampleRateHz Number of frames per second in output audio.
     * @param audioPromptFile An audio prompt file location for zero shot model.
     * @param audioPromptEncoding Encoding of audio prompt file, e.g. AudioEncoding.LINEAR_PCM.
     * @param quality This defines the number of times decoder is run. Higher number improves quality but takes longer.
     * @param customDictionary Dictionary with key-value pair containing grapheme and corresponding phoneme
     */
    async *synthesizeOnline(
        text: string,
        voiceName?: string,
        languageCode: string = 'en-US',
        encoding: AudioEncoding = AudioEncoding.LINEAR_PCM,
        sampleRateHz: number = 44100,
        audioPromptFile?: string,
        audioPromptEncoding: AudioEncoding = AudioEncoding.LINEAR_PCM,
        quality: number = 20,
        customDictionary?: Record<string, string>
    ): AsyncGenerator<SynthesizeSpeechResponse, void, unknown> {
        const req: SynthesizeSpeechRequest = {
            text,
            languageCode,
            sampleRateHz,
            encoding
        };

        if (voiceName) {
            req.voiceName = voiceName;
        }

        if (audioPromptFile) {
            const wavFile = new WaveFile(fs.readFileSync(audioPromptFile)) as WaveFileType;
            const samples = wavFile.getSamples();
            if (!samples || (Array.isArray(samples) && !samples.length)) {
                throw new RivaError('Invalid WAV file: no samples found');
            }
            if (!wavFile.fmt?.sampleRate) {
                throw new RivaError('Invalid WAV file: no sample rate found');
            }

            const zeroShotData: ZeroShotData = {
                audioPrompt: convertSamplesToBuffer(samples),
                encoding: audioPromptEncoding,
                sampleRateHz: wavFile.fmt.sampleRate,
                quality
            };
            req.zeroShotData = zeroShotData;
        }

        addCustomDictionaryToConfig(req, customDictionary);

        try {
            const stream = this.stub.SynthesizeOnline(req, this.getCallMetadata());
            for await (const response of stream) {
                yield response;
            }
        } catch (error) {
            if (error instanceof Error) {
                throw handleGrpcError(error);
            }
            throw new RivaError('Unknown error during streaming synthesis');
        }
    }
}
