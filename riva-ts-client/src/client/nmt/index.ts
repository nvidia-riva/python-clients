import * as grpc from '@grpc/grpc-js';
import { BaseClient } from '../base';
import { handleGrpcError } from '../errors';
import { getProtoClient } from '../utils/proto';
import {
    StreamingS2SRequest,
    StreamingS2SResponse,
    StreamingS2TRequest,
    StreamingS2TResponse,
    TranslateRequest,
    TranslateResponse,
    AvailableLanguageRequest,
    AvailableLanguageResponse,
    NMTServiceClient,
    StreamingS2SConfig,
    StreamingS2TConfig,
    ClientConfig
} from './types';

/**
 * Generator for streaming speech-to-speech translation requests
 */
function* streaming_s2s_request_generator(
    audioChunks: Iterable<Uint8Array>,
    streamingConfig: StreamingS2SConfig
): Generator<StreamingS2SRequest, void, unknown> {
    yield { config: streamingConfig };
    for (const chunk of audioChunks) {
        yield { audioContent: chunk };
    }
}

/**
 * Generator for streaming speech-to-text translation requests
 */
function* streaming_s2t_request_generator(
    audioChunks: Iterable<Uint8Array>,
    streamingConfig: StreamingS2TConfig
): Generator<StreamingS2TRequest, void, unknown> {
    yield { config: streamingConfig };
    for (const chunk of audioChunks) {
        yield { audioContent: chunk };
    }
}

/**
 * Neural Machine Translation Service for text and speech translation
 */
export class NeuralMachineTranslationService extends BaseClient {
    private readonly stub: NMTServiceClient;

    constructor(config: ClientConfig) {
        super(config);
        const { RivaSpeechTranslationClient } = getProtoClient('riva_services');
        this.stub = new RivaSpeechTranslationClient(
            config.serverUrl,
            config.auth?.credentials || grpc.credentials.createInsecure()
        ) as NMTServiceClient;
    }

    /**
     * Generates speech to speech translation responses for fragments of speech audio
     */
    async *streaming_s2s_response_generator(
        audioChunks: Iterable<Uint8Array>,
        streamingConfig: StreamingS2SConfig
    ): AsyncGenerator<StreamingS2SResponse, void, unknown> {
        try {
            const generator = streaming_s2s_request_generator(audioChunks, streamingConfig);
            const stream = this.stub.streamingTranslateSpeechToSpeech(generator, this.getCallMetadata());
            
            for await (const response of stream) {
                yield response;
            }
        } catch (err) {
            const error = err as Error;
            throw handleGrpcError(error);
        }
    }

    /**
     * Generates speech to text translation responses for fragments of speech audio
     */
    async *streaming_s2t_response_generator(
        audioChunks: Iterable<Uint8Array>,
        streamingConfig: StreamingS2TConfig
    ): AsyncGenerator<StreamingS2TResponse, void, unknown> {
        try {
            const generator = streaming_s2t_request_generator(audioChunks, streamingConfig);
            const stream = this.stub.streamingTranslateSpeechToText(generator, this.getCallMetadata());
            
            for await (const response of stream) {
                yield response;
            }
        } catch (err) {
            const error = err as Error;
            throw handleGrpcError(error);
        }
    }

    /**
     * Translates text from one language to another
     */
    async translate(request: TranslateRequest): Promise<TranslateResponse> {
        try {
            return await this.stub.translateText(request, this.getCallMetadata());
        } catch (err) {
            const error = err as Error;
            throw handleGrpcError(error);
        }
    }

    /**
     * Gets supported language pairs for a model
     */
    async get_supported_language_pairs(model: string): Promise<AvailableLanguageResponse> {
        try {
            return await this.stub.listSupportedLanguagePairs({ model }, this.getCallMetadata());
        } catch (err) {
            const error = err as Error;
            throw handleGrpcError(error);
        }
    }
}

export type {
    TranslateRequest,
    TranslateResponse,
    StreamingS2SConfig,
    StreamingS2TConfig,
    AvailableLanguageRequest,
    AvailableLanguageResponse
};
