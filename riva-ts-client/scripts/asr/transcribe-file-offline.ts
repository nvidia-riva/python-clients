

import * as fs from 'fs';
import * as path from 'path';
import { program } from 'commander';
import { Auth, ASRService } from '../../src/client';
import { addConnectionArgparseParameters } from '../utils/argparse';
import { addAsrConfigArgparseParameters } from '../utils/asr_argparse';
import { AudioEncoding, RecognitionConfig } from '../../src/client/asr/types';
import { getWavFileParameters } from '../../src/client/asr/utils';

async function main() {
    program
        .description('Offline file transcription via Riva AI Services')
        .requiredOption('--input-file <file>', 'A path to a local file to transcribe.')
        .option('--boosted-lm-words <words...>', 'List of words to boost when decoding.')
        .option('--boosted-lm-score <score>', 'Score by which to boost the boosted words.', '4.0')
        .option('--speaker-diarization', 'Enable speaker diarization.')
        .option('--diarization-max-speakers <number>', 'Maximum number of speakers to identify.', '6')
        .option('--start-history <number>', 'Number of frames to use for start threshold.', '30')
        .option('--start-threshold <number>', 'Threshold for starting audio.', '0.0')
        .option('--stop-history <number>', 'Number of frames to use for stop threshold.', '30')
        .option('--stop-history-eou <number>', 'Number of frames to use for end-of-utterance detection.', '30')
        .option('--stop-threshold <number>', 'Threshold for stopping audio.', '0.0')
        .option('--stop-threshold-eou <number>', 'Threshold for end-of-utterance detection.', '0.0');

    addConnectionArgparseParameters(program);
    addAsrConfigArgparseParameters(program);

    program.parse();

    const options = program.opts();
    const inputFile = path.resolve(options.inputFile);

    if (!fs.existsSync(inputFile)) {
        console.error(`Input file ${inputFile} does not exist`);
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

    const { encoding, sampleRate } = await getWavFileParameters(inputFile);
    if (encoding !== AudioEncoding.LINEAR_PCM) {
        console.error('Only LINEAR_PCM WAV files are supported');
        process.exit(1);
    }

    try {
        const audioContent = fs.readFileSync(inputFile);
        
        const config: RecognitionConfig = {
            encoding,
            sampleRateHertz: sampleRate,
            languageCode: options.languageCode || 'en-US',
            maxAlternatives: options.maxAlternatives ? parseInt(options.maxAlternatives) : 1,
            profanityFilter: options.profanityFilter,
            enableWordTimeOffsets: options.wordTimeOffsets,
            enableAutomaticPunctuation: options.automaticPunctuation,
            enableSpeakerDiarization: options.speakerDiarization,
            diarizationConfig: options.speakerDiarization ? {
                enableSpeakerDiarization: true,
                maxSpeakerCount: options.diarizationMaxSpeakers ? parseInt(options.diarizationMaxSpeakers) : undefined
            } : undefined,
            speechContexts: options.boostedLmWords ? [{
                phrases: options.boostedLmWords,
                boost: options.boostedLmScore ? parseFloat(options.boostedLmScore) : 1.0
            }] : undefined
        };

        const response = await asr.recognize(audioContent, config);

        for (const result of response.results) {
            if (result.alternatives.length === 0) continue;

            const transcript = result.alternatives[0].transcript;
            console.log(`\nTranscript: ${transcript}`);

            if (options.wordTimeOffsets) {
                console.log('\nWord timings:');
                for (const word of result.alternatives[0].words || []) {
                    const start = word.startTime || 0;
                    const end = word.endTime || 0;
                    console.log(`  ${word.word}: ${start}s - ${end}s`);
                }
            }

            if (options.speakerDiarization && result.alternatives[0].words) {
                console.log('\nSpeaker diarization:');
                for (const word of result.alternatives[0].words) {
                    if (word.speakerTag) {
                        console.log(`  Speaker ${word.speakerTag}: ${word.word}`);
                    }
                }
            }
        }
    } catch (error) {
        console.error('Error in transcription:', error);
        process.exit(1);
    }
}

if (require.main === module) {
    main().catch(console.error);
}
