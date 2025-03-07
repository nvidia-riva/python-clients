import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SpeechSynthesisService } from '../../src/client/tts';
import { AudioEncoding } from '../../src/client/asr/types';
import { RivaError } from '../../src/client/errors';
import { createMockStream } from './helpers';
import { createGrpcMock } from './helpers/grpc';
import * as fs from 'fs';
import { WaveFile } from 'wavefile';
import type { 
    SynthesizeSpeechRequest,
    SynthesizeSpeechResponse,
    RivaSynthesisConfigRequest,
    RivaSynthesisConfigResponse,
    RivaSpeechSynthesisStub
} from '../../src/client/tts/types';
import type { ServiceError } from '@grpc/grpc-js';
import { Metadata, status } from '@grpc/grpc-js';
import type { ClientReadableStream } from '@grpc/grpc-js';
import { EventEmitter } from 'events';

// Create mock client before setting up mocks
const mockClient = createGrpcMock<RivaSpeechSynthesisStub>(['GetRivaSynthesisConfig', 'Synthesize', 'SynthesizeOnline']);

// Mock dependencies
vi.mock('fs', () => ({
    readFileSync: vi.fn()
}));

vi.mock('wavefile', () => ({
    WaveFile: vi.fn().mockImplementation(() => ({
        getSamples: vi.fn(),
        fmt: { sampleRate: 44100 }
    }))
}));

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
        RivaSpeechSynthesisStub: function() {
            return mockClient;
        }
    })
}));

describe('SpeechSynthesisService', () => {
    let service: SpeechSynthesisService;
    const mockConfig = {
        serverUrl: 'localhost:50051',
        auth: {
            ssl: false,
            credentials: undefined
        }
    };

    beforeEach(() => {
        vi.clearAllMocks();
        service = new SpeechSynthesisService(mockConfig);
    });

    describe('getRivaSynthesisConfig', () => {
        it('should get synthesis config successfully', async () => {
            const mockResponse: RivaSynthesisConfigResponse = {
                modelConfig: [{
                    parameters: {
                        languageCode: 'en-US',
                        voiceName: 'test-voice',
                        subvoices: 'voice1,voice2'
                    }
                }]
            };

            mockClient.GetRivaSynthesisConfig.mockResolvedValue(mockResponse);

            const result = await service.getRivaSynthesisConfig();
            expect(result).toEqual(mockResponse);
            expect(mockClient.GetRivaSynthesisConfig).toHaveBeenCalledWith({}, expect.any(Metadata));
        });

        it('should handle gRPC errors properly', async () => {
            const mockGrpcError = new Error('UNAVAILABLE: Server is currently unavailable') as ServiceError;
            mockGrpcError.code = status.UNAVAILABLE;
            mockGrpcError.details = 'Server is down for maintenance';
            mockGrpcError.metadata = new Metadata();

            mockClient.GetRivaSynthesisConfig.mockRejectedValue(mockGrpcError);

            await expect(service.getRivaSynthesisConfig()).rejects.toThrow(Error);
            await expect(service.getRivaSynthesisConfig()).rejects.toThrow('UNAVAILABLE: Server is currently unavailable');
        });
    });

    describe('synthesize', () => {
        const defaultRequest: SynthesizeSpeechRequest = {
            text: 'test text',
            languageCode: 'en-US',
            sampleRateHz: 44100,
            encoding: AudioEncoding.LINEAR_PCM
        };

        const defaultResponse: SynthesizeSpeechResponse = {
            audio: new Uint8Array(Buffer.from('test audio')),
            audioConfig: {
                encoding: AudioEncoding.LINEAR_PCM,
                sampleRateHz: 44100
            }
        };

        it('should synthesize with default parameters', async () => {
            mockClient.Synthesize.mockResolvedValue(defaultResponse);

            const result = await service.synthesize('test text');
            expect(result).toEqual(defaultResponse);
            expect(mockClient.Synthesize).toHaveBeenCalledWith(defaultRequest, expect.any(Metadata));
        });

        it('should synthesize with custom voice', async () => {
            const voiceName = 'English-US-Female-1';
            mockClient.Synthesize.mockResolvedValue(defaultResponse);

            await service.synthesize('test text', voiceName);
            expect(mockClient.Synthesize).toHaveBeenCalledWith({
                ...defaultRequest,
                voiceName
            }, expect.any(Metadata));
        });

        it('should handle zero-shot synthesis with audio prompt', async () => {
            const audioPromptFile = 'test.wav';
            const mockSamples = new Float64Array([1, 2, 3]);
            const mockWaveFile = {
                getSamples: vi.fn().mockReturnValue(mockSamples),
                fmt: { sampleRate: 44100 }
            };
            vi.mocked(WaveFile).mockImplementation(() => mockWaveFile as any);
            vi.mocked(fs.readFileSync).mockReturnValue(Buffer.from('test'));

            mockClient.Synthesize.mockResolvedValue(defaultResponse);

            await service.synthesize('test text', undefined, 'en-US', AudioEncoding.LINEAR_PCM, 44100, audioPromptFile);

            expect(mockClient.Synthesize).toHaveBeenCalledWith({
                ...defaultRequest,
                zeroShotData: {
                    audioPrompt: expect.any(Buffer),
                    encoding: AudioEncoding.LINEAR_PCM,
                    sampleRateHz: 44100,
                    quality: 20
                }
            }, expect.any(Metadata));
        });

        it('should handle invalid WAV file errors', async () => {
            const audioPromptFile = 'test.wav';
            vi.mocked(WaveFile).mockImplementation(() => ({
                getSamples: vi.fn().mockReturnValue(null),
                fmt: { sampleRate: 44100 }
            }) as any);

            await expect(
                service.synthesize('test text', undefined, 'en-US', AudioEncoding.LINEAR_PCM, 44100, audioPromptFile)
            ).rejects.toThrow('Invalid WAV file: no samples found');
        });

        it('should handle WAV file without sample rate', async () => {
            const audioPromptFile = 'test.wav';
            vi.mocked(WaveFile).mockImplementation(() => ({
                getSamples: vi.fn().mockReturnValue(new Float64Array([1, 2, 3])),
                fmt: {}
            }) as any);

            await expect(
                service.synthesize('test text', undefined, 'en-US', AudioEncoding.LINEAR_PCM, 44100, audioPromptFile)
            ).rejects.toThrow('Invalid WAV file: no sample rate found');
        });

        it('should add custom dictionary to request', async () => {
            const customDictionary = {
                'word1': 'phoneme1',
                'word2': 'phoneme2'
            };
            mockClient.Synthesize.mockResolvedValue(defaultResponse);

            await service.synthesize('test text', undefined, 'en-US', AudioEncoding.LINEAR_PCM, 44100, undefined, AudioEncoding.LINEAR_PCM, 20, false, customDictionary);

            expect(mockClient.Synthesize).toHaveBeenCalledWith({
                ...defaultRequest,
                customDictionary: 'word1  phoneme1,word2  phoneme2'
            }, expect.any(Metadata));
        });
    });

    describe('synthesizeOnline', () => {
        const defaultRequest: SynthesizeSpeechRequest = {
            text: 'test text',
            languageCode: 'en-US',
            sampleRateHz: 44100,
            encoding: AudioEncoding.LINEAR_PCM
        };

        function mockChunkResponse(data: string): SynthesizeSpeechResponse {
            return {
                audio: new Uint8Array(Buffer.from(data)),
                audioConfig: {
                    encoding: AudioEncoding.LINEAR_PCM,
                    sampleRateHz: 44100
                }
            };
        }

        it('should stream synthesis results', async () => {
            // Create a mock stream that implements the ClientReadableStream interface
            const mockOn = vi.fn((event: string, callback: (...args: any[]) => void) => {
                if (event === 'data') {
                    setTimeout(() => {
                        callback(mockChunkResponse('chunk1'));
                        callback(mockChunkResponse('chunk2'));
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
                    yield mockChunkResponse('chunk1');
                    yield mockChunkResponse('chunk2');
                }
            } as any as ClientReadableStream<SynthesizeSpeechResponse>;

            mockClient.SynthesizeOnline.mockReturnValue(mockStream);

            const chunks: SynthesizeSpeechResponse[] = [];
            for await (const chunk of service.synthesizeOnline('test text')) {
                chunks.push(chunk);
            }

            expect(chunks).toHaveLength(2);
            expect(chunks[0]).toEqual(mockChunkResponse('chunk1'));
            expect(chunks[1]).toEqual(mockChunkResponse('chunk2'));
            expect(mockClient.SynthesizeOnline).toHaveBeenCalledWith(defaultRequest, expect.any(Metadata));
        });

        it('should handle stream errors', async () => {
            // Create a mock stream that implements the ClientReadableStream interface
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
            } as any as ClientReadableStream<SynthesizeSpeechResponse>;

            mockClient.SynthesizeOnline.mockReturnValue(mockStream);

            await expect(async () => {
                for await (const _ of service.synthesizeOnline('test text')) {
                    // consume stream
                }
            }).rejects.toThrow('Stream error');
        });
    });
});
