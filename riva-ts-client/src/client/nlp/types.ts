import * as grpc from '@grpc/grpc-js';
import {
  ClassifyResponse,
  TokenClassifyResponse,
  TransformTextResponse,
  AnalyzeIntentResponse,
  NaturalQueryResponse
} from '../../proto/riva_nlp';

/**
 * Interface for the NLP service client that matches the Python implementation
 */
export interface NLPServiceClient extends grpc.Client {
  /**
   * Classifies text provided in inputStrings. For example, this method can be used for
   * intent classification.
   */
  classifyText(
    inputStrings: string | string[],
    modelName: string,
    languageCode?: string,
    future?: boolean
  ): Promise<ClassifyResponse>;

  /**
   * Classifies tokens in texts in inputStrings. Can be used for slot classification or NER.
   */
  classifyTokens(
    inputStrings: string | string[],
    modelName: string,
    languageCode?: string,
    future?: boolean
  ): Promise<TokenClassifyResponse>;

  /**
   * The behavior of the function is defined entirely by the underlying model and may be used for
   * tasks like translation, adding punctuation, augment the input directly, etc.
   */
  transformText(
    inputStrings: string | string[],
    modelName: string,
    languageCode?: string,
    future?: boolean
  ): Promise<TransformTextResponse>;

  /**
   * Takes text with no- or limited- punctuation and returns the same text with corrected punctuation and
   * capitalization.
   */
  punctuateText(
    inputStrings: string | string[],
    languageCode?: string,
    future?: boolean
  ): Promise<TransformTextResponse>;

  /**
   * Accepts an input string and returns all named entities within the text, as well as a category and likelihood.
   */
  analyzeEntities(
    inputString: string,
    languageCode?: string,
    future?: boolean
  ): Promise<TokenClassifyResponse>;

  /**
   * Accepts an input string and returns the most likely intent as well as slots relevant to that intent.
   */
  analyzeIntent(
    inputString: string,
    options?: any,
    future?: boolean
  ): Promise<AnalyzeIntentResponse>;

  /**
   * A search function that enables querying one or more documents or contexts with a query that is written in
   * natural language.
   */
  naturalQuery(
    query: string,
    context: string,
    topN?: number,
    future?: boolean
  ): Promise<NaturalQueryResponse>;
}

// Utility functions for result extraction
export function extractAllTextClassesAndConfidences(
    response: any
): [string[][], number[][]] {
    const textClasses: string[][] = [];
    const confidences: number[][] = [];
    
    for (const result of response.results) {
        textClasses.push(result.labels.map((lbl: any) => lbl.className));
        confidences.push(result.labels.map((lbl: any) => lbl.score));
    }
    
    return [textClasses, confidences];
}

export function extractMostProbableTextClassAndConfidence(
    response: any
): [string[], number[]] {
    const [intents, confidences] = extractAllTextClassesAndConfidences(response);
    return [intents.map(x => x[0]), confidences.map(x => x[0])];
}

export function extractAllTokenClassificationPredictions(
    response: any
): [string[][], string[][][], number[][][], number[][][], number[][][]] {
    const tokens: string[][] = [];
    const tokenClasses: string[][][] = [];
    const confidences: number[][][] = [];
    const starts: number[][][] = [];
    const ends: number[][][] = [];

    for (const batchResult of response.results) {
        const elemTokens: string[] = [];
        const elemTokenClasses: string[][] = [];
        const elemConfidences: number[][] = [];
        const elemStarts: number[][] = [];
        const elemEnds: number[][] = [];

        for (const result of batchResult.results) {
            elemTokens.push(result.token);
            elemTokenClasses.push(result.label.map((lbl: any) => lbl.className));
            elemConfidences.push(result.label.map((lbl: any) => lbl.score));
            elemStarts.push(result.span.map((span: any) => span.start));
            elemEnds.push(result.span.map((span: any) => span.end));
        }

        tokens.push(elemTokens);
        tokenClasses.push(elemTokenClasses);
        confidences.push(elemConfidences);
        starts.push(elemStarts);
        ends.push(elemEnds);
    }

    return [tokens, tokenClasses, confidences, starts, ends];
}

export function extractMostProbableTokenClassificationPredictions(
    response: any
): [string[][], string[][], number[][], number[][], number[][]] {
    const [tokens, tokenClasses, confidences, starts, ends] = extractAllTokenClassificationPredictions(response);
    return [
        tokens,
        tokenClasses.map(x => x.map(xx => xx[0])),
        confidences.map(x => x.map(xx => xx[0])),
        starts.map(x => x.map(xx => xx[0])),
        ends.map(x => x.map(xx => xx[0]))
    ];
}

export function extractAllTransformedTexts(response: any): string[] {
    return response.text;
}

export function extractMostProbableTransformedText(response: any): string {
    return response.text[0];
}

export function prepareTransformTextRequest(
    inputStrings: string | string[],
    modelName: string,
    languageCode: string = 'en-US'
): any {
    const texts = Array.isArray(inputStrings) ? inputStrings : [inputStrings];
    return {
        text: texts,
        model: {
            modelName,
            languageCode
        }
    };
}
