import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Auth, AuthOptions } from '../../src/client/auth';
import * as grpc from '@grpc/grpc-js';
import * as fs from 'fs';
import { resolve } from 'path';

vi.mock('fs', () => ({
    readFileSync: vi.fn()
}));

vi.mock('@grpc/grpc-js', () => {
    let metadataStore = new Map<string, string[]>();

    class MetadataMock {
        constructor() {
            metadataStore = new Map<string, string[]>();
        }

        add(key: string, value: string) {
            const values = metadataStore.get(key) || [];
            values.push(value);
            metadataStore.set(key, values);
        }

        get(key: string) {
            return metadataStore.get(key) || [];
        }

        getMap() {
            const map: Record<string, string> = {};
            metadataStore.forEach((values, key) => {
                map[key] = values[0];
            });
            return map;
        }

        set(key: string, value: string) {
            metadataStore.set(key, [value]);
        }
    }

    return {
        ...vi.importActual('@grpc/grpc-js'),
        Channel: vi.fn().mockImplementation(() => ({
            getTarget: vi.fn().mockReturnValue('localhost:50051')
        })),
        credentials: {
            createInsecure: vi.fn().mockReturnValue({}),
            createSsl: vi.fn().mockReturnValue({}),
            createFromMetadataGenerator: vi.fn().mockReturnValue({}),
            combineChannelCredentials: vi.fn().mockReturnValue({})
        },
        Metadata: MetadataMock
    };
});

describe('Auth', () => {
    const testUri = 'localhost:50051';
    let auth: Auth;

    beforeEach(() => {
        vi.clearAllMocks();
    });

    describe('constructor with AuthOptions', () => {
        it('should initialize with default values', () => {
            auth = new Auth({ uri: testUri });
            expect(auth['uri']).toBe(testUri);
            expect(auth['useSsl']).toBe(false);
            expect(auth['sslCert']).toBeUndefined();
            expect(auth['metadata']).toEqual([]);
            expect(auth['channelOptions']).toEqual({});
            expect(grpc.Channel).toHaveBeenCalledWith(
                testUri,
                expect.any(Object),
                {}
            );
        });

        it('should initialize with custom values', () => {
            const sslCert = 'test-cert.pem';
            const metadata: [string, string][] = [['key', 'value']];
            const channelOptions = { 'grpc.keepalive_time_ms': 10000 };
            
            auth = new Auth({
                uri: testUri,
                useSsl: true,
                sslCert,
                metadata,
                channelOptions
            });

            expect(auth['uri']).toBe(testUri);
            expect(auth['useSsl']).toBe(true);
            expect(auth['sslCert']).toBe(sslCert);
            expect(auth['metadata']).toEqual(metadata);
            expect(auth['channelOptions']).toEqual(channelOptions);
            expect(fs.readFileSync).toHaveBeenCalledWith(resolve(sslCert));
        });

        it('should add api-key to metadata when provided', () => {
            const apiKey = 'test-api-key';
            auth = new Auth({
                uri: testUri,
                apiKey
            });

            expect(auth['metadata']).toEqual([['api-key', apiKey]]);
        });

        it('should combine provided metadata with api-key', () => {
            const apiKey = 'test-api-key';
            const metadata: [string, string][] = [['custom-key', 'custom-value']];
            auth = new Auth({
                uri: testUri,
                apiKey,
                metadata
            });

            expect(auth['metadata']).toEqual([
                ['custom-key', 'custom-value'],
                ['api-key', apiKey]
            ]);
        });

        it('should use provided credentials if available', () => {
            const customCredentials = grpc.credentials.createInsecure();
            auth = new Auth({
                uri: testUri,
                credentials: customCredentials
            });

            expect(grpc.Channel).toHaveBeenCalledWith(
                testUri,
                customCredentials,
                {}
            );
        });
    });

    describe('constructor with Python-style arguments', () => {
        it('should initialize with default values', () => {
            auth = new Auth();
            expect(auth['uri']).toBe('localhost:50051');
            expect(auth['useSsl']).toBe(false);
            expect(auth['sslCert']).toBeUndefined();
            expect(auth['metadata']).toEqual([]);
            expect(auth['channelOptions']).toEqual({});
        });

        it('should initialize with custom values', () => {
            const sslCert = 'test-cert.pem';
            const metadataArgs = [['key', 'value']];
            
            auth = new Auth(sslCert, true, testUri, metadataArgs);

            expect(auth['uri']).toBe(testUri);
            expect(auth['useSsl']).toBe(true);
            expect(auth['sslCert']).toBe(sslCert);
            expect(auth['metadata']).toEqual(metadataArgs);
            expect(auth['channelOptions']).toEqual({});
            expect(fs.readFileSync).toHaveBeenCalledWith(resolve(sslCert));
        });

        it('should throw error for invalid metadata format', () => {
            expect(() => {
                new Auth(undefined, false, testUri, [['single']]);
            }).toThrow('Metadata should have 2 parameters in "key" "value" pair. Received 1 parameters.');
        });
    });

    describe('getCallMetadata', () => {
        it('should return empty metadata when none provided', () => {
            auth = new Auth({ uri: testUri });
            const metadata = auth.getCallMetadata();
            expect(metadata instanceof grpc.Metadata).toBe(true);
            expect(metadata.getMap()).toEqual({});
        });

        it('should return metadata with provided values', () => {
            auth = new Auth({
                uri: testUri,
                metadata: [['key1', 'value1'], ['key2', 'value2']]
            });
            const metadata = auth.getCallMetadata();
            expect(metadata instanceof grpc.Metadata).toBe(true);
            expect(metadata.get('key1')).toEqual(['value1']);
            expect(metadata.get('key2')).toEqual(['value2']);
        });

        it('should add multiple values for the same key', () => {
            auth = new Auth({
                uri: testUri,
                metadata: [['key1', 'value1'], ['key1', 'value2']]
            });
            const metadata = auth.getCallMetadata();
            expect(metadata instanceof grpc.Metadata).toBe(true);
            const key1Values = metadata.get('key1');
            expect(key1Values).toHaveLength(2);
            expect(key1Values).toContain('value1');
            expect(key1Values).toContain('value2');
        });
    });

    describe('getAuthMetadata', () => {
        it('should return empty array when no metadata', () => {
            auth = new Auth({ uri: testUri });
            expect(auth.getAuthMetadata()).toEqual([]);
        });

        it('should return metadata array with provided values', () => {
            const metadata: [string, string][] = [['key1', 'value1'], ['key2', 'value2']];
            auth = new Auth({
                uri: testUri,
                metadata
            });
            expect(auth.getAuthMetadata()).toEqual(metadata);
        });

        it('should return metadata including api-key', () => {
            const metadata: [string, string][] = [['key1', 'value1']];
            const apiKey = 'test-api-key';
            auth = new Auth({
                uri: testUri,
                metadata,
                apiKey
            });
            expect(auth.getAuthMetadata()).toEqual([
                ['key1', 'value1'],
                ['api-key', apiKey]
            ]);
        });
    });

    describe('channel creation', () => {
        it('should create insecure channel by default', () => {
            auth = new Auth({ uri: testUri });
            expect(grpc.credentials.createInsecure).toHaveBeenCalled();
            expect(grpc.credentials.createSsl).not.toHaveBeenCalled();
        });

        it('should create SSL channel when useSsl is true', () => {
            auth = new Auth({
                uri: testUri,
                useSsl: true
            });
            expect(grpc.credentials.createSsl).toHaveBeenCalledWith(null);
            expect(grpc.credentials.createInsecure).not.toHaveBeenCalled();
        });

        it('should create SSL channel with cert when provided', () => {
            const sslCert = 'test-cert.pem';
            const certBuffer = Buffer.from('test-cert-content');
            vi.mocked(fs.readFileSync).mockReturnValue(certBuffer);

            auth = new Auth({
                uri: testUri,
                sslCert
            });
            expect(grpc.credentials.createSsl).toHaveBeenCalledWith(certBuffer);
            expect(fs.readFileSync).toHaveBeenCalledWith(resolve(sslCert));
        });

        it('should combine channel credentials with metadata when using SSL', () => {
            const metadata: [string, string][] = [['key', 'value']];
            auth = new Auth({
                uri: testUri,
                useSsl: true,
                metadata
            });
            expect(grpc.credentials.createFromMetadataGenerator).toHaveBeenCalled();
            expect(grpc.credentials.combineChannelCredentials).toHaveBeenCalled();
        });

        it('should use provided channel options', () => {
            const channelOptions = { 'grpc.keepalive_time_ms': 10000 };
            auth = new Auth({
                uri: testUri,
                channelOptions
            });
            expect(grpc.Channel).toHaveBeenCalledWith(
                testUri,
                expect.any(Object),
                channelOptions
            );
        });

        it('should handle file read errors gracefully', () => {
            const sslCert = 'nonexistent.pem';
            vi.mocked(fs.readFileSync).mockImplementation(() => {
                throw new Error('File not found');
            });

            expect(() => {
                new Auth({
                    uri: testUri,
                    sslCert
                });
            }).toThrow();
        });
    });

    describe('deprecated methods', () => {
        it('createChannel should return the same channel instance', () => {
            auth = new Auth({ uri: testUri });
            const channel = auth.createChannel();
            expect(channel).toBe(auth.channel);
        });
    });
});
