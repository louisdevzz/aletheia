import OpenAI from "openai";
import { getEmbeddingConfig } from "../../config/settings.js";

export class BatchEmbeddingClient {
  private readonly provider: string;
  private readonly model: string;
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly batchSize: number;

  constructor(
    provider?: string,
    model?: string,
    baseUrl?: string,
    apiKey?: string,
    batchSize = 32,
  ) {
    const config = getEmbeddingConfig();
    this.provider = provider ?? config.provider;
    this.model = model ?? config.model;
    this.baseUrl = baseUrl ?? config.ollamaBaseUrl;
    this.apiKey = apiKey ?? config.openaiApiKey;
    this.batchSize = batchSize;
  }

  async embedBatch(texts: readonly string[], batchSize?: number): Promise<number[][]> {
    const size = batchSize ?? this.batchSize;

    if (texts.length <= size) {
      return this.embedSingleBatch(texts);
    }

    const totalBatches = Math.ceil(texts.length / size);
    console.log(`[embeddings] Embedding ${texts.length} texts in ${totalBatches} batches...`);

    const results: number[][] = new Array(texts.length);
    const batchPromises: Promise<void>[] = [];

    for (let i = 0; i < texts.length; i += size) {
      const batchStart = i;
      const batch = texts.slice(i, i + size);

      batchPromises.push(
        this.embedSingleBatch(batch).then((embeddings) => {
          for (let j = 0; j < embeddings.length; j++) {
            results[batchStart + j] = embeddings[j];
          }
        }).catch((e) => {
          console.error(`[embeddings] Batch ${Math.floor(batchStart / size)} failed:`, e);
          for (let j = 0; j < batch.length; j++) {
            results[batchStart + j] = new Array(1024).fill(0);
          }
        })
      );
    }

    await Promise.all(batchPromises);
    return results;
  }

  private async embedSingleBatch(texts: readonly string[]): Promise<number[][]> {
    if (this.provider === "ollama") {
      return this.embedOllamaBatch(texts);
    }
    return this.embedOpenAIBatch(texts);
  }

  private async embedOllamaBatch(texts: readonly string[]): Promise<number[][]> {
    const ollamaUrl = this.baseUrl.replace("/v1", "");
    const response = await fetch(`${ollamaUrl}/api/embed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: this.model, input: texts }),
      signal: AbortSignal.timeout(120_000),
    });

    if (!response.ok) {
      throw new Error(`Ollama embedding failed: ${response.status}`);
    }

    const data = (await response.json()) as { embeddings: number[][] };
    return data.embeddings;
  }

  private async embedOpenAIBatch(texts: readonly string[]): Promise<number[][]> {
    const client = new OpenAI({ apiKey: this.apiKey });
    const response = await client.embeddings.create({
      model: this.model,
      input: texts as string[],
    });

    return response.data
      .sort((a, b) => a.index - b.index)
      .map((item) => item.embedding);
  }
}

export class EmbeddingCacheLayer {
  private readonly cache = new Map<string, number[]>();
  private readonly maxSize: number;

  constructor(maxSize = 10000) {
    this.maxSize = maxSize;
  }

  get(text: string): number[] | null {
    const hash = this.hashText(text);
    return this.cache.get(hash) ?? null;
  }

  set(text: string, embedding: number[]): void {
    if (this.cache.size >= this.maxSize) {
      // Evict oldest entry
      const firstKey = this.cache.keys().next().value;
      if (firstKey) this.cache.delete(firstKey);
    }
    const hash = this.hashText(text);
    this.cache.set(hash, embedding);
  }

  private hashText(text: string): string {
    const hasher = new Bun.CryptoHasher("md5");
    hasher.update(text);
    return hasher.digest("hex");
  }
}
