import { vi } from 'vitest';

/**
 * Create mocks for Web Audio API components
 */
export const createAudioMocks = () => {
    const mockTrack = {
        stop: vi.fn(),
        enabled: true,
        kind: 'audio',
        label: 'mock-track',
        id: 'mock-track-id',
        muted: false,
        readyState: 'live',
        applyConstraints: vi.fn(),
        clone: vi.fn(),
        getCapabilities: vi.fn(),
        getConstraints: vi.fn(),
        getSettings: vi.fn()
    };

    const mockMediaStream = {
        active: true,
        id: 'mock-stream-id',
        getTracks: () => [mockTrack],
        getAudioTracks: () => [mockTrack],
        addTrack: vi.fn(),
        clone: vi.fn(),
        getTrackById: vi.fn(),
        removeTrack: vi.fn()
    };

    const mockAudioContext = {
        state: 'running',
        sampleRate: 44100,
        destination: {},
        listener: {},
        currentTime: 0,
        decodeAudioData: vi.fn(),
        createBuffer: vi.fn(),
        createBufferSource: vi.fn(),
        createMediaStreamSource: vi.fn(),
        createAnalyser: vi.fn(),
        createBiquadFilter: vi.fn(),
        createGain: vi.fn(),
        createOscillator: vi.fn(),
        createPanner: vi.fn(),
        createDynamicsCompressor: vi.fn(),
        close: vi.fn(),
        suspend: vi.fn(),
        resume: vi.fn()
    };

    return { 
        mockTrack, 
        mockMediaStream, 
        mockAudioContext,
        mockAudioBuffer: {
            duration: 1.0,
            length: 44100,
            numberOfChannels: 1,
            sampleRate: 44100,
            getChannelData: vi.fn().mockReturnValue(new Float32Array(44100))
        }
    };
};
