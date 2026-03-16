import { homedir } from "os";
import { join } from "path";
import { mkdirSync, existsSync } from "fs";

export function getWorkspaceDir(): string {
  const workspace = join(homedir(), ".aletheia");
  if (!existsSync(workspace)) {
    mkdirSync(workspace, { recursive: true });
  }
  return workspace;
}

export interface MilvusConfig {
  readonly uri: string;
  readonly token: string;
  readonly host: string;
  readonly port: number;
}

export function getMilvusConfig(): MilvusConfig {
  return {
    uri: Bun.env.MILVUS_URI ?? "http://localhost:19530",
    token: Bun.env.MILVUS_TOKEN ?? "",
    host: Bun.env.MILVUS_HOST ?? "localhost",
    port: parseInt(Bun.env.MILVUS_PORT ?? "19530", 10),
  };
}

export function getMilvusConnectionParams(config: MilvusConfig): { address: string; token?: string } {
  if (config.token) {
    return { address: config.uri, token: config.token };
  }
  return { address: `${config.host}:${config.port}` };
}

export interface ElasticsearchConfig {
  readonly url: string;
  readonly apiKey: string;
  readonly host: string;
  readonly port: number;
}

export function getElasticsearchConfig(): ElasticsearchConfig {
  return {
    url: Bun.env.ELASTICSEARCH_URL ?? "http://localhost:9200",
    apiKey: Bun.env.ELASTIC_API_KEY ?? "",
    host: Bun.env.ELASTICSEARCH_HOST ?? "localhost",
    port: parseInt(Bun.env.ELASTICSEARCH_PORT ?? "9200", 10),
  };
}

export function getElasticsearchConnectionParams(config: ElasticsearchConfig): { node: string; auth?: { apiKey: string } } {
  if (config.apiKey) {
    return { node: config.url, auth: { apiKey: config.apiKey } };
  }
  return { node: `http://${config.host}:${config.port}` };
}

export interface EmbeddingConfig {
  readonly provider: string;
  readonly model: string;
  readonly dimension: number;
  readonly openaiApiKey: string;
  readonly ollamaBaseUrl: string;
}

export function getEmbeddingConfig(): EmbeddingConfig {
  return {
    provider: Bun.env.EMBEDDING_PROVIDER ?? "ollama",
    model: Bun.env.EMBEDDING_MODEL ?? "mxbai-embed-large:335m",
    dimension: parseInt(Bun.env.EMBEDDING_DIMENSION ?? "1024", 10),
    openaiApiKey: Bun.env.OPENAI_API_KEY ?? "",
    ollamaBaseUrl: Bun.env.OLLAMA_BASE_URL ?? "http://localhost:11434/v1",
  };
}

export interface KimiConfig {
  readonly apiKey: string;
  readonly model: string;
  readonly baseUrl: string;
  readonly userAgent: string;
}

export function getKimiConfig(): KimiConfig {
  return {
    apiKey: Bun.env.KIMI_API_KEY ?? "",
    model: Bun.env.KIMI_MODEL ?? "kimi-coding",
    baseUrl: Bun.env.KIMI_BASE_URL ?? "https://api.kimi.com/coding/v1",
    userAgent: "KimiCLI/0.77",
  };
}

export interface RetrievalConfig {
  readonly topK: number;
  readonly batchSize: number;
  readonly maxRetries: number;
  readonly timeoutSeconds: number;
}

export function getRetrievalConfig(): RetrievalConfig {
  return {
    topK: parseInt(Bun.env.RETRIEVAL_TOP_K ?? "3", 10),
    batchSize: parseInt(Bun.env.BATCH_SIZE ?? "5", 10),
    maxRetries: parseInt(Bun.env.MAX_RETRIES ?? "3", 10),
    timeoutSeconds: parseInt(Bun.env.TIMEOUT_SECONDS ?? "30", 10),
  };
}

export interface StorageConfig {
  readonly dbPath: string;
}

export function getStorageConfig(): StorageConfig {
  const workspace = getWorkspaceDir();
  const dbDir = join(workspace, "database");
  if (!existsSync(dbDir)) {
    mkdirSync(dbDir, { recursive: true });
  }
  return { dbPath: join(dbDir, "aletheia.db") };
}

export interface CohereConfig {
  readonly apiKey: string;
}

export function getCohereConfig(): CohereConfig {
  return {
    apiKey: Bun.env.COHERE_API_KEY ?? "",
  };
}
