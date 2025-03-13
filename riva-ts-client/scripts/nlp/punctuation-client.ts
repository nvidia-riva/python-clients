import * as fs from 'fs';
import { program } from 'commander';
import { Auth, NLPService } from '../../src/client';
import { addConnectionArgparseParameters } from '../utils/argparse';
import * as readline from 'readline';

interface TestCase {
    input: string;
    expected: string;
}

const TEST_CASES: TestCase[] = [
    {
        input: 'can you prove that you are self aware',
        expected: 'Can you prove that you are self-aware?'
    },
    {
        input: 'hello how are you today',
        expected: 'Hello, how are you today?'
    },
    {
        input: 'i like pizza pasta and ice cream',
        expected: 'I like pizza, pasta, and ice cream.'
    },
    {
        input: 'what time is it',
        expected: 'What time is it?'
    },
    {
        input: 'my name is john and i live in new york',
        expected: 'My name is John and I live in New York.'
    }
];

async function runPunctCapit(
    nlpService: NLPService,
    query: string,
    modelName: string = 'punctuation',
    languageCode: string = 'en-US'
): Promise<string> {
    const start = Date.now();
    try {
        const response = await nlpService.punctuateText(query, modelName);
        const result = response.text;
        const timeTaken = (Date.now() - start) / 1000;
        console.log(`Time taken: ${timeTaken.toFixed(3)}s`);
        return result;
    } catch (error) {
        console.error('Error during punctuation:', error);
        throw error;
    }
}

async function runTests(nlpService: NLPService, modelName?: string, languageCode: string = 'en-US'): Promise<void> {
    console.log('Running tests...\n');
    let passed = 0;
    let failed = 0;

    for (const [index, testCase] of TEST_CASES.entries()) {
        console.log(`Test ${index + 1}:`);
        console.log(`Input: "${testCase.input}"`);
        console.log(`Expected: "${testCase.expected}"`);

        try {
            const result = await runPunctCapit(nlpService, testCase.input, modelName, languageCode);
            console.log(`Got: "${result}"`);

            if (result === testCase.expected) {
                console.log('✓ PASSED\n');
                passed++;
            } else {
                console.log('✗ FAILED\n');
                failed++;
            }
        } catch (error) {
            console.log('✗ FAILED (error occurred)\n');
            failed++;
        }
    }

    console.log(`Summary: ${passed} passed, ${failed} failed`);
}

async function interactive(nlpService: NLPService, modelName?: string, languageCode: string = 'en-US'): Promise<void> {
    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout
    });

    while (true) {
        try {
            const query = await new Promise<string>((resolve) => {
                rl.question('Enter a query (or Ctrl+C to exit): ', resolve);
            });

            const result = await runPunctCapit(nlpService, query, modelName, languageCode);
            console.log(`Result: "${result}"\n`);
        } catch (error) {
            console.error('Error occurred:', error);
        }
    }
}

async function main() {
    program
        .description('Client app to restore Punctuation and Capitalization with Riva')
        .option(
            '--model <name>',
            'Model on Riva Server to execute. If this parameter is missing, then the server will try to select a first available Punctuation & Capitalization model.'
        )
        .option('--query <text>', 'Input Query', 'can you prove that you are self aware')
        .option(
            '--run-tests',
            'Flag to run sanity tests. If this option is chosen, then options --query and --interactive are ignored and a model is run on several hardcoded examples.'
        )
        .option(
            '--interactive',
            'If this option is set, then --query argument is ignored and the script suggests user to enter queries to standard input.'
        )
        .option('--language-code <code>', 'Language code of the model to be used.', 'en-US')
        .option('--input-file <file>', 'Input file with text to punctuate')
        .option('--output-file <file>', 'Output file to write punctuated text');

    addConnectionArgparseParameters(program);

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

    const nlpService = new NLPService({
        serverUrl: options.server,
        auth
    });

    try {
        if (options.runTests) {
            await runTests(nlpService, options.model, options.languageCode);
        } else if (options.interactive) {
            await interactive(nlpService, options.model, options.languageCode);
        } else {
            let text = options.query;
            if (options.inputFile) {
                text = fs.readFileSync(options.inputFile, 'utf-8');
            }

            const result = await runPunctCapit(nlpService, text, options.model, options.languageCode);

            if (options.outputFile) {
                fs.writeFileSync(options.outputFile, result);
                console.log(`Punctuated text written to ${options.outputFile}`);
            } else {
                console.log(`Result: "${result}"`);
            }
        }
    } catch (error) {
        console.error('Error:', error);
        process.exit(1);
    }
}

if (require.main === module) {
    main().catch(console.error);

    process.on('SIGINT', () => {
        console.log('\nExiting...');
        process.exit(0);
    });
}
