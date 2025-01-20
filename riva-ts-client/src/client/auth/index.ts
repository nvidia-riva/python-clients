import * as grpc from '@grpc/grpc-js';
import { readFileSync } from 'fs';
import { resolve } from 'path';

export interface AuthOptions {
    uri?: string;
    useSsl?: boolean;
    sslCert?: string;
    credentials?: grpc.ChannelCredentials;
    metadata?: Array<[string, string]>;
    apiKey?: string;
    channelOptions?: grpc.ChannelOptions;
}

/**
 * Creates a gRPC channel with the specified authentication settings
 */
function createChannel(
    sslCert?: string,
    useSsl: boolean = false,
    uri: string = 'localhost:50051',
    metadata?: Array<[string, string]>,
    channelOptions: grpc.ChannelOptions = {}
): grpc.Channel {
    const metadataCallback = (_params: any, callback: Function) => {
        const grpcMetadata = new grpc.Metadata();
        if (metadata) {
            for (const [key, value] of metadata) {
                grpcMetadata.add(key, value);
            }
        }
        callback(null, grpcMetadata);
    };

    if (sslCert || useSsl) {
        let rootCertificates: Buffer | null = null;
        if (sslCert) {
            const certPath = resolve(sslCert);
            rootCertificates = readFileSync(certPath);
        }

        let creds = grpc.credentials.createSsl(rootCertificates);
        if (metadata) {
            const callCreds = grpc.credentials.createFromMetadataGenerator(metadataCallback);
            creds = grpc.credentials.combineChannelCredentials(creds, callCreds);
        }
        return new grpc.Channel(uri, creds, channelOptions);
    }

    return new grpc.Channel(uri, grpc.credentials.createInsecure(), channelOptions);
}

export class Auth {
    private readonly uri: string;
    private readonly useSsl: boolean;
    private readonly sslCert: string | undefined;
    private readonly metadata: Array<[string, string]>;
    private readonly channelOptions: grpc.ChannelOptions;
    public readonly channel: grpc.Channel;

    constructor(options: AuthOptions);
    constructor(
        sslCert?: string,
        useSsl?: boolean,
        uri?: string,
        metadataArgs?: string[][]
    );
    constructor(
        optionsOrSslCert?: AuthOptions | string,
        useSsl: boolean = false,
        uri: string = 'localhost:50051',
        metadataArgs?: string[][]
    ) {
        if (typeof optionsOrSslCert === 'object') {
            // AuthOptions constructor
            const options = optionsOrSslCert;
            this.uri = options.uri || 'localhost:50051';
            this.useSsl = options.useSsl || false;
            this.sslCert = options.sslCert;
            this.channelOptions = options.channelOptions || {};
            
            // Combine provided metadata with API key if present
            this.metadata = [...(options.metadata || [])];
            if (options.apiKey) {
                this.metadata.push(['api-key', options.apiKey]);
            }
        } else {
            // Python-style constructor
            this.uri = uri;
            this.useSsl = useSsl;
            this.sslCert = optionsOrSslCert;
            this.channelOptions = {};
            this.metadata = [];

            if (metadataArgs) {
                for (const meta of metadataArgs) {
                    if (meta.length !== 2) {
                        throw new Error(`Metadata should have 2 parameters in "key" "value" pair. Received ${meta.length} parameters.`);
                    }
                    this.metadata.push([meta[0], meta[1]]);
                }
            }
        }

        this.channel = createChannel(
            this.sslCert,
            this.useSsl,
            this.uri,
            this.metadata,
            this.channelOptions
        );
    }

    /**
     * Gets metadata for gRPC calls
     */
    getCallMetadata(): grpc.Metadata {
        const metadata = new grpc.Metadata();
        for (const [key, value] of this.metadata) {
            metadata.add(key, value);
        }
        return metadata;
    }

    /**
     * Alias for getCallMetadata to maintain Python compatibility
     */
    getAuthMetadata(): Array<[string, string]> {
        return this.metadata;
    }

    /**
     * Creates a gRPC channel with the current settings
     * @deprecated Use the channel property instead
     */
    createChannel(): grpc.Channel {
        return this.channel;
    }
}
