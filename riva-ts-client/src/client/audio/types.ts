export interface AudioDeviceInfo {
    index: number;
    name: string;
    maxInputChannels: number;
    maxOutputChannels: number;
    defaultSampleRate: number;
    defaultLowInputLatency: number;
    defaultLowOutputLatency: number;
    defaultHighInputLatency: number;
    defaultHighOutputLatency: number;
}

export interface MicrophoneStreamOptions {
    rate: number;
    chunk: number;
    device?: number;
}

export interface AudioStreamCallbacks {
    onData?: (chunk: Buffer) => void;
    onError?: (error: Error) => void;
    onClose?: () => void;
}

export interface SoundCallbackOptions {
    outputDeviceIndex?: number;
    sampwidth: number;
    nchannels: number;
    framerate: number;
}

export interface AudioStreamConfig {
    format: number;
    channels: number;
    rate: number;
    framesPerBuffer: number;
    inputDevice?: number;
    outputDevice?: number;
}

export interface AudioDeviceManager {
    getDeviceInfo(deviceId: number): Promise<AudioDeviceInfo>;
    getDefaultInputDeviceInfo(): Promise<AudioDeviceInfo | null>;
    listOutputDevices(): Promise<AudioDeviceInfo[]>;
    listInputDevices(): Promise<AudioDeviceInfo[]>;
}

export interface AudioStream {
    start(): void;
    stop(): void;
    pause(): void;
    resume(): void;
    isActive(): boolean;
    on(event: 'data', callback: (chunk: Buffer) => void): void;
    on(event: 'error', callback: (error: Error) => void): void;
    on(event: 'close', callback: () => void): void;
    off(event: string, callback: Function): void;
}
