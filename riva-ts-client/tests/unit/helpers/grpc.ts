import { vi } from 'vitest';

/**
 * Create a typed gRPC mock with vi.fn() for each method
 */
export const createGrpcMock = <T extends Record<string, any>>(methods: Array<keyof T>) => {
    const mock: Partial<{ [K in keyof T]: ReturnType<typeof vi.fn> }> = {};
    methods.forEach(method => {
        mock[method] = vi.fn();
    });
    return mock as { [K in keyof T]: ReturnType<typeof vi.fn> };
};

/**
 * Create a mock gRPC metadata instance
 */
export const createMetadataMock = () => ({
    get: vi.fn(),
    set: vi.fn(),
    getMap: vi.fn(),
    clone: vi.fn(),
    merge: vi.fn(),
    toHttp2Headers: vi.fn()
});
