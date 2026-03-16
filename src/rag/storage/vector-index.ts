import { MilvusClient, DataType } from "@zilliz/milvus2-sdk-node";
import OpenAI from "openai";
import { getMilvusConfig, getEmbeddingConfig } from "../../config/settings.js";
import type { MilvusConfig, EmbeddingConfig } from "../../config/settings.js";

export interface VectorSearchResult {
  readonly sentence_id: string;
  readonly score: number;
  readonly metadata: {
    readonly doc_id: string;
    readonly page_num: number;
    readonly paragraph_id: string;
  };
}

async function withRetry<T>(fn: () => Promise<T>, maxAttempts = 5, baseDelay = 2000): Promise<T> {
  let lastError: unknown;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (e) {
      lastError = e;
      if (attempt < maxAttempts) {
        const delay = Math.min(baseDelay * Math.pow(2, attempt - 1), 20000);
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
  }
  throw lastError;
}

export class VectorIndex {
  private readonly client: MilvusClient;
  private readonly collectionName: string;
  private readonly dimension: number;
  private readonly embeddingModel: string;
  private readonly provider: string;
  private readonly openaiClient: OpenAI | null;
  private readonly ollamaBaseUrl: string;

  constructor(collectionName = "sentence_embeddings", uri?: string, token?: string) {
    this.collectionName = collectionName;

    const milvusConfig: MilvusConfig = getMilvusConfig();
    const embeddingConfig: EmbeddingConfig = getEmbeddingConfig();

    this.dimension = embeddingConfig.dimension;
    this.embeddingModel = embeddingConfig.model;
    this.provider = embeddingConfig.provider;
    this.ollamaBaseUrl = embeddingConfig.ollamaBaseUrl;

    if (this.provider === "openai") {
      this.openaiClient = new OpenAI({ apiKey: embeddingConfig.openaiApiKey });
    } else {
      this.openaiClient = null;
    }

    const resolvedUri = uri ?? milvusConfig.uri;
    const resolvedToken = token ?? milvusConfig.token;

    this.client = resolvedToken
      ? new MilvusClient({ address: resolvedUri, token: resolvedToken })
      : new MilvusClient({ address: resolvedUri });

    console.log(`[milvus] Connected to ${resolvedUri}`);
  }

  async createCollection(dropExisting = false): Promise<void> {
    if (dropExisting) {
      const exists = await this.client.hasCollection({ collection_name: this.collectionName });
      if (exists.value) {
        await this.client.dropCollection({ collection_name: this.collectionName });
        console.log(`[milvus] Dropped existing collection: ${this.collectionName}`);
      }
    }

    const exists = await this.client.hasCollection({ collection_name: this.collectionName });
    if (exists.value) {
      console.log(`[milvus] Collection already exists: ${this.collectionName}`);
      return;
    }

    await this.client.createCollection({
      collection_name: this.collectionName,
      fields: [
        { name: "id", data_type: DataType.VarChar, max_length: 200, is_primary_key: true },
        { name: "embedding", data_type: DataType.FloatVector, dim: this.dimension },
        { name: "doc_id", data_type: DataType.VarChar, max_length: 100 },
        { name: "page_num", data_type: DataType.Int64 },
        { name: "paragraph_id", data_type: DataType.VarChar, max_length: 100 },
        { name: "sentence_id", data_type: DataType.VarChar, max_length: 100 },
      ],
    });

    await this.client.createIndex({
      collection_name: this.collectionName,
      field_name: "embedding",
      index_type: "IVF_FLAT",
      metric_type: "COSINE",
      params: { nlist: 1024 },
    });

    console.log(`[milvus] Created collection: ${this.collectionName} with COSINE similarity`);
  }

  async generateEmbeddings(texts: readonly string[]): Promise<number[][]> {
    if (this.provider === "ollama") {
      return this.generateOllamaEmbeddings(texts);
    }
    return this.generateOpenAIEmbeddings(texts);
  }

  private async generateOpenAIEmbeddings(texts: readonly string[]): Promise<number[][]> {
    if (!this.openaiClient) throw new Error("OpenAI client not initialized");

    const response = await withRetry(() =>
      this.openaiClient!.embeddings.create({
        model: this.embeddingModel,
        input: texts as string[],
      })
    );

    return response.data.map((item) => item.embedding);
  }

  private async generateOllamaEmbeddings(texts: readonly string[]): Promise<number[][]> {
    return withRetry(async () => {
      const response = await fetch(`${this.ollamaBaseUrl.replace("/v1", "")}/api/embed`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: this.embeddingModel, input: texts }),
      });

      if (!response.ok) {
        throw new Error(`Ollama embedding failed: ${response.status} ${response.statusText}`);
      }

      const data = (await response.json()) as { embeddings: number[][] };
      return data.embeddings;
    });
  }

  async insertVectors(sentences: readonly { id: string; text: string; page_num: number; paragraph_id: string }[], docId: string): Promise<void> {
    if (sentences.length === 0) return;

    const texts = sentences.map((s) => s.text);
    const embeddings = await this.generateEmbeddings(texts);

    const data = sentences.map((sentence, i) => ({
      id: sentence.id,
      embedding: embeddings[i],
      doc_id: docId,
      page_num: sentence.page_num,
      paragraph_id: sentence.paragraph_id,
      sentence_id: sentence.id,
    }));

    await this.client.insert({ collection_name: this.collectionName, data });
    console.log(`[milvus] Inserted ${sentences.length} vectors`);
  }

  async search(query: string, topK = 5, filterDocId?: string, filterPageNum?: number): Promise<VectorSearchResult[]> {
    const queryEmbedding = (await this.generateEmbeddings([query]))[0];

    let filterExpr: string | undefined;
    if (filterDocId && filterPageNum !== undefined) {
      filterExpr = `doc_id == "${filterDocId}" && page_num == ${filterPageNum}`;
    } else if (filterDocId) {
      filterExpr = `doc_id == "${filterDocId}"`;
    } else if (filterPageNum !== undefined) {
      filterExpr = `page_num == ${filterPageNum}`;
    }

    const results = await this.client.search({
      collection_name: this.collectionName,
      data: [queryEmbedding],
      anns_field: "embedding",
      params: { nprobe: 10 },
      limit: topK,
      filter: filterExpr,
      output_fields: ["doc_id", "page_num", "paragraph_id", "sentence_id"],
    });

    return (results.results ?? []).map((hit: Record<string, unknown>) => ({
      sentence_id: (hit.sentence_id as string) ?? "",
      score: Number(hit.score ?? hit.distance ?? 0),
      metadata: {
        doc_id: (hit.doc_id as string) ?? "",
        page_num: Number(hit.page_num ?? 0),
        paragraph_id: (hit.paragraph_id as string) ?? "",
      },
    }));
  }

  async pageExists(docId: string, pageNum: number): Promise<boolean> {
    const filterExpr = `doc_id == "${docId}" && page_num == ${pageNum}`;
    const results = await this.client.query({
      collection_name: this.collectionName,
      filter: filterExpr,
      limit: 1,
      output_fields: ["sentence_id"],
    });
    return (results.data?.length ?? 0) > 0;
  }

  async deleteByDocId(docId: string): Promise<void> {
    await this.client.delete({
      collection_name: this.collectionName,
      filter: `doc_id == "${docId}"`,
    });
    console.log(`[milvus] Deleted vectors for doc_id: ${docId}`);
  }

  async close(): Promise<void> {
    await this.client.closeConnection();
    console.log("[milvus] Connection closed");
  }
}
