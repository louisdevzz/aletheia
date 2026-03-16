import { VectorIndex } from "../storage/vector-index.js";
import { BM25Index } from "../storage/bm25-index.js";
import { SQLiteStore } from "../storage/sqlite-store.js";
import { SearchCache } from "../cache/search-cache.js";
import { Reranker } from "./reranker.js";
import type { SearchResult } from "./retrieval.js";

export class FastRetrieval {
  private readonly cache: SearchCache | null;
  private readonly vectorIndex: VectorIndex;
  private readonly bm25Index: BM25Index;
  private readonly sentenceStore: SQLiteStore;
  private readonly reranker: Reranker | null;

  private stats = { cacheHits: 0, cacheMisses: 0, avgLatencyMs: 0 };

  constructor(useCache = true, useReranker = true) {
    this.cache = useCache ? new SearchCache() : null;
    this.vectorIndex = new VectorIndex();
    this.bm25Index = new BM25Index();
    this.sentenceStore = new SQLiteStore();
    this.reranker = useReranker ? new Reranker() : null;
  }

  async search(
    query: string,
    topK = 5,
    alpha = 0.5,
    filterDocId?: string,
    useCumulative = false,
  ): Promise<SearchResult[]> {
    const startTime = performance.now();
    const filters = filterDocId ? { doc_id: filterDocId } : {};

    // 1. Check cache
    if (this.cache) {
      const cached = this.cache.get(query, filters);
      if (cached) {
        this.stats.cacheHits++;
        return (cached as unknown as SearchResult[]).slice(0, topK);
      }
      this.stats.cacheMisses++;
    }

    // 2. Parallel Vector + BM25 search
    const fetchK = Math.max(topK * 4, 20);

    const [vectorResults, bm25Results] = await Promise.allSettled([
      this.vectorIndex.search(query, fetchK, filterDocId),
      this.bm25Index.search(query, fetchK, filterDocId),
    ]);

    const vectorHits = vectorResults.status === "fulfilled" ? vectorResults.value : [];
    const bm25Hits = bm25Results.status === "fulfilled" ? bm25Results.value : [];

    if (vectorResults.status === "rejected") console.error("[fast-retrieval] Vector search error:", vectorResults.reason);
    if (bm25Results.status === "rejected") console.error("[fast-retrieval] BM25 search error:", bm25Results.reason);

    // 3. Score fusion
    const fused = this.fuseScores(vectorHits, bm25Hits, alpha);

    // 4. Batch fetch context
    const candidateIds = fused.slice(0, fetchK).map((r) => r.sentence_id);

    if (useCumulative) {
      const contexts = this.sentenceStore.getParagraphContextBatch(candidateIds);
      for (const result of fused.slice(0, fetchK)) {
        const ctx = contexts[result.sentence_id] ?? [];
        result.text = ctx.map((s) => s.text).join(" ");
      }
    } else {
      const sentences = this.sentenceStore.getSentencesByIdsBatch(candidateIds);
      for (const result of fused.slice(0, fetchK)) {
        const sentence = sentences[result.sentence_id];
        result.text = sentence?.text ?? "";
      }
    }

    // 5. Reranking
    let reranked: SearchResult[];
    if (this.reranker && fused.length > 0) {
      const candidates = fused.slice(0, Math.min(20, fused.length));
      reranked = await this.reranker.rerank(query, candidates, topK);
    } else {
      reranked = fused.slice(0, topK);
    }

    // 6. Cache results
    if (this.cache) {
      this.cache.set(query, filters, reranked as unknown as Record<string, unknown>[]);
    }

    // Update stats
    const latencyMs = performance.now() - startTime;
    this.updateLatencyStats(latencyMs);

    return reranked;
  }

  private fuseScores(
    vectorResults: { sentence_id: string; score: number; metadata: Record<string, unknown> }[],
    bm25Results: { sentence_id: string; score: number; metadata: Record<string, unknown> }[],
    alpha: number,
  ): SearchResult[] {
    const combined = new Map<string, SearchResult>();

    if (vectorResults.length > 0) {
      const maxVector = Math.max(...vectorResults.map((r) => r.score));
      for (const r of vectorResults) {
        const normalized = maxVector > 0 ? r.score / maxVector : 0;
        const existing = combined.get(r.sentence_id);
        combined.set(r.sentence_id, {
          sentence_id: r.sentence_id,
          text: "",
          score: (existing?.score ?? 0) + alpha * normalized,
          metadata: r.metadata,
        });
      }
    }

    if (bm25Results.length > 0) {
      const maxBm25 = Math.max(...bm25Results.map((r) => r.score));
      for (const r of bm25Results) {
        const normalized = maxBm25 > 0 ? r.score / maxBm25 : 0;
        const existing = combined.get(r.sentence_id);
        combined.set(r.sentence_id, {
          sentence_id: r.sentence_id,
          text: existing?.text ?? "",
          score: (existing?.score ?? 0) + (1 - alpha) * normalized,
          metadata: existing?.metadata ?? r.metadata,
        });
      }
    }

    return [...combined.values()].sort((a, b) => b.score - a.score);
  }

  private updateLatencyStats(latencyMs: number): void {
    const n = this.stats.cacheHits + this.stats.cacheMisses;
    if (n > 0) {
      this.stats.avgLatencyMs = (this.stats.avgLatencyMs * (n - 1) + latencyMs) / n;
    }
  }

  getStats(): { cacheHits: number; cacheMisses: number; cacheHitRate: string; avgLatencyMs: string } {
    const total = this.stats.cacheHits + this.stats.cacheMisses;
    const hitRate = total > 0 ? this.stats.cacheHits / total : 0;
    return {
      cacheHits: this.stats.cacheHits,
      cacheMisses: this.stats.cacheMisses,
      cacheHitRate: `${(hitRate * 100).toFixed(1)}%`,
      avgLatencyMs: this.stats.avgLatencyMs.toFixed(1),
    };
  }

  clearCache(): void {
    this.cache?.clear();
  }
}
