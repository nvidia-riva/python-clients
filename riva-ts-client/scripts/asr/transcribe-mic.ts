

import { program } from 'commander';
import * as mic from 'mic';
import { Auth, ASRService } from '../../src/client';
import { addConnectionArgparseParameters } from '../utils/argparse';
import { addAsrConfigArgparseParameters } from '../utils/asr_argparse';
import { AudioEncoding, StreamingRecognitionConfig, AudioChunk } from '../../src/client/asr/types';

async function* createMicAudioSource(micInstance: mic.MicInstance): AsyncGenerator<AudioChunk, void, unknown> {
    const audioStream = micInstance.getAudioStream();
    try {
        for await (const chunk of audioStream) {
            if (chunk instanceof Buffer && chunk.length > 0) {
                yield { audioContent: chunk };
            }
        }
    } finally {
        micInstance.stop();
    }
}

async function main() {
    program
        .description('Streaming transcription from microphone via Riva AI Services')
        .option('--list-models', 'List available models.')
        .option('--show-intermediate', 'Show intermediate transcripts as they are available.')
        .option('--device <device>', 'Input device to use.')
        .option('--rate <rate>', 'Input device sample rate.', '16000')
        .option('--channels <channels>', 'Number of input channels.', '1');

    addConnectionArgparseParameters(program);
    addAsrConfigArgparseParameters(program);

    program.parse();

    const options = program.opts();

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

    const micInstance = mic({
        rate: options.rate,
        channels: options.channels,
        debug: false,
        device: options.device
    });

    const config: StreamingRecognitionConfig = {
        config: {
            encoding: AudioEncoding.LINEAR_PCM,
            sampleRateHertz: parseInt(options.rate),
            languageCode: options.languageCode || 'en-US',
            maxAlternatives: options.maxAlternatives ? parseInt(options.maxAlternatives) : 1,
            profanityFilter: options.profanityFilter,
            enableWordTimeOffsets: options.wordTimeOffsets,
            enableAutomaticPunctuation: options.automaticPunctuation
        }
    };

    try {
        const audioSource = createMicAudioSource(micInstance);
        micInstance.start();

        console.log('Listening... Press Ctrl+C to stop.');

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
        }
    } catch (error) {
        console.error('Error in transcription:', error);
        process.exit(1);
    } finally {
        micInstance.stop();
    }
}

if (require.main === module) {
    main().catch(console.error);
}
