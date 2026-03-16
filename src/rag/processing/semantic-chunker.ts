import { BatchEmbeddingClient } from "./batch-embeddings.js";

export interface ChunkResult {
  readonly text: string;
  readonly startIdx: number;
  readonly endIdx: number;
  readonly sentences: readonly string[];
  readonly tokenCount: number;
}

function cosineSimilarity(a: number[], b: number[]): number {
  let dotProduct = 0;
  let normA = 0;
  let normB = 0;
  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  const denominator = Math.sqrt(normA) * Math.sqrt(normB);
  return denominator === 0 ? 0 : dotProduct / denominator;
}

function meanEmbedding(embeddings: number[][]): number[] {
  if (embeddings.length === 0) return [];
  const dim = embeddings[0].length;
  const result = new Array<number>(dim).fill(0);
  for (const emb of embeddings) {
    for (let i = 0; i < dim; i++) {
      result[i] += emb[i];
    }
  }
  for (let i = 0; i < dim; i++) {
    result[i] /= embeddings.length;
  }
  return result;
}

/** Regex-based sentence splitter (replaces nltk.sent_tokenize) */
function splitSentences(text: string): string[] {
  // Split on sentence-ending punctuation followed by whitespace or end of string
  const sentences = text.match(/[^.!?]+[.!?]+[\s]?|[^.!?]+$/g);
  if (!sentences) return [text];
  return sentences.map((s) => s.trim()).filter((s) => s.length > 0);
}

function estimateTokens(text: string): number {
  return Math.ceil(text.split(/\s+/).length * 1.3);
}

export class SemanticChunker {
  private readonly embeddingClient: BatchEmbeddingClient;
  private readonly similarityThreshold: number;
  private readonly maxTokens: number;
  private readonly overlapSentences: number;

  constructor(
    similarityThreshold = 0.7,
    maxTokens = 512,
    overlapSentences = 1,
  ) {
    this.embeddingClient = new BatchEmbeddingClient();
    this.similarityThreshold = similarityThreshold;
    this.maxTokens = maxTokens;
    this.overlapSentences = overlapSentences;
  }

  async chunk(text: string, maxTokens?: number): Promise<ChunkResult[]> {
    const limit = maxTokens ?? this.maxTokens;
    const sentences = splitSentences(text);

    if (sentences.length <= 1) {
      return [
        {
          text,
          startIdx: 0,
          endIdx: text.length,
          sentences,
          tokenCount: estimateTokens(text),
        },
      ];
    }

    // Get embeddings for all sentences
    const embeddings = await this.embeddingClient.embedBatch(sentences);

    const chunks: ChunkResult[] = [];
    let currentSentences: string[] = [sentences[0]];
    let currentEmbeddings: number[][] = [embeddings[0]];
    let currentTokenCount = estimateTokens(sentences[0]);

    for (let i = 1; i < sentences.length; i++) {
      const sentence = sentences[i];
      const embedding = embeddings[i];
      const sentenceTokens = estimateTokens(sentence);

      let shouldSplit = false;

      // Reason 1: Semantic shift
      if (currentEmbeddings.length > 0) {
        const avgEmb = meanEmbedding(currentEmbeddings);
        const similarity = cosineSimilarity(avgEmb, embedding);
        if (similarity < this.similarityThreshold) {
          shouldSplit = true;
        }
      }

      // Reason 2: Token limit
      if (currentTokenCount + sentenceTokens > limit) {
        shouldSplit = true;
      }

      if (shouldSplit && currentSentences.length > 0) {
        const chunkText = currentSentences.join(" ");
        chunks.push({
          text: chunkText,
          startIdx: text.indexOf(currentSentences[0]),
          endIdx: text.indexOf(currentSentences[currentSentences.length - 1]) + currentSentences[currentSentences.length - 1].length,
          sentences: [...currentSentences],
          tokenCount: currentTokenCount,
        });

        // Start new chunk with overlap
        const overlap = this.overlapSentences > 0
          ? currentSentences.slice(-this.overlapSentences)
          : [];
        const overlapEmbeddings = this.overlapSentences > 0
          ? currentEmbeddings.slice(-this.overlapSentences)
          : [];

        currentSentences = [...overlap, sentence];
        currentEmbeddings = [...overlapEmbeddings, embedding];
        currentTokenCount = currentSentences.reduce((sum, s) => sum + estimateTokens(s), 0);
      } else {
        currentSentences.push(sentence);
        currentEmbeddings.push(embedding);
        currentTokenCount += sentenceTokens;
      }
    }

    // Last chunk
    if (currentSentences.length > 0) {
      const chunkText = currentSentences.join(" ");
      chunks.push({
        text: chunkText,
        startIdx: text.indexOf(currentSentences[0]),
        endIdx: text.indexOf(currentSentences[currentSentences.length - 1]) + currentSentences[currentSentences.length - 1].length,
        sentences: currentSentences,
        tokenCount: currentTokenCount,
      });
    }

    return chunks;
  }
}

export { splitSentences, estimateTokens, cosineSimilarity };
