

import * as fs from 'fs';
import * as path from 'path';
import * as wavPlayer from 'node-wav-player';
import { program } from 'commander';
import { Auth, SpeechSynthesisService } from '../../src/client';
import { addConnectionArgparseParameters } from '../utils/argparse';
import { AudioEncoding } from '../../src/client/asr/types';

interface CustomDictionary {
    [key: string]: string;
}

function readFileToDict(filePath: string): CustomDictionary {
    const resultDict: CustomDictionary = {};
    const fileContent = fs.readFileSync(filePath, 'utf-8');
    const lines = fileContent.split('\n');

    for (const [lineNumber, line] of lines.entries()) {
        const trimmedLine = line.trim();
        if (!trimmedLine) continue;

        try {
            const [key, value] = trimmedLine.split(/\s{2,}/);
            if (key && value) {
                resultDict[key.trim()] = value.trim();
            } else {
                console.warn(`Warning: Malformed line ${lineNumber + 1}`);
            }
        } catch (error) {
            console.warn(`Warning: Malformed line ${lineNumber + 1}`);
            continue;
        }
    }

    if (Object.keys(resultDict).length === 0) {
        throw new Error("No valid entries found in the file.");
    }

    return resultDict;
}

class AudioPlayer {
    private tempFile: string;

    constructor() {
        this.tempFile = path.join(process.cwd(), '.temp_audio.wav');
    }

    async write(audioData: Uint8Array): Promise<void> {
        fs.writeFileSync(this.tempFile, Buffer.from(audioData));
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

async function main() {
    program
        .description('Speech synthesis via Riva AI Services')
        .option('--text <text>', 'Text input to synthesize.')
        .option('--list-devices', 'List output audio devices indices.')
        .option('--list-voices', 'List available voices.')
        .option('--voice <voice>', 'A voice name to use. If this parameter is missing, then the server will try a first available model based on parameter `--language-code`.')
        .option('--audio_prompt_file <file>', 'An input audio prompt (.wav) file for zero shot model. This is required to do zero shot inferencing.')
        .option('-o, --output <file>', 'Output file .wav file to write synthesized audio.', 'output.wav')
        .option('--quality <number>', 'Number of times decoder should be run on the output audio. A higher number improves quality but introduces latencies.', parseInt)
        .option('--play-audio', 'Whether to play input audio simultaneously with transcribing.')
        .option('--output-device <number>', 'Output device to use.', parseInt)
        .option('--language-code <code>', 'A language of input text.', 'en-US')
        .option('--sample-rate-hz <rate>', 'Number of audio frames per second in synthesized audio.', parseInt, 44100)
        .option('--custom-dictionary <file>', 'A file path to a user dictionary with key-value pairs separated by double spaces.')
        .option('--stream', 'If set, streaming synthesis is applied. Audio is yielded as it gets ready. Otherwise, synthesized audio is returned in 1 response when all text is processed.');

    addConnectionArgparseParameters(program);
    program.parse();

    const options = program.opts();
    const outputPath = path.resolve(options.output);

    if (fs.existsSync(outputPath) && fs.statSync(outputPath).isDirectory()) {
        console.error("Empty output file path not allowed");
        return;
    }

    if (options.listDevices) {
        console.log("Audio devices listing is not supported in this version");
        return;
    }

    const auth = new Auth({
        uri: options.server,
        useSsl: options.useSsl,
        sslCert: options.sslCert,
        credentials: options.credentials,
        metadata: options.metadata?.map(m => {
            const [key, value] = m.split('=');
            return [key, value] as [string, string];
        })
    });

    const service = new SpeechSynthesisService({
        serverUrl: options.server,
        auth: {
            ssl: options.useSsl,
            sslCert: options.sslCert,
            metadata: options.metadata?.map(m => {
                const [key, value] = m.split('=');
                return [key, value] as [string, string];
            })
        }
    });

    let soundStream: AudioPlayer | null = null;
    let outFile: fs.WriteStream | null = null;

    if (options.listVoices) {
        try {
            const configResponse = await service.getRivaSynthesisConfig();
            const ttsModels: { [key: string]: { voices: string[] } } = {};

            for (const modelConfig of configResponse.modelConfig) {
                const languageCode = modelConfig.parameters.languageCode;
                const voiceName = modelConfig.parameters.voiceName;
                const subvoices = modelConfig.parameters.subvoices
                    .split(',')
                    .map((voice: string) => voice.split(':')[0]);
                const fullVoiceNames = subvoices.map((subvoice: string) => `${voiceName}.${subvoice}`);

                if (languageCode in ttsModels) {
                    ttsModels[languageCode].voices.push(...fullVoiceNames);
                } else {
                    ttsModels[languageCode] = { voices: fullVoiceNames };
                }
            }

            console.log(JSON.stringify(ttsModels, null, 4));
            return;
        } catch (error) {
            console.error('Error getting voices:', error);
            return;
        }
    }

    if (!options.text) {
        console.error("No input text provided");
        return;
    }

    try {
        if (options.outputDevice !== undefined || options.playAudio) {
            soundStream = new AudioPlayer();
        }

        if (outputPath) {
            outFile = fs.createWriteStream(outputPath);
        }

        let customDictionaryInput: CustomDictionary = {};
        if (options.customDictionary) {
            customDictionaryInput = readFileToDict(options.customDictionary);
        }

        console.log("Generating audio for request...");
        const start = Date.now();

        if (options.stream) {
            const responses = service.synthesizeOnline(
                options.text,
                options.voice,
                options.languageCode,
                AudioEncoding.LINEAR_PCM,
                options.sampleRateHz,
                options.audioPromptFile,
                AudioEncoding.LINEAR_PCM,
                options.quality ?? 20,
                customDictionaryInput
            );

            let first = true;
            for await (const resp of responses) {
                const stop = Date.now();
                if (first) {
                    console.log(`Time to first audio: ${(stop - start) / 1000}s`);
                    first = false;
                }
                if (soundStream) {
                    await soundStream.write(resp.audio);
                }
                if (outFile) {
                    outFile.write(Buffer.from(resp.audio));
                }
            }
        } else {
            const resp = await service.synthesize(
                options.text,
                options.voice,
                options.languageCode,
                AudioEncoding.LINEAR_PCM,
                options.sampleRateHz,
                options.audioPromptFile,
                AudioEncoding.LINEAR_PCM,
                options.quality ?? 20,
                false,
                customDictionaryInput
            );

            const stop = Date.now();
            console.log(`Time spent: ${(stop - start) / 1000}s`);

            if (soundStream) {
                await soundStream.write(resp.audio);
            }
            if (outFile) {
                outFile.write(Buffer.from(resp.audio));
            }
        }
    } catch (error) {
        if (error instanceof Error) {
            console.error(error.message);
        } else {
            console.error('An unknown error occurred');
        }
    } finally {
        if (outFile) {
            outFile.end();
        }
        if (soundStream) {
            soundStream.close();
        }
    }
}

if (require.main === module) {
    main().catch(console.error);
}
