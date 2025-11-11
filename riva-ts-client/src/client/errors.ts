import * as grpc from '@grpc/grpc-js';

export class RivaError extends Error {
    constructor(
        message: string,
        public readonly code?: grpc.status,
        public readonly details?: string
    ) {
        super(message);
        this.name = 'RivaError';
    }

    static fromGrpcError(error: Error & { code?: grpc.status; details?: string }): RivaError {
        return new RivaError(
            error.message,
            error.code,
            error.details
        );
    }
}

export class AuthenticationError extends RivaError {
    constructor(message: string, details?: string) {
        super(message, grpc.status.UNAUTHENTICATED, details);
        this.name = 'AuthenticationError';
    }
}

export class ConnectionError extends RivaError {
    constructor(message: string, details?: string) {
        super(message, grpc.status.UNAVAILABLE, details);
        this.name = 'ConnectionError';
    }
}

export class InvalidArgumentError extends RivaError {
    constructor(message: string, details?: string) {
        super(message, grpc.status.INVALID_ARGUMENT, details);
        this.name = 'InvalidArgumentError';
    }
}

export function handleGrpcError(error: Error & { code?: grpc.status }): never {
    switch (error.code) {
        case grpc.status.UNAUTHENTICATED:
            throw new AuthenticationError(error.message);
        case grpc.status.UNAVAILABLE:
            throw new ConnectionError(error.message);
        case grpc.status.INVALID_ARGUMENT:
            throw new InvalidArgumentError(error.message);
        default:
            throw RivaError.fromGrpcError(error);
    }
}
