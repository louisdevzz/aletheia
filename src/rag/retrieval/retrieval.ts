import { VectorIndex } from "../storage/vector-index.js";
import type { VectorSearchResult } from "../storage/vector-index.js";
import { BM25Index } from "../storage/bm25-index.js";
import type { BM25SearchResult } from "../storage/bm25-index.js";
import { SQLiteStore } from "../storage/sqlite-store.js";
import { Reranker } from "./reranker.js";
import type { RerankCandidate } from "./reranker.js";
import { CumulativeSummarizer } from "./cumulative-summarizer.js";

export interface SearchResult {
  readonly sentence_id: string;
  text: string;
  score: number;
  metadata: Record<string, unknown>;
}

export class HybridRetrieval {
  private readonly vectorIndex: VectorIndex;
  private readonly bm25Index: BM25Index;
  private readonly sentenceStore: SQLiteStore;
  private readonly reranker: Reranker;

  constructor() {
    this.vectorIndex = new VectorIndex();
    this.bm25Index = new BM25Index();
    this.sentenceStore = new SQLiteStore();
    this.reranker = new Reranker();
  }

  async vectorSearch(query: string, topK = 10, filterDocId?: string): Promise<VectorSearchResult[]> {
    return this.vectorIndex.search(query, topK, filterDocId);
  }

  async bm25Search(query: string, topK = 10, filterDocId?: string): Promise<BM25SearchResult[]> {
    return this.bm25Index.search(query, topK, filterDocId);
  }

  async hybridSearch(
    query: string,
    topK = 3,
    alpha = 0.5,
    filterDocId?: string,
    rerankMethod: "weighted" | "rrf" = "weighted",
    useCumulativeContext = false,
    generator?: { client: { chat: { completions: { create: (...args: unknown[]) => Promise<unknown> } } }; model: string },
  ): Promise<SearchResult[]> {
    // Phase 1: Initial Retrieval
    const candidateK = Math.max(topK * 2, 10);
    const fetchK = candidateK * 2;

    const [vectorResults, bm25Results] = await Promise.all([
      this.vectorSearch(query, fetchK, filterDocId),
      this.bm25Search(query, fetchK, filterDocId),
    ]);

    // Score fusion
    const combinedScores = rerankMethod === "rrf"
      ? this.reciprocalRankFusion(vectorResults, bm25Results)
      : this.weightedFusion(vectorResults, bm25Results, alpha);

    // Rank and get top candidates
    const rankedIds = [...combinedScores.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, candidateK);

    if (rankedIds.length === 0) return [];

    // Phase 2: Context Expansion
    const candidates: RerankCandidate[] = [];

    for (const [sentenceId, score] of rankedIds) {
      const sentenceData = this.sentenceStore.getSentenceById(sentenceId);
      if (!sentenceData) continue;

      const window = this.sentenceStore.getParagraphContext(sentenceData.doc_id, sentenceData.paragraph_id);
      const paragraphText = window.map((s) => s.text).join(" ");

      candidates.push({
        sentence_id: sentenceId,
        text: paragraphText,
        score,
        metadata: {
          doc_id: sentenceData.doc_id,
          page_num: sentenceData.page_num,
          paragraph_id: sentenceData.paragraph_id,
          char_offset_start: sentenceData.char_offset_start,
          char_offset_end: sentenceData.char_offset_end,
          item_type: sentenceData.item_type ?? "paragraph",
        },
      });
    }

    // Phase 3: Reranking
    const reranked = candidates.length > 0
      ? await this.reranker.rerank(query, candidates, topK)
      : candidates.slice(0, topK);

    // Phase 4: Cumulative Context (optional)
    if (!useCumulativeContext || !generator) {
      return reranked;
    }

    const summarizer = new CumulativeSummarizer(generator);

    // Group by document
    const docGroups = new Map<string, SearchResult[]>();
    for (const result of reranked) {
      const docId = result.metadata.doc_id as string;
      const existing = docGroups.get(docId) ?? [];
      docGroups.set(docId, [...existing, result]);
    }

    const finalResults: SearchResult[] = [];

    for (const [docId, docResults] of docGroups) {
      const docInfo = this.sentenceStore.getDocument(docId);
      const docName = docInfo?.filename ?? docId;

      for (const result of docResults) {
        const paraId = result.metadata.paragraph_id as string;
        const allParas = this.sentenceStore.getPrecedingParagraphs(docId, paraId);

        if (allParas.length === 0) {
          finalResults.push(result);
          continue;
        }

        allParas.sort((a, b) => a.rank - b.rank);

        const textChunks: Record<string, unknown>[] = [];
        const tableChunks: Record<string, unknown>[] = [];
        const formulaChunks: Record<string, unknown>[] = [];

        for (let idx = 0; idx < allParas.length - 1; idx++) {
          const para = allParas[idx];
          const contentType = summarizer.detectContentType(para);

          if (contentType === "table") {
            tableChunks.push(summarizer.applyTableStrategy(para));
          } else if (contentType === "formula") {
            formulaChunks.push(summarizer.applyFormulaStrategy(para, allParas, idx));
          } else {
            textChunks.push(para);
          }
        }

        const targetChunk = allParas[allParas.length - 1];

        let summary = "";
        if (textChunks.length > 0) {
          try {
            summary = await summarizer.summarizeBatch(textChunks);
          } catch {
            summary = summarizer.createFallbackSummary(textChunks, "text");
          }
        }

        const enrichedContext = summarizer.assembleContext(summary, tableChunks, formulaChunks, targetChunk);

        finalResults.push({
          ...result,
          text: enrichedContext,
          metadata: {
            ...result.metadata,
            doc_name: docName,
            cumulative: true,
            summary_chunks: textChunks.length,
            table_count: tableChunks.length,
            formula_count: formulaChunks.length,
          },
        });
      }
    }

    return finalResults;
  }

  private weightedFusion(
    vectorResults: VectorSearchResult[],
    bm25Results: BM25SearchResult[],
    alpha: number,
  ): Map<string, number> {
    const combined = new Map<string, number>();

    if (vectorResults.length > 0) {
      const maxVector = Math.max(...vectorResults.map((r) => r.score));
      for (const r of vectorResults) {
        const normalized = maxVector > 0 ? r.score / maxVector : 0;
        combined.set(r.sentence_id, (combined.get(r.sentence_id) ?? 0) + alpha * normalized);
      }
    }

    if (bm25Results.length > 0) {
      const maxBm25 = Math.max(...bm25Results.map((r) => r.score));
      for (const r of bm25Results) {
        const normalized = maxBm25 > 0 ? r.score / maxBm25 : 0;
        combined.set(r.sentence_id, (combined.get(r.sentence_id) ?? 0) + (1 - alpha) * normalized);
      }
    }

    return combined;
  }

  private reciprocalRankFusion(
    vectorResults: VectorSearchResult[],
    bm25Results: BM25SearchResult[],
    k = 60,
  ): Map<string, number> {
    const scores = new Map<string, number>();

    for (let rank = 0; rank < vectorResults.length; rank++) {
      const id = vectorResults[rank].sentence_id;
      scores.set(id, (scores.get(id) ?? 0) + 1 / (k + rank + 1));
    }

    for (let rank = 0; rank < bm25Results.length; rank++) {
      const id = bm25Results[rank].sentence_id;
      scores.set(id, (scores.get(id) ?? 0) + 1 / (k + rank + 1));
    }

    return scores;
  }

  close(): void {
    this.sentenceStore.close();
  }
}
