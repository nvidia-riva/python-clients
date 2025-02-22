// Basic types for the Riva client
export interface RivaConfig {
    serverUrl: string;
    auth?: {
        ssl?: boolean;
        apiKey?: string;
    };
    logging?: {
        level: 'debug' | 'info' | 'warn' | 'error';
    };
}

export interface AudioConfig {
    sampleRateHz: number;
    encoding: 'LINEAR16' | 'FLAC' | 'MULAW' | 'ALAW';
    languageCode?: string;
}
