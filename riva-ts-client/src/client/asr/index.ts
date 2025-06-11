import * as grpc from '@grpc/grpc-js';
import { BaseClient } from '../base';
import { RivaError, handleGrpcError } from '../errors';
import * as fs from 'fs';
import * as path from 'path';
import {
    ASRServiceClient,
    AudioChunk,
    AudioSource,
    AudioContentSource,
    RecognitionConfig,
    RecognizeResponse,
    StreamingRecognitionConfig,
    StreamingRecognizeResponse,
    SpeechContext,
    SpeakerDiarizationConfig,
    EndpointingConfig,
    WavFileParameters,
    AudioEncoding,
    ListModelsResponse
} from './types';
import { getProtoClient } from '../utils/proto';

/**
 * Get WAV file parameters
 * @param filePath Path to WAV file
 */
export function getWavFileParameters(filePath: string): WavFileParameters | null {
    try {
        const buffer = fs.readFileSync(filePath);
        if (buffer.toString('ascii', 0, 4) !== 'RIFF' || buffer.toString('ascii', 8, 12) !== 'WAVE') {
            return null;
        }

        // Parse WAV header
        const sampleRate = buffer.readUInt32LE(24);
        const numChannels = buffer.readUInt16LE(22);
        const bitsPerSample = buffer.readUInt16LE(34);
        const dataOffset = 44; // Standard WAV header size
        const dataSize = buffer.readUInt32LE(40);
        const numFrames = dataSize / (numChannels * (bitsPerSample / 8));

        return {
            nframes: numFrames,
            framerate: sampleRate,
            duration: numFrames / sampleRate,
            nchannels: numChannels,
            sampwidth: bitsPerSample / 8,
            dataOffset
        };
    } catch {
        return null;
    }
}

/**
 * Sleep for the duration of an audio chunk
 * @param chunk Audio chunk
 * @param duration Duration in seconds
 */
export function sleepAudioLength(chunk: Uint8Array, duration: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, duration * 1000));
}

/**
 * Iterator for audio chunks from a file
 */
export class AudioChunkFileIterator implements AsyncIterator<AudioChunk> {
    private fileHandle: fs.promises.FileHandle | null = null;
    private fileParameters: WavFileParameters | null = null;
    private firstBuffer = true;
    private closed = false;
    private _delayCallback?: (chunk: Uint8Array, duration: number) => Promise<void>;

    constructor(
        private readonly filePath: string,
        private readonly chunkFrames: number,
        delayCallback?: (chunk: Uint8Array, duration: number) => Promise<void>
    ) {
        this._delayCallback = delayCallback;
    }

    async init(): Promise<void> {
        this.fileParameters = getWavFileParameters(this.filePath);
        this.fileHandle = await fs.promises.open(this.filePath, 'r');
        
        if (this._delayCallback && !this.fileParameters) {
            console.warn('delay_callback not supported for encoding other than LINEAR_PCM');
            this._delayCallback = undefined;
        }
    }

    async next(): Promise<IteratorResult<AudioChunk>> {
        if (!this.fileHandle || this.closed) {
            return { done: true, value: undefined };
        }

        if (!this.fileParameters) {
            const chunk = Buffer.alloc(this.chunkFrames);
            const { bytesRead } = await this.fileHandle.read(chunk, 0, this.chunkFrames);
            if (bytesRead === 0) {
                await this.close();
                return { done: true, value: undefined };
            }
            return { done: false, value: { audioContent: chunk.slice(0, bytesRead) } };
        }

        const bytesToRead = this.chunkFrames * this.fileParameters.sampwidth * this.fileParameters.nchannels;
        const chunk = Buffer.alloc(bytesToRead);
        const { bytesRead } = await this.fileHandle.read(chunk, 0, bytesToRead);

        if (bytesRead === 0) {
            await this.close();
            return { done: true, value: undefined };
        }

        if (this._delayCallback) {
            const offset = this.firstBuffer ? this.fileParameters.dataOffset : 0;
            await this._delayCallback(
                chunk.slice(offset),
                (bytesRead - offset) / this.fileParameters.sampwidth / this.fileParameters.framerate
            );
            this.firstBuffer = false;
        }

        return {
            done: false,
            value: { audioContent: chunk.slice(0, bytesRead) }
        };
    }

    async close(): Promise<void> {
        if (this.fileHandle) {
            await this.fileHandle.close();
            this.fileHandle = null;
        }
        this.closed = true;
    }

    [Symbol.asyncIterator](): AsyncIterator<AudioChunk> {
        return this;
    }
}

/**
 * ASR Service for speech recognition
 */
export class ASRService extends BaseClient {
    private readonly client: ASRServiceClient;

    constructor(config: { serverUrl: string; auth?: any }) {
        super(config);
        
        const { RivaSpeechRecognitionClient } = getProtoClient('riva_asr');
        this.client = new RivaSpeechRecognitionClient(
            config.serverUrl,
            config.auth?.credentials || grpc.credentials.createInsecure()
        );
    }

    private isContentSource(source: AudioSource): source is AudioContentSource {
        return 'content' in source;
    }

    private isAsyncIterable(source: AudioSource): source is AsyncIterable<AudioChunk> {
        return Symbol.asyncIterator in source;
    }

    private isIterable(source: AudioSource): source is Iterable<AudioChunk> {
        return Symbol.iterator in source;
    }

    /**
     * Add word boosting to config
     */
    public addWordBoosting(
        config: RecognitionConfig | StreamingRecognitionConfig,
        words: string[],
        score: number
    ): void {
        const innerConfig = 'config' in config ? config.config : config;
        if (words && words.length > 0) {
            const context: SpeechContext = {
                phrases: words,
                boost: score
            };
            innerConfig.speechContexts = innerConfig.speechContexts || [];
            innerConfig.speechContexts.push(context);
        }
    }

    /**
     * Add speaker diarization to config
     */
    public addSpeakerDiarization(
        config: RecognitionConfig,
        enable: boolean,
        maxSpeakers: number
    ): void {
        config.enableSpeakerDiarization = enable;
        if (enable) {
            config.diarizationConfig = {
                enableSpeakerDiarization: true,
                maxSpeakerCount: maxSpeakers
            };
        }
    }

    /**
     * Add endpoint parameters to config
     */
    public addEndpointParameters(
        config: RecognitionConfig | StreamingRecognitionConfig,
        endpointConfig: EndpointingConfig
    ): void {
        const innerConfig = 'config' in config ? config.config : config;
        innerConfig.endpointingConfig = endpointConfig;
    }

    /**
     * Add audio file specs to config
     */
    public addAudioFileSpecs(
        config: RecognitionConfig | StreamingRecognitionConfig,
        filePath: string
    ): void {
        const innerConfig = 'config' in config ? config.config : config;
        const params = getWavFileParameters(filePath);
        if (params) {
            innerConfig.encoding = AudioEncoding.LINEAR_PCM;
            innerConfig.sampleRateHertz = params.framerate;
            innerConfig.audioChannelCount = params.nchannels;
        }
    }

    /**
     * Add custom configuration to config
     */
    public addCustomConfiguration(
        config: RecognitionConfig | StreamingRecognitionConfig,
        customConfig: string
    ): void {
        const innerConfig = 'config' in config ? config.config : config;
        try {
            const customConfigObj = JSON.parse(customConfig);
            innerConfig.customConfiguration = customConfigObj;
        } catch (error) {
            console.warn('Failed to parse custom configuration:', error);
        }
    }

    /**
     * Perform streaming recognition
     */
    public async *streamingRecognize(
        audioSource: AudioSource,
        config: StreamingRecognitionConfig
    ): AsyncGenerator<StreamingRecognizeResponse> {
        const metadata = this.auth?.getCallMetadata();
        const stream = this.client.streamingRecognize(metadata);

        // Send config
        stream.write({ streamingConfig: config });

        // Send audio chunks
        if (this.isContentSource(audioSource)) {
            stream.write({ audioContent: audioSource.content });
        } else if (this.isAsyncIterable(audioSource)) {
            for await (const chunk of audioSource) {
                stream.write({ audioContent: chunk.audioContent });
            }
        } else if (this.isIterable(audioSource)) {
            for (const chunk of audioSource) {
                stream.write({ audioContent: chunk.audioContent });
            }
        }

        stream.end();

        try {
            for await (const response of stream) {
                yield response;
            }
        } catch (err) {
            const error = err as Error;
            throw handleGrpcError(error);
        }
    }

    /**
     * Perform offline recognition
     */
    public async recognize(audio: Uint8Array, config: RecognitionConfig): Promise<RecognizeResponse> {
        try {
            return await this.client.recognize({ config, audio: { content: audio } });
        } catch (err) {
            const error = err as Error;
            throw handleGrpcError(error);
        }
    }

    /**
     * List available ASR models
     */
    public async listModels(): Promise<Array<{
        name: string;
        languages: string[];
        sampleRate: number;
        streaming: boolean;
    }>> {
        try {
            const response = await this.client.listModels({});
            return response.models.map(model => ({
                name: model.name,
                languages: model.languages,
                sampleRate: model.sample_rate,
                streaming: model.streaming_supported
            }));
        } catch (err) {
            const error = err as Error;
            throw handleGrpcError(error);
        }
    }
}
