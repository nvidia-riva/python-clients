import { describe, it, expect, vi, beforeEach } from 'vitest';
import { NeuralMachineTranslationService } from '../../src/client/nmt';
import { RivaError } from '../../src/client/errors';
import { createGrpcMock } from './helpers/grpc';
import type { 
    TranslateRequest,
    TranslateResponse,
    AvailableLanguageRequest,
    AvailableLanguageResponse,
    StreamingS2SRequest,
    StreamingS2SResponse,
    StreamingS2TRequest,
    StreamingS2TResponse,
    LanguagePair,
    StreamingS2SConfig,
    StreamingS2TConfig,
    StreamingRecognitionConfig,
    RecognitionConfig,
    TranslationConfig,
    SynthesizeSpeechConfig,
    NMTServiceClient
} from '../../src/client/nmt/types';
import type { ServiceError } from '@grpc/grpc-js';
import { Metadata, status } from '@grpc/grpc-js';
import type { ClientReadableStream } from '@grpc/grpc-js';

// Create mock client before setting up mocks
const mockClient = createGrpcMock<NMTServiceClient>([
    'translateText',
    'listSupportedLanguagePairs',
    'streamingTranslateSpeechToSpeech',
    'streamingTranslateSpeechToText'
]);

// Mock dependencies
vi.mock('@grpc/grpc-js', async () => {
    const actual = await vi.importActual('@grpc/grpc-js');
    return {
        ...actual,
        credentials: {
            createInsecure: vi.fn(),
            createFromMetadataGenerator: vi.fn()
        },
        Metadata: vi.fn(),
        Channel: vi.fn().mockImplementation(() => ({
            getTarget: vi.fn(),
            close: vi.fn(),
            getConnectivityState: vi.fn(),
            watchConnectivityState: vi.fn()
        }))
    };
});

vi.mock('../../src/client/utils/proto', () => ({
    getProtoClient: () => ({
        RivaSpeechTranslationClient: function() {
            return mockClient;
        }
    })
}));

describe('NeuralMachineTranslationService', () => {
    let service: NeuralMachineTranslationService;
    const mockConfig = {
        serverUrl: 'localhost:50051',
        auth: {
            ssl: false
        }
    };

    beforeEach(() => {
        vi.clearAllMocks();
        service = new NeuralMachineTranslationService(mockConfig);
    });

    describe('translate', () => {
        const mockRequest: TranslateRequest = {
            text: 'Hello world',
            sourceLanguage: 'en-US',
            targetLanguage: 'es-US'
        };

        it('should translate text successfully', async () => {
            const mockResponse: TranslateResponse = {
                translations: [{
                    text: 'Hola mundo',
                    score: 0.95
                }],
                text: 'Hola mundo',
                score: 0.95
            };

            mockClient.translateText.mockResolvedValue(mockResponse);

            const result = await service.translate(mockRequest);
            expect(result).toEqual(mockResponse);
            expect(mockClient.translateText).toHaveBeenCalledWith(mockRequest, expect.any(Metadata));
        });

        it('should handle gRPC errors', async () => {
            const mockError = new Error('UNAVAILABLE: Server is currently unavailable') as ServiceError;
            mockError.code = status.UNAVAILABLE;
            mockError.details = 'Server is down for maintenance';
            mockError.metadata = new Metadata();

            mockClient.translateText.mockRejectedValue(mockError);

            await expect(service.translate(mockRequest)).rejects.toThrow(RivaError);
            await expect(service.translate(mockRequest)).rejects.toThrow('UNAVAILABLE: Server is currently unavailable');
        });
    });

    describe('get_supported_language_pairs', () => {
        const mockModel = 'nmt-model';
        const mockRequest: AvailableLanguageRequest = { model: mockModel };

        it('should get language pairs successfully', async () => {
            const mockResponse: AvailableLanguageResponse = {
                supportedLanguagePairs: [{
                    sourceLanguageCode: 'en-US',
                    targetLanguageCode: 'es-US'
                }]
            };

            mockClient.listSupportedLanguagePairs.mockResolvedValue(mockResponse);

            const result = await service.get_supported_language_pairs(mockModel);
            expect(result).toEqual(mockResponse);
            expect(mockClient.listSupportedLanguagePairs).toHaveBeenCalledWith(mockRequest, expect.any(Metadata));
        });

        it('should handle gRPC errors', async () => {
            const mockError = new Error('UNAVAILABLE: Server is currently unavailable') as ServiceError;
            mockError.code = status.UNAVAILABLE;
            mockError.details = 'Server is down for maintenance';
            mockError.metadata = new Metadata();

            mockClient.listSupportedLanguagePairs.mockRejectedValue(mockError);

            await expect(service.get_supported_language_pairs(mockModel)).rejects.toThrow(RivaError);
            await expect(service.get_supported_language_pairs(mockModel)).rejects.toThrow('UNAVAILABLE: Server is currently unavailable');
        });
    });

    describe('streaming_s2s_response_generator', () => {
        const mockConfig: StreamingS2SConfig = {
            asrConfig: {
                config: {
                    languageCode: 'en-US',
                    audioEncoding: 1,
                    sampleRateHertz: 16000
                },
                interimResults: true
            },
            translationConfig: {
                sourceLanguageCode: 'en-US',
                targetLanguageCode: 'es-US'
            },
            ttsConfig: {
                languageCode: 'es-US',
                sampleRateHz: 16000
            }
        };

        function mockResponse(text: string, translation: string, isPartial: boolean): StreamingS2SResponse {
            return {
                result: {
                    transcript: text,
                    translation: translation,
                    audioContent: new Uint8Array(Buffer.from('mock audio')),
                    isPartial
                }
            };
        }

        it('should stream speech-to-speech translation', async () => {
            const mockOn = vi.fn((event: string, callback: (...args: any[]) => void) => {
                if (event === 'data') {
                    setTimeout(() => {
                        callback(mockResponse('Hello', 'Hola', true));
                        callback(mockResponse('Hello world', 'Hola mundo', false));
                        const endCallback = mockOn.mock.calls.find(([evt]) => evt === 'end')?.[1];
                        if (endCallback) endCallback();
                    }, 0);
                }
                return mockStream;
            });

            const mockStream = {
                on: mockOn,
                removeListener: vi.fn(),
                [Symbol.asyncIterator]: function* () {
                    yield mockResponse('Hello', 'Hola', true);
                    yield mockResponse('Hello world', 'Hola mundo', false);
                }
            } as any as ClientReadableStream<StreamingS2SResponse>;

            mockClient.streamingTranslateSpeechToSpeech.mockReturnValue(mockStream);

            const audioChunks = [new Uint8Array(Buffer.from('chunk1')), new Uint8Array(Buffer.from('chunk2'))];
            const responses: StreamingS2SResponse[] = [];

            for await (const response of service.streaming_s2s_response_generator(audioChunks, mockConfig)) {
                responses.push(response);
            }

            expect(responses).toHaveLength(2);
            expect(responses[0].result.transcript).toBe('Hello');
            expect(responses[0].result.translation).toBe('Hola');
            expect(responses[0].result.isPartial).toBe(true);
            expect(responses[1].result.transcript).toBe('Hello world');
            expect(responses[1].result.translation).toBe('Hola mundo');
            expect(responses[1].result.isPartial).toBe(false);
        });

        it('should handle stream errors', async () => {
            const mockStream = {
                on: vi.fn((event: string, callback: (...args: any[]) => void) => {
                    if (event === 'error') {
                        setTimeout(() => {
                            callback(new Error('Stream error'));
                        }, 0);
                    }
                    return mockStream;
                }),
                removeListener: vi.fn(),
                [Symbol.asyncIterator]: function* () {
                    throw new Error('Stream error');
                }
            } as any as ClientReadableStream<StreamingS2SResponse>;

            mockClient.streamingTranslateSpeechToSpeech.mockReturnValue(mockStream);

            const audioChunks = [new Uint8Array(Buffer.from('chunk1'))];
            await expect(async () => {
                for await (const _ of service.streaming_s2s_response_generator(audioChunks, mockConfig)) {
                    // consume stream
                }
            }).rejects.toThrow('Stream error');
        });
    });

    describe('streaming_s2t_response_generator', () => {
        const mockConfig: StreamingS2TConfig = {
            asrConfig: {
                config: {
                    languageCode: 'en-US',
                    audioEncoding: 1,
                    sampleRateHertz: 16000
                },
                interimResults: true
            },
            translationConfig: {
                sourceLanguageCode: 'en-US',
                targetLanguageCode: 'es-US'
            }
        };

        function mockResponse(text: string, translation: string, isPartial: boolean): StreamingS2TResponse {
            return {
                result: {
                    transcript: text,
                    translation: translation,
                    isPartial
                }
            };
        }

        it('should stream speech-to-text translation', async () => {
            const mockOn = vi.fn((event: string, callback: (...args: any[]) => void) => {
                if (event === 'data') {
                    setTimeout(() => {
                        callback(mockResponse('Hello', 'Hola', true));
                        callback(mockResponse('Hello world', 'Hola mundo', false));
                        const endCallback = mockOn.mock.calls.find(([evt]) => evt === 'end')?.[1];
                        if (endCallback) endCallback();
                    }, 0);
                }
                return mockStream;
            });

            const mockStream = {
                on: mockOn,
                removeListener: vi.fn(),
                [Symbol.asyncIterator]: function* () {
                    yield mockResponse('Hello', 'Hola', true);
                    yield mockResponse('Hello world', 'Hola mundo', false);
                }
            } as any as ClientReadableStream<StreamingS2TResponse>;

            mockClient.streamingTranslateSpeechToText.mockReturnValue(mockStream);

            const audioChunks = [new Uint8Array(Buffer.from('chunk1')), new Uint8Array(Buffer.from('chunk2'))];
            const responses: StreamingS2TResponse[] = [];

            for await (const response of service.streaming_s2t_response_generator(audioChunks, mockConfig)) {
                responses.push(response);
            }

            expect(responses).toHaveLength(2);
            expect(responses[0].result.transcript).toBe('Hello');
            expect(responses[0].result.translation).toBe('Hola');
            expect(responses[0].result.isPartial).toBe(true);
            expect(responses[1].result.transcript).toBe('Hello world');
            expect(responses[1].result.translation).toBe('Hola mundo');
            expect(responses[1].result.isPartial).toBe(false);
        });

        it('should handle stream errors', async () => {
            const mockStream = {
                on: vi.fn((event: string, callback: (...args: any[]) => void) => {
                    if (event === 'error') {
                        setTimeout(() => {
                            callback(new Error('Stream error'));
                        }, 0);
                    }
                    return mockStream;
                }),
                removeListener: vi.fn(),
                [Symbol.asyncIterator]: function* () {
                    throw new Error('Stream error');
                }
            } as any as ClientReadableStream<StreamingS2TResponse>;

            mockClient.streamingTranslateSpeechToText.mockReturnValue(mockStream);

            const audioChunks = [new Uint8Array(Buffer.from('chunk1'))];
            await expect(async () => {
                for await (const _ of service.streaming_s2t_response_generator(audioChunks, mockConfig)) {
                    // consume stream
                }
            }).rejects.toThrow('Stream error');
        });
    });
});
