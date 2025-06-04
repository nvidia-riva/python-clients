declare module 'mic' {
    interface MicOptions {
        rate?: string;
        channels?: string;
        debug?: boolean;
        exitOnSilence?: number;
        device?: string;
        endian?: 'big' | 'little';
        bitwidth?: string;
        encoding?: string;
        additionalParameters?: string[];
    }

    interface MicInstance {
        start(): void;
        stop(): void;
        pause(): void;
        resume(): void;
        getAudioStream(): NodeJS.ReadableStream;
    }

    function mic(options?: MicOptions): MicInstance;
    export = mic;
}
