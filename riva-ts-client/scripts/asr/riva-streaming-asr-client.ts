

import * as fs from 'fs';
import * as path from 'path';
import { program } from 'commander';
import { Auth, ASRService } from '../../src/client';
import { addConnectionArgparseParameters } from '../utils/argparse';
import { addAsrConfigArgparseParameters } from '../utils/asr_argparse';
import { AudioEncoding, RecognitionConfig } from '../../src/client/asr/types';
import { getWavFileParameters } from '../../src/client/asr/utils';

interface StreamingTranscriptionOptions {
    inputFile: string;
    server: string;
    useSsl: boolean;
    sslCert?: string;
    metadata?: string[];
    maxAlternatives?: number;
    profanityFilter?: boolean;
    wordTimeOffsets?: boolean;
    automaticPunctuation?: boolean;
    noVerbatimTranscripts?: boolean;
    speakerDiarization?: boolean;
    diarizationMaxSpeakers?: string;
    boostedLmWords?: string[];
    boostedLmScore?: string;
    startHistory?: string;
    startThreshold?: string;
    stopHistory?: string;
    stopHistoryEou?: string;
    stopThreshold?: string;
    stopThresholdEou?: string;
}

async function streamingTranscriptionWorker(options: StreamingTranscriptionOptions, threadId: number) {
    const outputFile = path.join(process.cwd(), `output_${threadId}.txt`);
    
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
        auth,
        serverUrl: options.server
    });

    const { encoding, sampleRate } = await getWavFileParameters(options.inputFile);
    if (encoding !== AudioEncoding.LINEAR_PCM) {
        throw new Error('Only LINEAR_PCM WAV files are supported');
    }

    const audioContent = fs.readFileSync(options.inputFile);

    try {
        const config: RecognitionConfig = {
            encoding,
            sampleRateHertz: sampleRate,
            languageCode: 'en-US',
            maxAlternatives: options.maxAlternatives,
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
            }] : undefined,
            endpointingConfig: {
                startHistory: options.startHistory ? parseInt(options.startHistory) : undefined,
                startThreshold: options.startThreshold ? parseFloat(options.startThreshold) : undefined,
                stopHistory: options.stopHistory ? parseInt(options.stopHistory) : undefined,
                stopHistoryEou: options.stopHistoryEou ? parseInt(options.stopHistoryEou) : undefined,
                stopThreshold: options.stopThreshold ? parseFloat(options.stopThreshold) : undefined,
                stopThresholdEou: options.stopThresholdEou ? parseFloat(options.stopThresholdEou) : undefined
            }
        };

        const responses = await asr.streamingRecognize(
            { content: audioContent },
            { config }
        );

        const outputStream = fs.createWriteStream(outputFile);

        for await (const response of responses) {
            if (response.results.length === 0) continue;

            for (const result of response.results) {
                if (result.alternatives.length === 0) continue;

                const transcript = result.alternatives[0].transcript;
                if (result.isPartial) {
                    process.stdout.write(`\rIntermediate transcript: ${transcript}`);
                } else {
                    console.log(`\nFinal transcript: ${transcript}`);
                    outputStream.write(`${transcript}\n`);
                }

                if (options.wordTimeOffsets && !result.isPartial) {
                    console.log('\nWord timings:');
                    for (const word of result.alternatives[0].words || []) {
                        const start = word.startTime || 0;
                        const end = word.endTime || 0;
                        console.log(`  ${word.word}: ${start}s - ${end}s`);
                    }
                }
            }
        }

        outputStream.end();
    } catch (error) {
        console.error(`Thread ${threadId} error:`, error);
        throw error;
    }
}

async function main() {
    program
        .description('Streaming transcription via Riva AI Services')
        .requiredOption('--input-file <file>', 'A path to a local file to transcribe.')
        .option('--num-parallel <number>', 'Number of parallel transcription threads.', '1')
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
    const numParallel = parseInt(options.numParallel);

    const promises = Array.from({ length: numParallel }, (_, i) =>
        streamingTranscriptionWorker(options as StreamingTranscriptionOptions, i + 1)
    );

    try {
        await Promise.all(promises);
        console.log('\nAll transcription threads completed successfully');
    } catch (error) {
        console.error('Error in transcription:', error);
        process.exit(1);
    }
}

if (require.main === module) {
    main().catch(console.error);
}
