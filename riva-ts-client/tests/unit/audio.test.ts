import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AudioDeviceManagerImpl, MicrophoneStream, SoundCallback } from '../../src/client/audio/io';
import { AudioDeviceInfo, MicrophoneStreamOptions, SoundCallbackOptions } from '../../src/client/audio/types';
import { createMockAudioContext, createMockMediaDevices, createMockMediaStream } from './helpers';

describe('AudioDeviceManagerImpl', () => {
    let deviceManager: AudioDeviceManagerImpl;
    const mockAudioContext = createMockAudioContext();
    const mockMediaDevices = createMockMediaDevices();

    beforeEach(() => {
        vi.clearAllMocks();
        (global as any).AudioContext = vi.fn().mockImplementation(() => mockAudioContext);
        (global.navigator as any).mediaDevices = mockMediaDevices;
        deviceManager = new AudioDeviceManagerImpl();
    });

    describe('getDeviceInfo', () => {
        it('should return device info for input device', async () => {
            const mockDevice = {
                deviceId: '1',
                kind: 'audioinput',
                label: 'Test Microphone'
            } as MediaDeviceInfo;
            mockMediaDevices.enumerateDevices.mockResolvedValue([mockDevice]);

            const info = await deviceManager.getDeviceInfo(0);

            expect(info).toEqual<AudioDeviceInfo>({
                index: 0,
                name: 'Test Microphone',
                maxInputChannels: 1,
                maxOutputChannels: 0,
                defaultSampleRate: mockAudioContext.sampleRate,
                defaultLowInputLatency: 0,
                defaultLowOutputLatency: 0,
                defaultHighInputLatency: 0,
                defaultHighOutputLatency: 0
            });
        });

        it('should throw error for non-existent device', async () => {
            mockMediaDevices.enumerateDevices.mockResolvedValue([]);

            await expect(deviceManager.getDeviceInfo(0))
                .rejects.toThrow('Device with ID 0 not found');
        });
    });

    describe('getDefaultInputDeviceInfo', () => {
        it('should return info for default input device', async () => {
            const mockDevice = {
                deviceId: '1',
                kind: 'audioinput',
                label: 'Test Microphone'
            } as MediaDeviceInfo;
            mockMediaDevices.enumerateDevices.mockResolvedValue([mockDevice]);

            const info = await deviceManager.getDefaultInputDeviceInfo();

            expect(info).toEqual<AudioDeviceInfo>({
                index: 0,
                name: 'Test Microphone',
                maxInputChannels: 1,
                maxOutputChannels: 0,
                defaultSampleRate: mockAudioContext.sampleRate,
                defaultLowInputLatency: 0,
                defaultLowOutputLatency: 0,
                defaultHighInputLatency: 0,
                defaultHighOutputLatency: 0
            });
        });

        it('should return null when no input devices found', async () => {
            mockMediaDevices.enumerateDevices.mockResolvedValue([]);
            const info = await deviceManager.getDefaultInputDeviceInfo();
            expect(info).toBeNull();
        });
    });

    describe('listInputDevices', () => {
        it('should list all input devices', async () => {
            const mockDevices = [
                { deviceId: '1', kind: 'audioinput', label: 'Mic 1' },
                { deviceId: '2', kind: 'audioinput', label: 'Mic 2' }
            ] as MediaDeviceInfo[];
            mockMediaDevices.enumerateDevices.mockResolvedValue(mockDevices);

            const devices = await deviceManager.listInputDevices();

            expect(devices).toEqual([
                {
                    index: 0,
                    name: 'Mic 1',
                    maxInputChannels: 1,
                    maxOutputChannels: 0,
                    defaultSampleRate: mockAudioContext.sampleRate,
                    defaultLowInputLatency: 0,
                    defaultLowOutputLatency: 0,
                    defaultHighInputLatency: 0,
                    defaultHighOutputLatency: 0
                },
                {
                    index: 1,
                    name: 'Mic 2',
                    maxInputChannels: 1,
                    maxOutputChannels: 0,
                    defaultSampleRate: mockAudioContext.sampleRate,
                    defaultLowInputLatency: 0,
                    defaultLowOutputLatency: 0,
                    defaultHighInputLatency: 0,
                    defaultHighOutputLatency: 0
                }
            ]);
        });
    });

    describe('listOutputDevices', () => {
        it('should list all output devices', async () => {
            const mockDevices = [
                { deviceId: '1', kind: 'audiooutput', label: 'Speaker 1' },
                { deviceId: '2', kind: 'audiooutput', label: 'Speaker 2' }
            ] as MediaDeviceInfo[];
            mockMediaDevices.enumerateDevices.mockResolvedValue(mockDevices);

            const devices = await deviceManager.listOutputDevices();

            expect(devices).toEqual([
                {
                    index: 0,
                    name: 'Speaker 1',
                    maxInputChannels: 0,
                    maxOutputChannels: 2,
                    defaultSampleRate: mockAudioContext.sampleRate,
                    defaultLowInputLatency: 0,
                    defaultLowOutputLatency: 0,
                    defaultHighInputLatency: 0,
                    defaultHighOutputLatency: 0
                },
                {
                    index: 1,
                    name: 'Speaker 2',
                    maxInputChannels: 0,
                    maxOutputChannels: 2,
                    defaultSampleRate: mockAudioContext.sampleRate,
                    defaultLowInputLatency: 0,
                    defaultLowOutputLatency: 0,
                    defaultHighInputLatency: 0,
                    defaultHighOutputLatency: 0
                }
            ]);
        });
    });
});

describe('MicrophoneStream', () => {
    let micStream: MicrophoneStream;
    const mockAudioContext = createMockAudioContext();
    const mockMediaDevices = createMockMediaDevices();
    const mockTrack = {
        stop: vi.fn(),
        enabled: true
    };
    const mockMediaStream = {
        getTracks: vi.fn().mockReturnValue([mockTrack])
    };

    beforeEach(() => {
        vi.clearAllMocks();
        (global as any).AudioContext = vi.fn().mockImplementation(() => mockAudioContext);
        (global.navigator as any).mediaDevices = mockMediaDevices;
        mockMediaDevices.getUserMedia.mockResolvedValue(mockMediaStream);

        const options: MicrophoneStreamOptions = {
            rate: 16000,
            chunk: 1024,
            device: 1
        };
        micStream = new MicrophoneStream(options);
    });

    describe('start', () => {
        it('should set up audio processing chain', async () => {
            const mockSourceNode = {
                connect: vi.fn(),
                disconnect: vi.fn()
            };
            const mockProcessorNode = {
                connect: vi.fn(),
                disconnect: vi.fn(),
                onaudioprocess: null as any
            };

            mockAudioContext.createMediaStreamSource.mockReturnValue(mockSourceNode);
            mockAudioContext.createScriptProcessor.mockReturnValue(mockProcessorNode);

            await micStream.start();

            expect(mockMediaDevices.getUserMedia).toHaveBeenCalled();
            expect(mockAudioContext.createMediaStreamSource).toHaveBeenCalledWith(mockMediaStream);
            expect(mockSourceNode.connect).toHaveBeenCalled();
            expect(mockProcessorNode.connect).toHaveBeenCalledWith(mockAudioContext.destination);
        });

        it('should emit error on getUserMedia failure', async () => {
            const error = new Error('Permission denied');
            mockMediaDevices.getUserMedia.mockRejectedValue(error);

            await expect(micStream.start()).rejects.toThrow('Permission denied');
        });

        it('should not start if already active', async () => {
            const mockSourceNode = {
                connect: vi.fn(),
                disconnect: vi.fn()
            };
            mockAudioContext.createMediaStreamSource.mockReturnValue(mockSourceNode);

            await micStream.start();
            await micStream.start();

            expect(mockMediaDevices.getUserMedia).toHaveBeenCalledTimes(1);
        });
    });

    describe('stop', () => {
        it('should clean up resources', async () => {
            const mockSourceNode = {
                connect: vi.fn(),
                disconnect: vi.fn()
            };
            const mockProcessorNode = {
                connect: vi.fn(),
                disconnect: vi.fn(),
                onaudioprocess: null as any
            };

            mockAudioContext.createMediaStreamSource.mockReturnValue(mockSourceNode);
            mockAudioContext.createScriptProcessor.mockReturnValue(mockProcessorNode);

            await micStream.start();
            micStream.stop();

            expect(mockTrack.stop).toHaveBeenCalled();
            expect(mockAudioContext.close).toHaveBeenCalled();
            expect(mockSourceNode.disconnect).toHaveBeenCalled();
            expect(mockProcessorNode.disconnect).toHaveBeenCalled();
        });

        it('should do nothing if not active', () => {
            micStream.stop();
            expect(mockAudioContext.close).not.toHaveBeenCalled();
        });
    });

    describe('pause/resume', () => {
        it('should toggle track enabled state', async () => {
            await micStream.start();
            
            micStream.pause();
            expect(mockTrack.enabled).toBe(false);

            micStream.resume();
            expect(mockTrack.enabled).toBe(true);
        });
    });

    describe('isActive', () => {
        it('should return correct active state', async () => {
            expect(micStream.isActive()).toBe(false);
            
            await micStream.start();
            expect(micStream.isActive()).toBe(true);
            
            micStream.stop();
            expect(micStream.isActive()).toBe(false);
        });
    });
});

describe('SoundCallback', () => {
    let soundCallback: SoundCallback;
    const mockAudioContext = createMockAudioContext();
    const options: SoundCallbackOptions = {
        sampwidth: 2,
        nchannels: 1,
        framerate: 44100
    };

    beforeEach(() => {
        vi.clearAllMocks();
        (global as any).AudioContext = vi.fn().mockImplementation(() => mockAudioContext);
        soundCallback = new SoundCallback(options);
    });

    describe('write', () => {
        it('should process audio data correctly', async () => {
            const mockBuffer = Buffer.from([1, 2, 3, 4]);
            const mockAudioBuffer = { duration: 1 };
            const mockSource = {
                buffer: null as AudioBuffer | null,
                connect: vi.fn(),
                start: vi.fn()
            };

            mockAudioContext.decodeAudioData.mockImplementation((_buffer, onSuccess) => {
                if (onSuccess) {
                    onSuccess(mockAudioBuffer as AudioBuffer);
                }
                return Promise.resolve(mockAudioBuffer as AudioBuffer);
            });
            mockAudioContext.createBufferSource.mockReturnValue(mockSource as unknown as AudioBufferSourceNode);

            await soundCallback.write(mockBuffer);

            expect(mockAudioContext.decodeAudioData).toHaveBeenCalled();
            expect(mockSource.buffer).toBe(mockAudioBuffer);
            expect(mockSource.connect).toHaveBeenCalledWith(mockAudioContext.destination);
            expect(mockSource.start).toHaveBeenCalled();
        });

        it('should throw error when closed', async () => {
            await soundCallback.close();
            await expect(soundCallback.write(Buffer.from([1, 2, 3, 4])))
                .rejects.toThrow('Sound callback is closed');
        });

        it('should handle decodeAudioData failure', async () => {
            const error = new Error('Failed to decode audio data');
            mockAudioContext.decodeAudioData.mockRejectedValue(error);

            await expect(soundCallback.write(Buffer.from([1, 2, 3, 4])))
                .rejects.toThrow('Failed to decode audio data');
        });
    });

    describe('close', () => {
        it('should close audio context', async () => {
            await soundCallback.close();
            expect(mockAudioContext.close).toHaveBeenCalled();
        });

        it('should only close once', async () => {
            await soundCallback.close();
            await soundCallback.close();
            expect(mockAudioContext.close).toHaveBeenCalledTimes(1);
        });
    });
});
