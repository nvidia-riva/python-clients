import { createReadStream } from 'fs';
import { promisify } from 'util';
import { Transform, TransformCallback } from 'stream';
import { Readable } from 'stream';

export interface WavFileParameters {
    nframes: number;
    framerate: number;
    duration: number;
    nchannels: number;
    sampwidth: number;
    dataOffset: number;
}

export class WavHeaderError extends Error {
    constructor(message: string) {
        super(message);
        this.name = 'WavHeaderError';
    }
}

/**
 * Extracts WAV file parameters from a file
 * @param filePath Path to WAV file
 */
export async function getWavFileParameters(filePath: string): Promise<WavFileParameters> {
    const buffer = Buffer.alloc(44); // Standard WAV header size
    const stream = createReadStream(filePath, { start: 0, end: 43 }) as Readable;
    
    return new Promise((resolve, reject) => {
        stream.on('error', reject);
        stream.on('data', (chunk: Buffer) => {
            try {
                // Verify RIFF header
                if (chunk.toString('ascii', 0, 4) !== 'RIFF') {
                    throw new WavHeaderError('Not a valid WAV file: missing RIFF header');
                }

                // Verify WAVE format
                if (chunk.toString('ascii', 8, 12) !== 'WAVE') {
                    throw new WavHeaderError('Not a valid WAV file: missing WAVE format');
                }

                // Get format chunk
                if (chunk.toString('ascii', 12, 16) !== 'fmt ') {
                    throw new WavHeaderError('Not a valid WAV file: missing fmt chunk');
                }

                const params: WavFileParameters = {
                    nchannels: chunk.readUInt16LE(22),
                    framerate: chunk.readUInt32LE(24),
                    sampwidth: chunk.readUInt16LE(34) / 8,
                    dataOffset: 44, // Standard WAV header size
                    nframes: chunk.readUInt32LE(40) / (chunk.readUInt16LE(22) * chunk.readUInt16LE(34) / 8),
                    duration: 0 // Will be calculated
                };

                params.duration = params.nframes / params.framerate;
                resolve(params);
            } catch (error) {
                reject(error);
            } finally {
                stream.destroy();
            }
        });
    });
}

/**
 * Transform stream that splits audio data into chunks
 */
export class AudioChunkTransform extends Transform {
    private readonly chunkSize: number;
    private buffer: Buffer;

    constructor(chunkSize: number) {
        super();
        this.chunkSize = chunkSize;
        this.buffer = Buffer.alloc(0);
    }

    _transform(chunk: Buffer, _encoding: string, callback: TransformCallback): void {
        // Append new data to buffer
        this.buffer = Buffer.concat([this.buffer, chunk]);

        // Process complete chunks
        while (this.buffer.length >= this.chunkSize) {
            const chunkData = this.buffer.slice(0, this.chunkSize);
            this.push(chunkData);
            this.buffer = this.buffer.slice(this.chunkSize);
        }

        callback();
    }

    _flush(callback: TransformCallback): void {
        // Push remaining data if any
        if (this.buffer.length > 0) {
            this.push(this.buffer);
        }
        callback();
    }
}

/**
 * Creates an async iterator for audio chunks from a WAV file
 */
export async function* createAudioChunkIterator(
    filePath: string,
    chunkFrames: number,
    params?: WavFileParameters
): AsyncGenerator<{ audioContent: Buffer; timeOffset: number }> {
    // Get WAV parameters if not provided
    const wavParams = params || await getWavFileParameters(filePath);
    const chunkSize = chunkFrames * wavParams.nchannels * wavParams.sampwidth;
    
    // Create read stream starting after WAV header
    const stream = createReadStream(filePath, { 
        start: wavParams.dataOffset,
        highWaterMark: chunkSize
    });

    // Create transform stream for chunking
    const chunker = new AudioChunkTransform(chunkSize);
    stream.pipe(chunker);

    let timeOffset = 0;
    const frameTime = 1 / wavParams.framerate;

    for await (const chunk of chunker) {
        yield {
            audioContent: chunk,
            timeOffset
        };
        timeOffset += chunkFrames * frameTime;
    }
}
