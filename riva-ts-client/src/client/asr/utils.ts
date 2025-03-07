import { Writable } from 'stream';
import { StreamingRecognizeResponse, RecognizeResponse, AudioEncoding } from './types';
import * as wav from 'node-wav';
import * as fs from 'fs';

export type PrintMode = 'no' | 'time' | 'confidence';

export interface WavFileParameters {
    encoding: AudioEncoding;
    sampleRate: number;
}

/**
 * Get WAV file parameters
 */
export async function getWavFileParameters(filePath: string): Promise<WavFileParameters> {
    const buffer = fs.readFileSync(filePath);
    const result = wav.decode(buffer);
    
    return {
        encoding: AudioEncoding.LINEAR_PCM,
        sampleRate: result.sampleRate
    };
}

/**
 * Print streaming recognition results
 */
export function printStreaming(
    responses: AsyncIterable<StreamingRecognizeResponse>,
    outputStreams: Writable[] = [process.stdout],
    additionalInfo: PrintMode = 'no',
    wordTimeOffsets = false,
    showIntermediate = false,
    fileMode = 'w'
): void {
    const write = (text: string) => {
        for (const stream of outputStreams) {
            stream.write(text + '\n');
        }
    };

    (async () => {
        for await (const response of responses) {
            if (!response.results.length) continue;

            for (const result of response.results) {
                if (!showIntermediate && result.isPartial) continue;

                const prefix = result.isPartial ? '>>' : '##';
                let text = `${prefix} ${result.alternatives[0].transcript}`;

                if (additionalInfo === 'time') {
                    text = `${response.timeOffset?.toFixed(2)}s ${text}`;
                } else if (additionalInfo === 'confidence') {
                    text = `${result.alternatives[0].confidence.toFixed(2)} ${text}`;
                }

                write(text);

                if (wordTimeOffsets && result.alternatives[0].words.length > 0) {
                    const words = result.alternatives[0].words.map(word => {
                        const info = [word.word];
                        if (word.startTime !== undefined) {
                            info.push(`${word.startTime.toFixed(2)}s`);
                        }
                        if (word.endTime !== undefined) {
                            info.push(`${word.endTime.toFixed(2)}s`);
                        }
                        if (word.confidence !== undefined) {
                            info.push(`${word.confidence.toFixed(2)}`);
                        }
                        if (word.speakerLabel !== undefined) {
                            info.push(`speaker:${word.speakerLabel}`);
                        }
                        return info.join(' ');
                    });
                    write(`   ${words.join(' | ')}`);
                }
            }
        }
    })();
}

/**
 * Print offline recognition results
 */
export function printOffline(
    response: RecognizeResponse,
    outputStreams: Writable[] = [process.stdout]
): void {
    const write = (text: string) => {
        for (const stream of outputStreams) {
            stream.write(text + '\n');
        }
    };

    if (!response.results.length) return;

    for (const result of response.results) {
        write(`## ${result.alternatives[0].transcript}`);

        if (result.alternatives[0].words.length > 0) {
            const words = result.alternatives[0].words.map(word => {
                const info = [word.word];
                if (word.startTime !== undefined) {
                    info.push(`${word.startTime.toFixed(2)}s`);
                }
                if (word.endTime !== undefined) {
                    info.push(`${word.endTime.toFixed(2)}s`);
                }
                if (word.confidence !== undefined) {
                    info.push(`${word.confidence.toFixed(2)}`);
                }
                if (word.speakerLabel !== undefined) {
                    info.push(`speaker:${word.speakerLabel}`);
                }
                return info.join(' ');
            });
            write(`   ${words.join(' | ')}`);
        }
    }
}
