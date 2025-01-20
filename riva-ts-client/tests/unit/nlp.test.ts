import { describe, it, expect, vi, beforeEach } from 'vitest';
import { NLPService } from '../../src/client/nlp';
import { RivaError } from '../../src/client/errors';
import { createGrpcMock } from './helpers/grpc';
import type {
  ClassifyResponse,
  TokenClassifyResponse,
  TransformTextResponse,
  AnalyzeEntitiesResponse,
  AnalyzeIntentResponse,
  NaturalQueryResponse,
  AnalyzeIntentResponse_Slot
} from '../../src/proto/riva_nlp';
import { status } from '@grpc/grpc-js';
import type { ServiceError } from '@grpc/grpc-js';
import { Metadata } from '@grpc/grpc-js';

const mockClient = createGrpcMock([
  'Classify',
  'TokenClassify',
  'TransformText',
  'AnalyzeEntities',
  'AnalyzeIntent',
  'NaturalQuery'
]);

// Mock dependencies
vi.mock('@grpc/grpc-js', async () => {
  const actual = await vi.importActual('@grpc/grpc-js');
  return {
    ...actual,
    credentials: {
      createInsecure: vi.fn(),
      createFromMetadataGenerator: vi.fn()
    },
    Metadata: vi.fn(),
    Channel: vi.fn().mockImplementation(() => ({
      getTarget: vi.fn(),
      close: vi.fn(),
      getConnectivityState: vi.fn(),
      watchConnectivityState: vi.fn()
    }))
  };
});

// Mock getProtoClient
vi.mock('../../src/client/utils/proto', () => ({
  getProtoClient: vi.fn().mockReturnValue({
    RivaNLPServiceClient: vi.fn().mockImplementation(() => mockClient)
  })
}));

describe('NLPService', () => {
  let service: NLPService;
  const mockConfig = {
    serverUrl: 'localhost:50051',
    auth: {
      credentials: {}
    }
  };

  beforeEach(() => {
    vi.clearAllMocks();
    service = new NLPService(mockConfig);
  });

  describe('classifyText', () => {
    it('should classify text with correct parameters', async () => {
      const mockResponse: ClassifyResponse = {
        results: [{
          label: 'test',
          score: 0.9
        }]
      };

      mockClient.Classify.mockResolvedValue(mockResponse);

      const result = await service.classifyText('test text', 'test-model');
      expect(result).toEqual(mockResponse);
      expect(mockClient.Classify).toHaveBeenCalledWith({
        text: ['test text'],
        model: { modelName: 'test-model', languageCode: 'en-US' }
      });
    });

    it('should handle gRPC errors properly', async () => {
      const mockError = new Error('UNAVAILABLE: Server is currently unavailable') as ServiceError;
      mockError.code = status.UNAVAILABLE;
      mockError.details = 'Server is down for maintenance';
      mockError.metadata = new Metadata();

      mockClient.Classify.mockRejectedValue(mockError);

      await expect(service.classifyText('test text', 'test-model')).rejects.toThrow(RivaError);
      await expect(service.classifyText('test text', 'test-model')).rejects.toThrow('UNAVAILABLE: Server is currently unavailable');
    });
  });

  describe('classifyTokens', () => {
    it('should classify tokens with correct parameters', async () => {
      const mockResponse: TokenClassifyResponse = {
        results: [{
          tokens: [{
            text: 'token1',
            label: 'label1',
            score: 0.9,
            start: 0,
            end: 6
          }]
        }]
      };

      mockClient.TokenClassify.mockResolvedValue(mockResponse);

      const result = await service.classifyTokens('test text', 'test-model');
      expect(result).toEqual(mockResponse);
      expect(mockClient.TokenClassify).toHaveBeenCalledWith({
        text: ['test text'],
        model: { modelName: 'test-model', languageCode: 'en-US' }
      });
    });

    it('should handle gRPC errors properly', async () => {
      const mockError = new Error('UNAVAILABLE: Server is currently unavailable') as ServiceError;
      mockError.code = status.UNAVAILABLE;
      mockError.details = 'Server is down for maintenance';
      mockError.metadata = new Metadata();

      mockClient.TokenClassify.mockRejectedValue(mockError);

      await expect(service.classifyTokens('test text', 'test-model')).rejects.toThrow(RivaError);
      await expect(service.classifyTokens('test text', 'test-model')).rejects.toThrow('UNAVAILABLE: Server is currently unavailable');
    });
  });

  describe('transformText', () => {
    it('should transform text with correct parameters', async () => {
      const mockResponse: TransformTextResponse = {
        text: 'transformed text'
      };

      mockClient.TransformText.mockResolvedValue(mockResponse);

      const result = await service.transformText('test text', 'test-model');
      expect(result).toEqual(mockResponse);
      expect(mockClient.TransformText).toHaveBeenCalledWith({
        text: 'test text',
        model: 'test-model'
      });
    });

    it('should handle gRPC errors properly', async () => {
      const mockError = new Error('UNAVAILABLE: Server is currently unavailable') as ServiceError;
      mockError.code = status.UNAVAILABLE;
      mockError.details = 'Server is down for maintenance';
      mockError.metadata = new Metadata();

      mockClient.TransformText.mockRejectedValue(mockError);

      await expect(service.transformText('test text', 'test-model')).rejects.toThrow(RivaError);
      await expect(service.transformText('test text', 'test-model')).rejects.toThrow('UNAVAILABLE: Server is currently unavailable');
    });
  });

  describe('punctuateText', () => {
    it('should punctuate text with correct parameters', async () => {
      const mockResponse: TransformTextResponse = {
        text: 'punctuated text'
      };

      mockClient.TransformText.mockResolvedValue(mockResponse);

      const result = await service.punctuateText('test text', 'test-model');
      expect(result).toEqual(mockResponse);
      expect(mockClient.TransformText).toHaveBeenCalledWith({
        text: 'test text',
        model: 'test-model'
      });
    });

    it('should handle gRPC errors properly', async () => {
      const mockError = new Error('UNAVAILABLE: Server is currently unavailable') as ServiceError;
      mockError.code = status.UNAVAILABLE;
      mockError.details = 'Server is down for maintenance';
      mockError.metadata = new Metadata();

      mockClient.TransformText.mockRejectedValue(mockError);

      await expect(service.punctuateText('test text', 'test-model')).rejects.toThrow(RivaError);
      await expect(service.punctuateText('test text', 'test-model')).rejects.toThrow('UNAVAILABLE: Server is currently unavailable');
    });
  });

  describe('analyzeEntities', () => {
    it('should analyze entities with correct parameters', async () => {
      const mockResponse: AnalyzeEntitiesResponse = {
        entities: [{
          text: 'test',
          type: 'test',
          score: 0.9,
          start: 0,
          end: 4
        }]
      };

      mockClient.AnalyzeEntities.mockResolvedValue(mockResponse);

      const result = await service.analyzeEntities('test text', 'test-model');
      expect(result).toEqual(mockResponse);
      expect(mockClient.AnalyzeEntities).toHaveBeenCalledWith({
        text: 'test text'
      });
    });

    it('should handle gRPC errors properly', async () => {
      const mockError = new Error('UNAVAILABLE: Server is currently unavailable') as ServiceError;
      mockError.code = status.UNAVAILABLE;
      mockError.details = 'Server is down for maintenance';
      mockError.metadata = new Metadata();

      mockClient.AnalyzeEntities.mockRejectedValue(mockError);

      await expect(service.analyzeEntities('test text', 'test-model')).rejects.toThrow(RivaError);
      await expect(service.analyzeEntities('test text', 'test-model')).rejects.toThrow('UNAVAILABLE: Server is currently unavailable');
    });
  });

  describe('analyzeIntent', () => {
    it('should analyze intent with correct parameters', async () => {
      const mockSlot: AnalyzeIntentResponse_Slot = {
        text: 'tomorrow',
        type: 'date',
        score: 0.9
      };
      const mockResponse = {
        intent: 'set_alarm',
        confidence: 0.95,
        slots: [mockSlot]
      };

      mockClient.AnalyzeIntent.mockResolvedValue(mockResponse);

      const result = await service.analyzeIntent('test text', 'test-model');
      expect(result).toEqual(mockResponse);
      expect(mockClient.AnalyzeIntent).toHaveBeenCalledWith({
        text: 'test text'
      });
    });

    it('should handle gRPC errors properly', async () => {
      const mockError = new Error('UNAVAILABLE: Server is currently unavailable') as ServiceError;
      mockError.code = status.UNAVAILABLE;
      mockError.details = 'Server is down for maintenance';
      mockError.metadata = new Metadata();

      mockClient.AnalyzeIntent.mockRejectedValue(mockError);

      await expect(service.analyzeIntent('test text', 'test-model')).rejects.toThrow(RivaError);
      await expect(service.analyzeIntent('test text', 'test-model')).rejects.toThrow('UNAVAILABLE: Server is currently unavailable');
    });
  });

  describe('naturalQuery', () => {
    it('should process natural query with correct parameters', async () => {
      const mockResponse: NaturalQueryResponse = {
        response: 'test answer',
        confidence: 0.9
      };

      mockClient.NaturalQuery.mockResolvedValue(mockResponse);

      const result = await service.naturalQuery('test question', 'test context');
      expect(result).toEqual(mockResponse);
      expect(mockClient.NaturalQuery).toHaveBeenCalledWith({
        query: 'test question',
        context: 'test context'
      });
    });

    it('should handle gRPC errors properly', async () => {
      const mockError = new Error('UNAVAILABLE: Server is currently unavailable') as ServiceError;
      mockError.code = status.UNAVAILABLE;
      mockError.details = 'Server is down for maintenance';
      mockError.metadata = new Metadata();

      mockClient.NaturalQuery.mockRejectedValue(mockError);

      await expect(service.naturalQuery('test question', 'test context')).rejects.toThrow(RivaError);
      await expect(service.naturalQuery('test question', 'test context')).rejects.toThrow('UNAVAILABLE: Server is currently unavailable');
    });
  });
});
