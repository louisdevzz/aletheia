import { Database } from "bun:sqlite";
import { createHash } from "crypto";
import { join } from "path";
import { mkdirSync, existsSync, statSync } from "fs";
import { getWorkspaceDir } from "../../config/settings.js";

export class SearchCache {
  private static readonly DEFAULT_TTL_SECONDS = 3600; // 1 hour

  private readonly db: Database;
  private readonly ttlSeconds: number;
  private readonly dbPath: string;

  constructor(ttlSeconds?: number) {
    this.ttlSeconds = ttlSeconds ?? SearchCache.DEFAULT_TTL_SECONDS;
    this.dbPath = this.getDbPath();
    this.db = new Database(this.dbPath);
    this.db.exec("PRAGMA journal_mode = WAL");
    this.initDb();
  }

  private getDbPath(): string {
    const workspace = getWorkspaceDir();
    const cacheDir = join(workspace, "cache");
    if (!existsSync(cacheDir)) {
      mkdirSync(cacheDir, { recursive: true });
    }
    return join(cacheDir, "search_cache.db");
  }

  private initDb(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS search_cache (
        key TEXT PRIMARY KEY,
        query_hash TEXT,
        filters_hash TEXT,
        results TEXT,
        created_at REAL,
        ttl_seconds INTEGER,
        access_count INTEGER DEFAULT 0,
        last_accessed REAL
      )
    `);

    this.db.exec(`CREATE INDEX IF NOT EXISTS idx_created_at ON search_cache(created_at)`);
  }

  private makeKey(query: string, filters: Record<string, unknown>): string {
    const normalized = query.toLowerCase().trim();
    const filterStr = JSON.stringify(filters, Object.keys(filters).sort());
    const combined = `${normalized}:${filterStr}`;
    return createHash("sha256").update(combined).digest("hex");
  }

  get(query: string, filters?: Record<string, unknown>): Record<string, unknown>[] | null {
    const key = this.makeKey(query, filters ?? {});

    const row = this.db.prepare(
      "SELECT results, created_at, ttl_seconds FROM search_cache WHERE key = ?"
    ).get(key) as { results: string; created_at: number; ttl_seconds: number } | null;

    if (!row) return null;

    // Check TTL
    const now = Date.now() / 1000;
    if (now - row.created_at > row.ttl_seconds) {
      this.db.prepare("DELETE FROM search_cache WHERE key = ?").run(key);
      return null;
    }

    // Update access stats
    this.db.prepare(
      "UPDATE search_cache SET access_count = access_count + 1, last_accessed = ? WHERE key = ?"
    ).run(now, key);

    return JSON.parse(row.results);
  }

  set(query: string, filters: Record<string, unknown>, results: Record<string, unknown>[], ttlSeconds?: number): void {
    const key = this.makeKey(query, filters);
    const ttl = ttlSeconds ?? this.ttlSeconds;
    const now = Date.now() / 1000;

    this.db.prepare(`
      INSERT OR REPLACE INTO search_cache
      (key, query_hash, filters_hash, results, created_at, ttl_seconds, last_accessed)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(
      key,
      createHash("sha256").update(query).digest("hex").slice(0, 16),
      createHash("sha256").update(JSON.stringify(filters)).digest("hex").slice(0, 16),
      JSON.stringify(results),
      now,
      ttl,
      now,
    );
  }

  invalidate(query: string, filters?: Record<string, unknown>): void {
    const key = this.makeKey(query, filters ?? {});
    this.db.prepare("DELETE FROM search_cache WHERE key = ?").run(key);
  }

  invalidateByDocId(docId: string): void {
    // Delete cache entries where results contain this doc_id
    this.db.prepare(
      "DELETE FROM search_cache WHERE results LIKE ?"
    ).run(`%${docId}%`);
  }

  clear(): void {
    this.db.exec("DELETE FROM search_cache");
  }

  cleanupExpired(): void {
    const now = Date.now() / 1000;
    this.db.prepare(
      "DELETE FROM search_cache WHERE (created_at + ttl_seconds) < ?"
    ).run(now);
  }

  getStats(): { total_entries: number; expired_entries: number; total_cache_hits: number; db_size_mb: number } {
    const total = (this.db.prepare("SELECT COUNT(*) as count FROM search_cache").get() as { count: number }).count;
    const now = Date.now() / 1000;
    const expired = (this.db.prepare("SELECT COUNT(*) as count FROM search_cache WHERE (created_at + ttl_seconds) < ?").get(now) as { count: number }).count;
    const totalHits = (this.db.prepare("SELECT COALESCE(SUM(access_count), 0) as total FROM search_cache").get() as { total: number }).total;

    let dbSizeMb = 0;
    try {
      dbSizeMb = statSync(this.dbPath).size / (1024 * 1024);
    } catch {
      // File may not exist yet
    }

    return { total_entries: total, expired_entries: expired, total_cache_hits: totalHits, db_size_mb: dbSizeMb };
  }

  close(): void {
    this.db.close();
  }
}
