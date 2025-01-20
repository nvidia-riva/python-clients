import { vi, type Mock } from 'vitest';

export type MockStreamEvents = 'data' | 'error' | 'end' | 'close';

export interface MockStream {
    write: Mock;
    end: Mock;
    on: Mock<[event: MockStreamEvents, callback: (...args: any[]) => void], any>;
    removeListener: Mock;
    [Symbol.asyncIterator](): AsyncIterator<any>;
}

export interface MockStreamOptions {
    onError?: (error: Error) => void;
    onData?: (data: any) => void;
    onEnd?: () => void;
}

/**
 * Creates a mock stream with vitest mock functions
 */
export const createMockStream = (options?: MockStreamOptions): MockStream => {
    const write = vi.fn();
    const end = vi.fn();
    const removeListener = vi.fn();
    const on = vi.fn((event: MockStreamEvents, callback: (...args: any[]) => void) => {
        if (event === 'error' && options?.onError) {
            callback(new Error('Stream error'));
        }
        if (event === 'data' && options?.onData) {
            callback({});
        }
        if (event === 'end' && options?.onEnd) {
            callback();
        }
    });

    return {
        write,
        end,
        on,
        removeListener,
        async *[Symbol.asyncIterator]() {
            if (options?.onError) {
                throw new Error('Stream error');
            }
            if (options?.onData) {
                yield {};
            }
            if (options?.onEnd) {
                return;
            }
        }
    };
};
