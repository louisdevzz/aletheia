import { CohereClientV2 } from "cohere-ai";
import { getCohereConfig } from "../../config/settings.js";

export interface RerankCandidate {
  readonly sentence_id: string;
  readonly text: string;
  score: number;
  readonly metadata: Record<string, unknown>;
}

export class Reranker {
  private readonly client: CohereClientV2 | null;
  private readonly model: string;

  constructor(model = "rerank-english-v3.0") {
    this.model = model;
    const config = getCohereConfig();

    if (config.apiKey) {
      this.client = new CohereClientV2({ token: config.apiKey });
      console.log("[reranker] Initialized with Cohere Rerank API");
    } else {
      this.client = null;
      console.log("[reranker] No Cohere API key, reranking disabled (pass-through mode)");
    }
  }

  async rerank(query: string, candidates: RerankCandidate[], topK = 5): Promise<RerankCandidate[]> {
    if (!this.client || candidates.length === 0) {
      return candidates.slice(0, topK);
    }

    try {
      const documents = candidates.map((c) => c.text);

      const response = await this.client.rerank({
        model: this.model,
        query,
        documents,
        topN: topK,
      });

      const reranked: RerankCandidate[] = [];
      for (const result of response.results ?? []) {
        const idx = result.index;
        const candidate = candidates[idx];
        reranked.push({
          ...candidate,
          score: result.relevanceScore,
        });
      }

      return reranked;
    } catch (e) {
      console.error("[reranker] Cohere rerank failed, falling back to score-only:", e);
      return candidates
        .toSorted((a, b) => b.score - a.score)
        .slice(0, topK);
    }
  }
}
