import { Command } from 'commander';

export function addConnectionArgparseParameters(program: Command): Command {
    return program
        .option('--ssl-cert <path>', 'Path to SSL certificate file.')
        .option('--use-ssl', 'Use SSL/TLS connection to the server.')
        .option('--server <address>', 'Server address.', 'localhost:50051')
        .option('--metadata <metadata...>', 'Metadata to pass to gRPC. Example: key1=val1 key2=val2');
}
