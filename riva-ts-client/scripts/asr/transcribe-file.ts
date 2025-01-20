

import * as fs from 'fs';
import * as path from 'path';
import * as wavPlayer from 'node-wav-player';
import { program } from 'commander';
import { Auth, ASRService } from '../../src/client';
import { addConnectionArgparseParameters } from '../utils/argparse';
import { addAsrConfigArgparseParameters } from '../utils/asr_argparse';
import { AudioEncoding, StreamingRecognitionConfig, AudioChunk } from '../../src/client/asr/types';
import { getWavFileParameters } from '../../src/client/asr/utils';

class AudioPlayer {
    private tempFile: string;

    constructor() {
        this.tempFile = path.join(process.cwd(), '.temp_audio.wav');
    }

    async play(audioData: Buffer): Promise<void> {
        fs.writeFileSync(this.tempFile, audioData);
        try {
            await wavPlayer.play({ path: this.tempFile });
        } catch (error) {
            console.error('Error playing audio:', error);
        }
    }

    close(): void {
        if (fs.existsSync(this.tempFile)) {
            fs.unlinkSync(this.tempFile);
        }
    }
}

async function* createAudioSource(fileStream: fs.ReadStream): AsyncGenerator<AudioChunk, void, unknown> {
    try {
        for await (const chunk of fileStream) {
            if (chunk instanceof Buffer && chunk.length > 0) {
                yield { audioContent: chunk };
            }
        }
    } finally {
        fileStream.destroy();
    }
}

async function main() {
    program
        .description(
            'Streaming transcription of a file via Riva AI Services. Streaming means that audio is sent to a ' +
            'server in small chunks and transcripts are returned as soon as these transcripts are ready. ' +
            'You may play transcribed audio simultaneously with transcribing by setting --play-audio option.'
        )
        .option('--input-file <file>', 'A path to a local file to stream.')
        .option('--list-models', 'List available models.')
        .option('--show-intermediate', 'Show intermediate transcripts as they are available.')
        .option('--play-audio', 'Whether to play input audio simultaneously with transcribing.')
        .option('--file-streaming-chunk <number>', 'A maximum number of frames in one chunk sent to server.', '1600')
        .option(
            '--simulate-realtime',
            'Option to simulate realtime transcription. Audio fragments are sent to a server at a pace that mimics normal speech.'
        );

    addConnectionArgparseParameters(program);
    addAsrConfigArgparseParameters(program);

    program.parse();

    const options = program.opts();

    if (!options.inputFile && !options.listModels) {
        console.error('Either --input-file or --list-models must be specified');
        process.exit(1);
    }

    const auth = new Auth({
        uri: options.server,
        useSsl: options.useSsl,
        sslCert: options.sslCert,
        metadata: options.metadata?.map(m => {
            const [key, value] = m.split('=');
            return [key, value] as [string, string];
        })
    });

    const asr = new ASRService({
        serverUrl: options.server,
        auth
    });

    if (options.listModels) {
        try {
            const models = await asr.listModels();
            console.log('Available models:');
            for (const model of models) {
                console.log(`  ${model.name}`);
                console.log(`    Languages: ${model.languages.join(', ')}`);
                console.log(`    Sample Rate: ${model.sampleRate}Hz`);
                console.log(`    Streaming: ${model.streaming}`);
                console.log();
            }
            return;
        } catch (error) {
            console.error('Error listing models:', error);
            process.exit(1);
        }
    }

    const inputFile = path.resolve(options.inputFile);
    if (!fs.existsSync(inputFile)) {
        console.error(`Input file ${inputFile} does not exist`);
        process.exit(1);
    }

    const { encoding, sampleRate } = await getWavFileParameters(inputFile);
    if (encoding !== AudioEncoding.LINEAR_PCM) {
        console.error('Only LINEAR_PCM WAV files are supported');
        process.exit(1);
    }

    const fileStream = fs.createReadStream(inputFile);
    let audioPlayer: AudioPlayer | null = null;

    if (options.playAudio) {
        audioPlayer = new AudioPlayer();
    }

    try {
        const config: StreamingRecognitionConfig = {
            config: {
                encoding,
                sampleRateHertz: sampleRate,
                languageCode: options.languageCode || 'en-US',
                maxAlternatives: options.maxAlternatives ? parseInt(options.maxAlternatives) : 1,
                profanityFilter: options.profanityFilter,
                enableWordTimeOffsets: options.wordTimeOffsets,
                enableAutomaticPunctuation: options.automaticPunctuation
            }
        };

        const audioSource = createAudioSource(fileStream);
        const responses = await asr.streamingRecognize(audioSource, config);

        for await (const response of responses) {
            if (response.results.length > 0) {
                const result = response.results[0];
                if (result.alternatives.length > 0) {
                    const transcript = result.alternatives[0].transcript;
                    if (!result.isPartial) {
                        console.log(`Final transcript: ${transcript}`);
                    } else if (options.showIntermediate) {
                        console.log(`Intermediate transcript: ${transcript}`);
                    }
                }
            }

            if (audioPlayer && response.audioContent) {
                const audioBuffer = Buffer.from(response.audioContent);
                await audioPlayer.play(audioBuffer);
            }
        }
    } catch (error) {
        console.error('Error in transcription:', error);
        process.exit(1);
    } finally {
        if (audioPlayer) {
            audioPlayer.close();
        }
    }
}

if (require.main === module) {
    main().catch(console.error);
}
