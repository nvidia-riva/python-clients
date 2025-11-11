import * as grpc from '@grpc/grpc-js';
import { AudioEncoding } from '../asr/types';
import { RivaConfig } from '../types';

/**
 * Configuration options for the client.
 */
export interface ClientConfig extends RivaConfig {
    /**
     * The URL of the server to connect to.
     */
    serverUrl: string;

    /**
     * Optional function to create a gRPC client for testing
     */
    createClient?: (url: string, credentials: grpc.ChannelCredentials) => grpc.Client;
    // Add other configuration options as needed
}

/**
 * Configuration options for speech recognition.
 */
export interface RecognitionConfig {
    /**
     * Whether to enable automatic punctuation.
     */
    enableAutomaticPunctuation?: boolean;
    /**
     * The audio encoding of the input audio.
     */
    audioEncoding?: AudioEncoding;
    /**
     * The sample rate of the input audio in Hz.
     */
    sampleRateHertz?: number;
    /**
     * The language code of the input audio.
     */
    languageCode?: string;
}

/**
 * Configuration options for streaming speech recognition.
 */
export interface StreamingRecognitionConfig {
    /**
     * The recognition configuration.
     */
    config: RecognitionConfig;
    /**
     * Whether to return interim results.
     */
    interimResults: boolean;
}

/**
 * Configuration options for text translation.
 */
export interface TranslationConfig {
    /**
     * The source language code.
     */
    sourceLanguageCode: string;
    /**
     * The target language code.
     */
    targetLanguageCode: string;
    /**
     * The model to use for translation.
     */
    model?: string;
    /**
     * The phrases to not translate.
     */
    doNotTranslatePhrases?: string[];
}

/**
 * Configuration options for speech synthesis.
 */
export interface SynthesizeSpeechConfig {
    /**
     * The sample rate of the output audio in Hz.
     */
    sampleRateHz: number;
    /**
     * The voice to use for synthesis.
     */
    voiceName?: string;
    /**
     * The language code of the output audio.
     */
    languageCode?: string;
}

/**
 * Configuration options for streaming speech-to-speech translation.
 */
export interface StreamingS2SConfig {
    /**
     * The ASR configuration.
     */
    asrConfig: StreamingRecognitionConfig;
    /**
     * The translation configuration.
     */
    translationConfig: TranslationConfig;
    /**
     * The TTS configuration.
     */
    ttsConfig: SynthesizeSpeechConfig;
}

/**
 * Configuration options for streaming speech-to-text translation.
 */
export interface StreamingS2TConfig {
    /**
     * The ASR configuration.
     */
    asrConfig: StreamingRecognitionConfig;
    /**
     * The translation configuration.
     */
    translationConfig: TranslationConfig;
}

/**
 * Request message for streaming speech-to-speech translation.
 */
export interface StreamingS2SRequest {
    /**
     * The configuration for the request.
     */
    config?: StreamingS2SConfig;
    /**
     * The audio content for the request.
     */
    audioContent?: Uint8Array;
}

/**
 * Request message for streaming speech-to-text translation.
 */
export interface StreamingS2TRequest {
    /**
     * The configuration for the request.
     */
    config?: StreamingS2TConfig;
    /**
     * The audio content for the request.
     */
    audioContent?: Uint8Array;
}

/**
 * Response message for streaming speech-to-speech translation.
 */
export interface StreamingS2SResponse {
    /**
     * The result of the translation.
     */
    result: {
        /**
         * The transcript of the input audio.
         */
        transcript: string;
        /**
         * The translation of the input audio.
         */
        translation: string;
        /**
         * The synthesized audio content.
         */
        audioContent: Uint8Array;
        /**
         * Whether the result is partial.
         */
        isPartial: boolean;
    };
}

/**
 * Response message for streaming speech-to-text translation.
 */
export interface StreamingS2TResponse {
    /**
     * The result of the translation.
     */
    result: {
        /**
         * The transcript of the input audio.
         */
        transcript: string;
        /**
         * The translation of the input audio.
         */
        translation: string;
        /**
         * Whether the result is partial.
         */
        isPartial: boolean;
    };
}

/**
 * Request message for text translation.
 */
export interface TranslateRequest {
    /**
     * The text to translate.
     */
    text: string;
    /**
     * The source language.
     */
    sourceLanguage: string;
    /**
     * The target language.
     */
    targetLanguage: string;
    /**
     * The model to use for translation.
     */
    model?: string;
    /**
     * The phrases to not translate.
     */
    doNotTranslatePhrases?: string[];
}

/**
 * Response message for text translation.
 */
export interface TranslateResponse {
    /**
     * The translations.
     */
    translations: Array<{
        /**
         * The translated text.
         */
        text: string;
        /**
         * The confidence score of the translation.
         */
        score: number;
    }>;
    /**
     * The translated text.
     */
    text: string;
    /**
     * The confidence score of the translation.
     */
    score: number;
}

/**
 * A language pair.
 */
export interface LanguagePair {
    /**
     * The source language code.
     */
    sourceLanguageCode: string;
    /**
     * The target language code.
     */
    targetLanguageCode: string;
}

/**
 * Request message for listing supported language pairs.
 */
export interface AvailableLanguageRequest {
    /**
     * The model to use for listing language pairs.
     */
    model: string;
}

/**
 * Response message for listing supported language pairs.
 */
export interface AvailableLanguageResponse {
    /**
     * The supported language pairs.
     */
    supportedLanguagePairs: LanguagePair[];
}

/**
 * The NMT service client.
 */
export interface NMTServiceClient {
    /**
     * Translates text.
     */
    translateText(
        request: TranslateRequest,
        metadata?: grpc.Metadata
    ): Promise<TranslateResponse>;

    /**
     * Lists supported language pairs.
     */
    listSupportedLanguagePairs(
        request: AvailableLanguageRequest,
        metadata?: grpc.Metadata
    ): Promise<AvailableLanguageResponse>;

    /**
     * Streams speech-to-speech translation.
     */
    streamingTranslateSpeechToSpeech(
        request: Generator<StreamingS2SRequest, void, unknown> | StreamingS2SRequest,
        metadata?: grpc.Metadata
    ): grpc.ClientReadableStream<StreamingS2SResponse>;

    /**
     * Streams speech-to-text translation.
     */
    streamingTranslateSpeechToText(
        request: Generator<StreamingS2TRequest, void, unknown> | StreamingS2TRequest,
        metadata?: grpc.Metadata
    ): grpc.ClientReadableStream<StreamingS2TResponse>;
}
