import * as grpc from '@grpc/grpc-js';

export interface AuthConfig {
    /**
     * Whether to use SSL/TLS for the connection
     */
    ssl?: boolean;

    /**
     * Path to SSL certificate file
     */
    sslCert?: string;

    /**
     * API key for authentication
     */
    apiKey?: string;

    /**
     * SSL/TLS credentials
     */
    credentials?: grpc.ChannelCredentials;

    /**
     * Additional metadata to send with each request
     */
    metadata?: [string, string][];
}

export interface RivaConfig {
    /**
     * Riva server URL (e.g., 'localhost:50051')
     */
    serverUrl: string;

    /**
     * Authentication configuration
     */
    auth?: AuthConfig;

    /**
     * Logging configuration
     */
    logging?: {
        /**
         * Log level (default: 'info')
         */
        level?: string;

        /**
         * Log format ('simple' or 'json', default: 'simple')
         */
        format?: 'simple' | 'json';
    };
}
