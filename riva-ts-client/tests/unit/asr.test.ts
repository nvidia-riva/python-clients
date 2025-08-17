import { vi, describe, it, expect, beforeEach, type MockInstance } from 'vitest';
import { ASRService } from '../../src/client/asr';
import { createGrpcMock, createMetadataMock } from './helpers/grpc';
import { createAudioMocks } from './helpers/audio';
import { createMockStream } from './helpers/stream';
import { AudioEncoding, type ASRServiceClient, type RecognitionConfig, type StreamingRecognitionConfig, type StreamingRecognizeResponse } from '../../src/client/asr/types';
import * as grpc from '@grpc/grpc-js';

// Create mock client before setting up mocks
const mockClient = createGrpcMock<ASRServiceClient>(['recognize', 'streamingRecognize', 'listModels']);

vi.mock('@grpc/grpc-js', async () => {
    const actual = await vi.importActual('@grpc/grpc-js') as typeof grpc;
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
        RivaSpeechRecognitionClient: function() {
            return mockClient;
        }
    })
}));

describe('ASRService', () => {
    let service: ASRService;
    let audioMocks;
    let mockMetadata;

    beforeEach(() => {
        audioMocks = createAudioMocks();
        mockMetadata = createMetadataMock();

        // Update the mock metadata implementation after creating mockMetadata
        (grpc.Metadata as unknown as MockInstance).mockImplementation(() => mockMetadata);

        service = new ASRService({
            serverUrl: 'test:50051',
            auth: {
                credentials: grpc.credentials.createInsecure()
            }
        });
    });

    describe('recognize', () => {
        it('should recognize audio with correct parameters', async () => {
            const mockResponse = {
                results: [{
                    alternatives: [{
                        transcript: 'test transcript',
                        confidence: 0.9,
                        words: [{
                            word: 'test',
                            startTime: 0,
                            endTime: 1,
                            confidence: 0.9,
                            speakerLabel: 'speaker_0'
                        }]
                    }]
                }]
            };

            mockClient.recognize.mockResolvedValue(mockResponse);

            const config: RecognitionConfig = {
                encoding: AudioEncoding.LINEAR_PCM,
                sampleRateHertz: 16000,
                languageCode: 'en-US',
                maxAlternatives: 1,
                enableAutomaticPunctuation: true
            };

            const result = await service.recognize(new Uint8Array(100), config);

            expect(mockClient.recognize).toHaveBeenCalledWith({
                config,
                audio: {
                    content: expect.any(Uint8Array)
                }
            });

            expect(result).toEqual(mockResponse);
        });

        it('should handle gRPC errors properly', async () => {
            const error = new Error('Network error');
            mockClient.recognize.mockRejectedValue(error);

            const config: RecognitionConfig = {
                encoding: AudioEncoding.LINEAR_PCM,
                sampleRateHertz: 16000,
                languageCode: 'en-US',
                maxAlternatives: 1,
                enableAutomaticPunctuation: true
            };

            await expect(service.recognize(new Uint8Array(100), config)).rejects.toThrow('Network error');
        });
    });

    describe('streamingRecognize', () => {
        it('should handle streaming recognition', async () => {
            const mockStream = createMockStream({
                onData: () => ({
                    results: [{
                        alternatives: [{
                            transcript: 'test transcript',
                            confidence: 0.9,
                            words: []
                        }]
                    }]
                })
            });
            mockClient.streamingRecognize.mockReturnValue(mockStream);

            const config: StreamingRecognitionConfig = {
                config: {
                    encoding: AudioEncoding.LINEAR_PCM,
                    sampleRateHertz: 16000,
                    languageCode: 'en-US',
                    maxAlternatives: 1,
                    enableAutomaticPunctuation: true
                }
            };

            const audioSource = {
                content: new Uint8Array(100)
            };

            const stream = service.streamingRecognize(audioSource, config);

            // Collect all responses
            const responses: StreamingRecognizeResponse[] = [];
            for await (const response of stream) {
                responses.push(response);
            }

            expect(mockClient.streamingRecognize).toHaveBeenCalled();
            expect(mockStream.write).toHaveBeenCalledWith({ streamingConfig: config });
            expect(mockStream.write).toHaveBeenCalledWith({ audioContent: audioSource.content });
            expect(mockStream.end).toHaveBeenCalled();
        });

        it('should handle streaming errors', async () => {
            const mockStream = createMockStream({
                onError: (error) => {
                    throw error;
                }
            });

            mockClient.streamingRecognize.mockReturnValue(mockStream);

            const config: StreamingRecognitionConfig = {
                config: {
                    encoding: AudioEncoding.LINEAR_PCM,
                    sampleRateHertz: 16000,
                    languageCode: 'en-US',
                    maxAlternatives: 1,
                    enableAutomaticPunctuation: true
                }
            };

            const audioSource = {
                content: new Uint8Array(100)
            };

            const stream = service.streamingRecognize(audioSource, config);

            await expect(async () => {
                for await (const _ of stream) {
                    // Just iterate to trigger error
                }
            }).rejects.toThrow('Stream error');
        });
    });

    describe('listModels', () => {
        it('should list available models', async () => {
            const mockResponse = {
                models: [{
                    name: 'test-model',
                    languages: ['en-US'],
                    sample_rate: 16000,
                    streaming_supported: true
                }]
            };

            const expectedResult = [{
                name: 'test-model',
                languages: ['en-US'],
                sampleRate: 16000,
                streaming: true
            }];

            mockClient.listModels.mockResolvedValue(mockResponse);

            const result = await service.listModels();

            expect(mockClient.listModels).toHaveBeenCalled();
            expect(result).toEqual(expectedResult);
        });

        it('should handle list models error', async () => {
            const error = new Error('Failed to list models');
            mockClient.listModels.mockRejectedValue(error);

            await expect(service.listModels()).rejects.toThrow('Failed to list models');
        });
    });
});
