

import * as fs from 'fs';
import * as readline from 'readline';
import { program } from 'commander';
import { Auth, NeuralMachineTranslationService } from '../../src/client';
import { addConnectionArgparseParameters } from '../utils/argparse';
import { TranslateRequest, TranslateResponse } from '../../src/client/nmt/types';

interface DNTPhraseMapping {
    phrase: string;
    replacement?: string;
}

function parseDNTPhrase(line: string): DNTPhraseMapping | null {
    line = line.trim();
    if (!line) return null;

    const parts = line.split('##').map(p => p.trim());
    if (parts[0]) {
        return {
            phrase: parts[0],
            replacement: parts[1]
        };
    }
    return null;
}

function readDntPhrasesFile(filePath: string): string[] {
    if (!filePath) return [];

    try {
        const content = fs.readFileSync(filePath, 'utf-8');
        return content
            .split('\n')
            .map(parseDNTPhrase)
            .filter((mapping): mapping is DNTPhraseMapping => mapping !== null)
            .map(mapping => mapping.phrase);
    } catch (error) {
        console.error('Error reading DNT phrases file:', error);
        return [];
    }
}

function formatTranslationResponse(response: TranslateResponse): string {
    if (response.translations && response.translations.length > 0) {
        const translation = response.translations[0];
        return `${translation.text} (confidence: ${translation.score.toFixed(2)})`;
    }
    return response.text;
}

async function interactive(
    nmtService: NeuralMachineTranslationService,
    config: {
        sourceLanguage: string;
        targetLanguage: string;
        model?: string;
        doNotTranslatePhrases?: string[];
    }
): Promise<void> {
    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout,
        terminal: true
    });

    console.log('\nEnter text to translate (press Ctrl+C to exit)\n');

    while (true) {
        try {
            const text = await new Promise<string>((resolve) => {
                rl.question('> ', resolve);
            });

            if (!text.trim()) {
                console.log('Please enter some text to translate.\n');
                continue;
            }

            const request: TranslateRequest = {
                text,
                sourceLanguage: config.sourceLanguage,
                targetLanguage: config.targetLanguage,
                model: config.model,
                doNotTranslatePhrases: config.doNotTranslatePhrases
            };

            const response = await nmtService.translate(request);
            console.log(`Translation: ${formatTranslationResponse(response)}\n`);
        } catch (error) {
            console.error('Translation error:', error instanceof Error ? error.message : 'Unknown error');
            console.log('Please try again.\n');
        }
    }
}

async function translateSingle(
    nmtService: NeuralMachineTranslationService,
    config: {
        text: string;
        sourceLanguage: string;
        targetLanguage: string;
        model?: string;
        doNotTranslatePhrases?: string[];
    }
): Promise<void> {
    try {
        const request: TranslateRequest = {
            text: config.text,
            sourceLanguage: config.sourceLanguage,
            targetLanguage: config.targetLanguage,
            model: config.model,
            doNotTranslatePhrases: config.doNotTranslatePhrases
        };

        const response = await nmtService.translate(request);
        console.log(`Translation: ${formatTranslationResponse(response)}`);
    } catch (error) {
        console.error('Translation error:', error instanceof Error ? error.message : 'Unknown error');
        process.exit(1);
    }
}

async function listSupportedLanguages(
    nmtService: NeuralMachineTranslationService,
    model?: string
): Promise<void> {
    try {
        const response = await nmtService.get_supported_language_pairs(model || '');
        console.log('\nSupported language pairs:');
        response.supportedLanguagePairs.forEach(pair => {
            console.log(`  ${pair.sourceLanguageCode} -> ${pair.targetLanguageCode}`);
        });
    } catch (error) {
        console.error('Error fetching supported languages:', error instanceof Error ? error.message : 'Unknown error');
        process.exit(1);
    }
}

async function main() {
    program
        .description('Neural Machine Translation (NMT) client for Riva')
        .option('--source-language <code>', 'Source language code', 'en-US')
        .option('--target-language <code>', 'Target language code', 'es-US')
        .option('--model <name>', 'Model name to use for translation')
        .option('--text <text>', 'Text to translate')
        .option('--interactive', 'Enable interactive mode')
        .option(
            '--dnt-file <file>',
            'Path to file containing "do not translate" phrases. Each line should contain a phrase, ' +
            'optionally followed by ## and a replacement'
        )
        .option('--list-languages', 'List supported language pairs for the specified model');

    addConnectionArgparseParameters(program);
    program.parse();

    const options = program.opts();
    
    if (!options.listLanguages && !options.interactive && !options.text) {
        console.error('Either --text, --interactive, or --list-languages must be specified');
        process.exit(1);
    }

    const nmtService = new NeuralMachineTranslationService({
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

    const config = {
        sourceLanguage: options.sourceLanguage,
        targetLanguage: options.targetLanguage,
        model: options.model,
        doNotTranslatePhrases: options.dntFile ? readDntPhrasesFile(options.dntFile) : undefined
    };

    if (options.listLanguages) {
        await listSupportedLanguages(nmtService, options.model);
    } else if (options.interactive) {
        await interactive(nmtService, config);
    } else if (options.text) {
        await translateSingle(nmtService, { ...config, text: options.text });
    }
}

if (require.main === module) {
    main().catch(error => {
        console.error('Fatal error:', error instanceof Error ? error.message : 'Unknown error');
        process.exit(1);
    });

    process.on('SIGINT', () => {
        console.log('\nExiting...');
        process.exit(0);
    });
}
