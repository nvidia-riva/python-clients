import { vi, type Mock } from 'vitest';
import { Auth } from '../../src/client/auth';
import * as grpc from '@grpc/grpc-js';
import { ClientDuplexStream, Metadata, StatusObject } from '@grpc/grpc-js';
import { RivaConfig } from '../../src/client/types';

type MockAuthConfig = {
    serverUrl: string;
    auth: {
        ssl: boolean;
        sslCert?: string;
        metadata?: Array<[string, string]>;
    };
};

/**
 * Creates a mock Auth instance for testing
 * @returns Tuple of [mockConfig, mockMetadata]
 */
export function createAuthMock(): [MockAuthConfig, grpc.Metadata] {
    const mockMetadata = new grpc.Metadata();
    mockMetadata.set('test-key', 'test-value');

    const mockConfig: MockAuthConfig = {
        serverUrl: 'localhost:50051',
        auth: {
            ssl: false,
            metadata: [['test-key', 'test-value']]
        }
    };

    return [mockConfig, mockMetadata];
}

type GrpcEventType = 'data' | 'end' | 'error' | 'status' | 'metadata' | 'close';

/**
 * Creates a mock gRPC stream for testing
 */
export function createMockStream<TReq = any, TRes = any>(): ClientDuplexStream<TReq, TRes> {
    const eventHandlers: Map<string, Function[]> = new Map();
    
    const mockStream = {
        on: vi.fn().mockImplementation((event: GrpcEventType, handler: Function) => {
            if (!eventHandlers.has(event)) {
                eventHandlers.set(event, []);
            }
            eventHandlers.get(event)!.push(handler);
            return mockStream;
        }),

        write: vi.fn().mockImplementation((data: TReq) => {
            const handlers = eventHandlers.get('data') || [];
            handlers.forEach(handler => handler(data));
            return true;
        }),

        end: vi.fn().mockImplementation(() => {
            const handlers = eventHandlers.get('end') || [];
            handlers.forEach(handler => handler());
        }),

        destroy: vi.fn().mockImplementation((error?: Error) => {
            if (error) {
                const handlers = eventHandlers.get('error') || [];
                handlers.forEach(handler => handler(error));
            }
            const closeHandlers = eventHandlers.get('close') || [];
            closeHandlers.forEach(handler => handler());
        }),

        emit: vi.fn().mockImplementation((event: string, ...args: any[]) => {
            const handlers = eventHandlers.get(event) || [];
            handlers.forEach(handler => handler(...args));
            return true;
        }),

        removeListener: vi.fn(),
        removeAllListeners: vi.fn(),
        pause: vi.fn(),
        resume: vi.fn(),
        isPaused: vi.fn().mockReturnValue(false),
        pipe: vi.fn(),
        unpipe: vi.fn(),
        unshift: vi.fn(),
        wrap: vi.fn(),
        [Symbol.asyncIterator]: vi.fn().mockImplementation(function* () {
            const dataHandlers = eventHandlers.get('data') || [];
            for (const handler of dataHandlers) {
                yield handler;
            }
        })
    } as unknown as ClientDuplexStream<TReq, TRes>;

    return mockStream;
}

export class MockAudioContext {
    createMediaStreamSource: Mock;
    createScriptProcessor: Mock;
    decodeAudioData: Mock;
    createBufferSource: Mock;
    destination: {};
    close: Mock;
    sampleRate: number;

    constructor() {
        this.createMediaStreamSource = vi.fn();
        this.createScriptProcessor = vi.fn();
        this.decodeAudioData = vi.fn();
        this.createBufferSource = vi.fn();
        this.destination = {};
        this.close = vi.fn();
        this.sampleRate = 44100;
    }
}

/**
 * Creates a mock AudioContext for testing
 */
export function createMockAudioContext(): MockAudioContext {
    return new MockAudioContext();
}

export class MockMediaDevices {
    getUserMedia: Mock;
    enumerateDevices: Mock;

    constructor() {
        this.getUserMedia = vi.fn();
        this.enumerateDevices = vi.fn();
    }
}

/**
 * Creates a mock MediaDevices for testing
 */
export function createMockMediaDevices(): MockMediaDevices {
    return new MockMediaDevices();
}

export class MockMediaStream {
    getTracks: Mock;

    constructor() {
        this.getTracks = vi.fn().mockReturnValue([]);
    }
}

/**
 * Creates a mock MediaStream for testing
 */
export function createMockMediaStream(): MockMediaStream {
    return new MockMediaStream();
}

export class MockGrpcClient {
    recognize: Mock;
    streamingRecognize: Mock;
    synthesize: Mock;
    streamingSynthesize: Mock;
    classify: Mock;
    tokenClassify: Mock;
    analyzeEntities: Mock;
    analyzeIntent: Mock;
    transformText: Mock;
    naturalQuery: Mock;
    translateText: Mock;
    streamingTranslateSpeechToSpeech: Mock;
    streamingTranslateSpeechToText: Mock;
    listSupportedLanguagePairs: Mock;

    constructor() {
        this.recognize = vi.fn();
        this.streamingRecognize = vi.fn();
        this.synthesize = vi.fn();
        this.streamingSynthesize = vi.fn();
        this.classify = vi.fn();
        this.tokenClassify = vi.fn();
        this.analyzeEntities = vi.fn();
        this.analyzeIntent = vi.fn();
        this.transformText = vi.fn();
        this.naturalQuery = vi.fn();
        this.translateText = vi.fn();
        this.streamingTranslateSpeechToSpeech = vi.fn();
        this.streamingTranslateSpeechToText = vi.fn();
        this.listSupportedLanguagePairs = vi.fn();
    }
}

/**
 * Creates a mock gRPC client for testing
 */
export function createMockGrpcClient(): MockGrpcClient {
    return new MockGrpcClient();
}

export class MockBuffer {
    length: number;
    slice: Mock;
    toString: Mock;
    readInt16LE: Mock;

    constructor(data: number[] = []) {
        this.length = data.length;
        this.slice = vi.fn().mockReturnThis();
        this.toString = vi.fn().mockReturnValue('');
        this.readInt16LE = vi.fn().mockReturnValue(0);
    }
}

/**
 * Creates a mock Buffer for testing
 */
export function createMockBuffer(data: number[] = []): MockBuffer {
    return new MockBuffer(data);
}
