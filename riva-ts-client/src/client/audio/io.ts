import { EventEmitter } from 'events';
import {
    AudioDeviceInfo,
    AudioDeviceManager,
    AudioStream,
    AudioStreamCallbacks,
    AudioStreamConfig,
    MicrophoneStreamOptions,
    SoundCallbackOptions
} from './types';

/**
 * Manages audio devices and provides information about them
 */
export class AudioDeviceManagerImpl implements AudioDeviceManager {
    private readonly audioContext: AudioContext;

    constructor() {
        this.audioContext = new AudioContext();
    }

    async getDeviceInfo(deviceId: number): Promise<AudioDeviceInfo> {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const device = devices[deviceId];
        if (!device) {
            throw new Error(`Device with ID ${deviceId} not found`);
        }

        return {
            index: deviceId,
            name: device.label,
            maxInputChannels: device.kind === 'audioinput' ? 1 : 0,
            maxOutputChannels: device.kind === 'audiooutput' ? 2 : 0,
            defaultSampleRate: this.audioContext.sampleRate,
            defaultLowInputLatency: 0,
            defaultLowOutputLatency: 0,
            defaultHighInputLatency: 0,
            defaultHighOutputLatency: 0
        };
    }

    async getDefaultInputDeviceInfo(): Promise<AudioDeviceInfo | null> {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const device = devices.find(d => d.kind === 'audioinput');
        if (!device) {
            return null;
        }

        return {
            index: 0,
            name: device.label,
            maxInputChannels: 1,
            maxOutputChannels: 0,
            defaultSampleRate: this.audioContext.sampleRate,
            defaultLowInputLatency: 0,
            defaultLowOutputLatency: 0,
            defaultHighInputLatency: 0,
            defaultHighOutputLatency: 0
        };
    }

    async listOutputDevices(): Promise<AudioDeviceInfo[]> {
        const devices = await navigator.mediaDevices.enumerateDevices();
        return devices
            .filter(d => d.kind === 'audiooutput')
            .map((device, index) => ({
                index,
                name: device.label,
                maxInputChannels: 0,
                maxOutputChannels: 2,
                defaultSampleRate: this.audioContext.sampleRate,
                defaultLowInputLatency: 0,
                defaultLowOutputLatency: 0,
                defaultHighInputLatency: 0,
                defaultHighOutputLatency: 0
            }));
    }

    async listInputDevices(): Promise<AudioDeviceInfo[]> {
        const devices = await navigator.mediaDevices.enumerateDevices();
        return devices
            .filter(d => d.kind === 'audioinput')
            .map((device, index) => ({
                index,
                name: device.label,
                maxInputChannels: 1,
                maxOutputChannels: 0,
                defaultSampleRate: this.audioContext.sampleRate,
                defaultLowInputLatency: 0,
                defaultLowOutputLatency: 0,
                defaultHighInputLatency: 0,
                defaultHighOutputLatency: 0
            }));
    }
}

/**
 * Handles microphone input streaming
 */
export class MicrophoneStream extends EventEmitter implements AudioStream {
    private readonly options: MicrophoneStreamOptions;
    private mediaStream?: MediaStream;
    private audioContext?: AudioContext;
    private sourceNode?: MediaStreamAudioSourceNode;
    private processorNode?: ScriptProcessorNode;
    private active: boolean = false;

    constructor(options: MicrophoneStreamOptions) {
        super();
        this.options = options;
    }

    async start(): Promise<void> {
        if (this.active) {
            return;
        }

        try {
            this.mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    deviceId: this.options.device ? { exact: String(this.options.device) } : undefined,
                    sampleRate: this.options.rate,
                    channelCount: 1
                }
            });

            this.audioContext = new AudioContext({
                sampleRate: this.options.rate
            });

            this.sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream);
            this.processorNode = this.audioContext.createScriptProcessor(
                this.options.chunk,
                1,
                1
            );

            this.processorNode.onaudioprocess = (e) => {
                const buffer = e.inputBuffer.getChannelData(0);
                this.emit('data', Buffer.from(buffer.buffer));
            };

            this.sourceNode.connect(this.processorNode);
            this.processorNode.connect(this.audioContext.destination);
            this.active = true;
        } catch (error) {
            this.emit('error', error instanceof Error ? error : new Error(String(error)));
        }
    }

    stop(): void {
        if (!this.active) {
            return;
        }

        if (this.processorNode) {
            this.processorNode.disconnect();
            this.processorNode = undefined;
        }

        if (this.sourceNode) {
            this.sourceNode.disconnect();
            this.sourceNode = undefined;
        }

        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = undefined;
        }

        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = undefined;
        }

        this.active = false;
        this.emit('close');
    }

    pause(): void {
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.enabled = false);
        }
    }

    resume(): void {
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.enabled = true);
        }
    }

    isActive(): boolean {
        return this.active;
    }
}

/**
 * Handles audio output
 */
export class SoundCallback {
    private readonly audioContext: AudioContext;
    private readonly options: SoundCallbackOptions;
    private opened: boolean = true;

    constructor(options: SoundCallbackOptions) {
        this.options = options;
        this.audioContext = new AudioContext({
            sampleRate: options.framerate,
            latencyHint: 'interactive'
        });
    }

    async write(audioData: Buffer): Promise<void> {
        if (!this.opened) {
            throw new Error('Sound callback is closed');
        }

        const arrayBuffer = audioData.buffer.slice(
            audioData.byteOffset,
            audioData.byteOffset + audioData.byteLength
        );

        const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
        const source = this.audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(this.audioContext.destination);
        source.start();
    }

    close(): void {
        if (this.opened) {
            this.audioContext.close();
            this.opened = false;
        }
    }
}
