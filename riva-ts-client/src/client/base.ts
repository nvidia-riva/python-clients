import * as grpc from '@grpc/grpc-js';
import { Auth, AuthOptions } from './auth/index';
import { RivaConfig } from './types';
import { Logger, createLogger, format, transports } from 'winston';

export abstract class BaseClient {
    protected readonly auth: Auth;
    protected readonly channel: grpc.Channel;
    protected readonly logger: Logger;

    constructor(config: RivaConfig) {
        const authOptions: AuthOptions = {
            uri: config.serverUrl,
            useSsl: config.auth?.ssl || false,
            apiKey: config.auth?.apiKey,
            metadata: config.auth?.metadata,
            credentials: config.auth?.credentials,
            sslCert: config.auth?.sslCert
        };

        this.auth = new Auth(authOptions);
        this.channel = this.auth.createChannel();
        
        // Set up logging with winston
        this.logger = createLogger({
            level: config.logging?.level || 'info',
            format: config.logging?.format === 'json' ? format.json() : format.simple(),
            transports: [new transports.Console()]
        });
    }

    /**
     * Closes the gRPC channel
     */
    close(): Promise<void> {
        return new Promise<void>((resolve, reject) => {
            try {
                this.channel.close();
                resolve();
            } catch (err) {
                reject(err);
            }
        });
    }

    /**
     * Gets call metadata for gRPC requests
     */
    protected getCallMetadata(): grpc.Metadata {
        return this.auth.getCallMetadata();
    }

    /**
     * Creates gRPC deadline from timeout in milliseconds
     */
    protected createDeadline(timeoutMs?: number): Date | undefined {
        if (!timeoutMs) return undefined;
        return new Date(Date.now() + timeoutMs);
    }
}
