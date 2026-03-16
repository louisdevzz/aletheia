import { Database } from "bun:sqlite";
import { createHash } from "crypto";
import { existsSync, mkdirSync } from "fs";
import { join } from "path";
import { getWorkspaceDir, getEmbeddingConfig } from "../config/settings.js";
import type { EmbeddingConfig } from "../config/settings.js";
import type { Memory, MemoryEntry } from "./memory-loader.js";

export class SQLiteMemoryStore implements Memory {
  private readonly db: Database;
  private readonly embeddingConfig: EmbeddingConfig;

  constructor(dbPath?: string) {
    if (!dbPath) {
      const memoryDir = join(getWorkspaceDir(), "memory");
      if (!existsSync(memoryDir)) {
        mkdirSync(memoryDir, { recursive: true });
      }
      dbPath = join(memoryDir, "memory.db");
    }

    this.db = new Database(dbPath);
    this.db.exec("PRAGMA journal_mode = WAL");
    this.embeddingConfig = getEmbeddingConfig();
    this.initDb();
  }

  private initDb(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY,
        key TEXT NOT NULL,
        content TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        timestamp TEXT NOT NULL,
        session_id TEXT,
        embedding BLOB,
        metadata TEXT
      )
    `);
    this.db.exec("CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key)");
    this.db.exec("CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)");
    this.db.exec("CREATE INDEX IF NOT EXISTS idx_memories_session ON memories(session_id)");
    this.db.exec("CREATE INDEX IF NOT EXISTS idx_memories_timestamp ON memories(timestamp)");
  }

  async store(
    key: string,
    content: string,
    category = "general",
    sessionId?: string,
    metadata?: Record<string, unknown>,
  ): Promise<void> {
    const timestamp = new Date().toISOString();
    const memoryId = createHash("md5").update(`${key}:${timestamp}`).digest("hex");

    const embedding = await this.getEmbedding(`${key}: ${content}`);
    const metadataJson = metadata ? JSON.stringify(metadata) : null;

    this.db.run(
      `INSERT INTO memories (id, key, content, category, timestamp, session_id, embedding, metadata)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      [memoryId, key, content, category, timestamp, sessionId ?? null, embedding, metadataJson],
    );
  }

  async recall(query: string, limit = 5, sessionId?: string): Promise<readonly MemoryEntry[]> {
    const queryEmbedding = await this.getEmbedding(query);

    const fetchLimit = limit * 3;
    let rows: { id: string; key: string; content: string; category: string; timestamp: string; embedding: Buffer }[];

    if (sessionId) {
      rows = this.db
        .query(
          "SELECT id, key, content, category, timestamp, embedding FROM memories WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
        )
        .all(sessionId, fetchLimit) as typeof rows;
    } else {
      rows = this.db
        .query(
          "SELECT id, key, content, category, timestamp, embedding FROM memories ORDER BY timestamp DESC LIMIT ?",
        )
        .all(fetchLimit) as typeof rows;
    }

    const queryVec = new Float32Array(queryEmbedding.buffer, queryEmbedding.byteOffset, queryEmbedding.byteLength / 4);

    const scored: { entry: MemoryEntry; similarity: number }[] = [];
    for (const row of rows) {
      if (!row.embedding) continue;
      const memVec = new Float32Array(
        row.embedding.buffer,
        row.embedding.byteOffset,
        row.embedding.byteLength / 4,
      );
      const similarity = cosineSimilarity(queryVec, memVec);

      scored.push({
        entry: {
          id: row.id,
          key: row.key,
          content: row.content,
          category: row.category,
          timestamp: row.timestamp,
          score: similarity,
        },
        similarity,
      });
    }

    scored.sort((a, b) => b.similarity - a.similarity);
    return scored.slice(0, limit).map((s) => s.entry);
  }

  async getByCategory(category: string, limit = 10): Promise<readonly MemoryEntry[]> {
    const rows = this.db
      .query(
        "SELECT id, key, content, category, timestamp FROM memories WHERE category = ? ORDER BY timestamp DESC LIMIT ?",
      )
      .all(category, limit) as { id: string; key: string; content: string; category: string; timestamp: string }[];

    return rows.map((row) => ({
      id: row.id,
      key: row.key,
      content: row.content,
      category: row.category,
      timestamp: row.timestamp,
    }));
  }

  async deleteOldMemories(days = 30): Promise<number> {
    const cutoffDate = new Date(Date.now() - days * 24 * 3600 * 1000).toISOString();
    const result = this.db.run(
      "DELETE FROM memories WHERE timestamp < ? AND category != 'core'",
      [cutoffDate],
    );
    return result.changes;
  }

  async getStats(): Promise<Record<string, unknown>> {
    const total = (this.db.query("SELECT COUNT(*) as count FROM memories").get() as { count: number }).count;
    const categories = this.db
      .query("SELECT category, COUNT(*) as count FROM memories GROUP BY category")
      .all() as { category: string; count: number }[];
    const byCategory: Record<string, number> = {};
    for (const row of categories) {
      byCategory[row.category] = row.count;
    }

    const range = this.db
      .query("SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest FROM memories")
      .get() as { oldest: string | null; newest: string | null };

    return {
      total_memories: total,
      by_category: byCategory,
      oldest_memory: range.oldest,
      newest_memory: range.newest,
    };
  }

  private async getEmbedding(text: string): Promise<Buffer> {
    const { provider, model, ollamaBaseUrl, openaiApiKey } = this.embeddingConfig;
    const openaiBaseUrl = "https://api.openai.com/v1";

    if (provider === "ollama") {
      const resp = await fetch(`${ollamaBaseUrl}/api/embeddings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model, prompt: text }),
      });
      const data = (await resp.json()) as { embedding: number[] };
      return Buffer.from(new Float32Array(data.embedding).buffer);
    }

    // OpenAI-compatible
    const resp = await fetch(`${openaiBaseUrl}/embeddings`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${openaiApiKey}`,
      },
      body: JSON.stringify({ model, input: text }),
    });
    const data = (await resp.json()) as { data: { embedding: number[] }[] };
    return Buffer.from(new Float32Array(data.data[0].embedding).buffer);
  }

  close(): void {
    this.db.close();
  }
}

function cosineSimilarity(a: Float32Array, b: Float32Array): number {
  if (a.length !== b.length) return 0;

  let dot = 0;
  let normA = 0;
  let normB = 0;

  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }

  const denom = Math.sqrt(normA) * Math.sqrt(normB);
  return denom === 0 ? 0 : dot / denom;
}

let memoryStore: SQLiteMemoryStore | null = null;

export function getMemoryStore(): SQLiteMemoryStore {
  if (!memoryStore) {
    memoryStore = new SQLiteMemoryStore();
  }
  return memoryStore;
}
