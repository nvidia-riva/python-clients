import * as grpc from '@grpc/grpc-js';
import { BaseClient } from '../base';
import { handleGrpcError } from '../errors';
import { getProtoClient } from '../utils/proto';
import {
  ClassifyRequest,
  TokenClassifyRequest,
  AnalyzeEntitiesRequest,
  AnalyzeIntentRequest,
  AnalyzeIntentResponse,
  TransformTextRequest,
  ClassifyResponse,
  TokenClassifyResponse,
  TransformTextResponse,
  NaturalQueryRequest,
  NaturalQueryResponse,
  AnalyzeEntitiesResponse,
  RivaNLPServiceClientImpl
} from '../../proto/riva_nlp';

/**
 * Provides text classification, token classification, text transformation,
 * intent recognition, punctuation and capitalization restoring,
 * question answering services.
 */
export class NLPService extends BaseClient {
  private readonly client: RivaNLPServiceClientImpl;

  constructor(config: { serverUrl: string; auth?: any }) {
    super(config);
    const { RivaNLPServiceClient } = getProtoClient('riva_nlp');
    this.client = new RivaNLPServiceClient(
      config.serverUrl,
      config.auth?.credentials || grpc.credentials.createInsecure()
    );
  }

  /**
   * Classifies text provided in inputStrings. For example, this method can be used for
   * intent classification.
   */
  async classifyText(
    inputStrings: string | string[],
    modelName: string,
    languageCode: string = 'en-US',
    future: boolean = false
  ): Promise<ClassifyResponse> {
    try {
      const texts = Array.isArray(inputStrings) ? inputStrings : [inputStrings];
      const request: ClassifyRequest = {
        text: texts,
        model: {
          modelName,
          languageCode
        }
      };

      return await this.client.Classify(request);
    } catch (error) {
      if (error instanceof Error) {
        throw handleGrpcError(error);
      }
      throw new Error('Unknown error occurred');
    }
  }

  /**
   * Classifies tokens in the text provided in inputStrings. For example, this method can be used for
   * named entity recognition.
   */
  async classifyTokens(
    inputStrings: string | string[],
    modelName: string,
    languageCode: string = 'en-US',
    future: boolean = false
  ): Promise<TokenClassifyResponse> {
    try {
      const texts = Array.isArray(inputStrings) ? inputStrings : [inputStrings];
      const request: TokenClassifyRequest = {
        text: texts,
        model: {
          modelName,
          languageCode
        }
      };

      return await this.client.TokenClassify(request);
    } catch (error) {
      if (error instanceof Error) {
        throw handleGrpcError(error);
      }
      throw new Error('Unknown error occurred');
    }
  }

  /**
   * Transforms text provided in inputString. For example, this method can be used for
   * text normalization.
   */
  async transformText(
    inputString: string,
    modelName: string,
    future: boolean = false
  ): Promise<TransformTextResponse> {
    try {
      const request: TransformTextRequest = {
        text: inputString,
        model: modelName
      };

      return await this.client.TransformText(request);
    } catch (error) {
      if (error instanceof Error) {
        throw handleGrpcError(error);
      }
      throw new Error('Unknown error occurred');
    }
  }

  /**
   * Restores punctuation and capitalization in the text provided in inputString.
   */
  async punctuateText(
    inputString: string,
    modelName: string,
    future: boolean = false
  ): Promise<TransformTextResponse> {
    try {
      const request: TransformTextRequest = {
        text: inputString,
        model: modelName
      };

      return await this.client.TransformText(request);
    } catch (error) {
      if (error instanceof Error) {
        throw handleGrpcError(error);
      }
      throw new Error('Unknown error occurred');
    }
  }

  /**
   * Analyzes entities in the text provided in inputString.
   */
  async analyzeEntities(
    inputString: string,
    modelName: string,
    languageCode: string = 'en-US',
    future: boolean = false
  ): Promise<AnalyzeEntitiesResponse> {
    try {
      const request: AnalyzeEntitiesRequest = {
        text: inputString
      };

      return await this.client.AnalyzeEntities(request);
    } catch (error) {
      if (error instanceof Error) {
        throw handleGrpcError(error);
      }
      throw new Error('Unknown error occurred');
    }
  }

  /**
   * Analyzes intent in the text provided in inputString.
   */
  async analyzeIntent(
    inputString: string,
    modelName: string,
    languageCode: string = 'en-US',
    future: boolean = false
  ): Promise<AnalyzeIntentResponse> {
    try {
      const request: AnalyzeIntentRequest = {
        text: inputString
      };

      return await this.client.AnalyzeIntent(request);
    } catch (error) {
      if (error instanceof Error) {
        throw handleGrpcError(error);
      }
      throw new Error('Unknown error occurred');
    }
  }

  /**
   * Performs natural language query using the provided query and context.
   */
  async naturalQuery(
    query: string,
    context: string,
    future: boolean = false
  ): Promise<NaturalQueryResponse> {
    try {
      const request: NaturalQueryRequest = {
        query,
        context
      };

      return await this.client.NaturalQuery(request);
    } catch (error) {
      if (error instanceof Error) {
        throw handleGrpcError(error);
      }
      throw new Error('Unknown error occurred');
    }
  }
}
