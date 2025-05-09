import { Transform, TransformCallback } from 'stream';
import { AudioEncoding } from '../asr/types';

export interface AudioTransformOptions {
    sourceSampleRate: number;
    targetSampleRate: number;
    sourceChannels: number;
    targetChannels: number;
    sourceEncoding: AudioEncoding;
    targetEncoding: AudioEncoding;
}

/**
 * Base class for audio transformations
 */
export abstract class AudioTransform extends Transform {
    protected readonly options: AudioTransformOptions;

    constructor(options: AudioTransformOptions) {
        super();
        this.options = options;
    }

    abstract _transform(chunk: Buffer, encoding: string, callback: TransformCallback): void;
}

/**
 * Transforms audio sample rate
 */
export class SampleRateTransform extends AudioTransform {
    private remainder: Buffer = Buffer.alloc(0);

    _transform(chunk: Buffer, _encoding: string, callback: TransformCallback): void {
        if (this.options.sourceSampleRate === this.options.targetSampleRate) {
            this.push(chunk);
            callback();
            return;
        }

        // Combine with remainder from previous chunk
        const buffer = Buffer.concat([this.remainder, chunk]);
        const ratio = this.options.targetSampleRate / this.options.sourceSampleRate;
        const bytesPerSample = 2; // Assuming 16-bit audio
        const samplesPerChannel = Math.floor(buffer.length / (bytesPerSample * this.options.sourceChannels));
        const targetSamples = Math.floor(samplesPerChannel * ratio);
        const targetSize = targetSamples * bytesPerSample * this.options.targetChannels;

        // Process complete samples
        if (targetSize > 0) {
            const resampledData = this.resample(
                buffer.slice(0, samplesPerChannel * bytesPerSample * this.options.sourceChannels),
                ratio
            );
            this.push(resampledData);

            // Save remainder for next chunk
            this.remainder = buffer.slice(samplesPerChannel * bytesPerSample * this.options.sourceChannels);
        } else {
            this.remainder = buffer;
        }

        callback();
    }

    private resample(buffer: Buffer, ratio: number): Buffer {
        // Simple linear interpolation - for production, use a proper resampling library
        const result = Buffer.alloc(Math.floor(buffer.length * ratio));
        const bytesPerSample = 2;
        const samplesPerChannel = buffer.length / (bytesPerSample * this.options.sourceChannels);

        for (let i = 0; i < Math.floor(samplesPerChannel * ratio); i++) {
            const sourceIdx = Math.floor(i / ratio);
            for (let channel = 0; channel < this.options.targetChannels; channel++) {
                const value = buffer.readInt16LE(sourceIdx * bytesPerSample * this.options.sourceChannels + channel * bytesPerSample);
                result.writeInt16LE(value, i * bytesPerSample * this.options.targetChannels + channel * bytesPerSample);
            }
        }

        return result;
    }
}

/**
 * Transforms number of audio channels
 */
export class ChannelTransform extends AudioTransform {
    _transform(chunk: Buffer, _encoding: string, callback: TransformCallback): void {
        if (this.options.sourceChannels === this.options.targetChannels) {
            this.push(chunk);
            callback();
            return;
        }

        const bytesPerSample = 2; // Assuming 16-bit audio
        const samplesPerChannel = chunk.length / (bytesPerSample * this.options.sourceChannels);
        const result = Buffer.alloc(samplesPerChannel * bytesPerSample * this.options.targetChannels);

        for (let i = 0; i < samplesPerChannel; i++) {
            if (this.options.sourceChannels > this.options.targetChannels) {
                // Downmix channels (average)
                let sum = 0;
                for (let ch = 0; ch < this.options.sourceChannels; ch++) {
                    sum += chunk.readInt16LE(i * bytesPerSample * this.options.sourceChannels + ch * bytesPerSample);
                }
                const avg = Math.round(sum / this.options.sourceChannels);
                result.writeInt16LE(avg, i * bytesPerSample);
            } else {
                // Upmix channels (duplicate)
                const value = chunk.readInt16LE(i * bytesPerSample * this.options.sourceChannels);
                for (let ch = 0; ch < this.options.targetChannels; ch++) {
                    result.writeInt16LE(value, i * bytesPerSample * this.options.targetChannels + ch * bytesPerSample);
                }
            }
        }

        this.push(result);
        callback();
    }
}

/**
 * Creates a transform stream pipeline for audio processing
 */
export function createAudioTransformPipeline(options: AudioTransformOptions): Transform {
    const transforms: Transform[] = [];

    // Add necessary transforms in the correct order
    if (options.sourceSampleRate !== options.targetSampleRate) {
        transforms.push(new SampleRateTransform(options));
    }

    if (options.sourceChannels !== options.targetChannels) {
        transforms.push(new ChannelTransform(options));
    }

    // Chain transforms
    return transforms.reduce((prev, curr) => prev.pipe(curr));
}
