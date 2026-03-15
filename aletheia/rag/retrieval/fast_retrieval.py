"""
Fast retrieval pipeline with caching, batch queries, and parallel execution.
"""

import asyncio
import time
from typing import List, Dict, Optional, Any
from collections import defaultdict

from ..cache import SearchCache
from ..storage.vector_index import VectorIndex
from ..storage.bm25_index import BM25Index
from ..storage.sqlite_store import SQLiteStore as OptimizedSentenceStore
from ..storage.sqlite_store import SQLiteStore as AsyncSentenceStore
from ..retrieval.reranker import Reranker


class FastRetrieval:
    """
    Optimized retrieval pipeline.

    Optimizations:
    1. Caching layer - avoid repeated searches
    2. Batch SQLite queries - fix N+1 problem
    3. Parallel Vector + BM25 search
    4. Early termination for common queries
    """

    def __init__(
        self,
        use_cache: bool = True,
        use_reranker: bool = True,
        cache_ttl: Optional[int] = None,
    ):
        """
        Initialize fast retrieval.

        Args:
            use_cache: Enable result caching
            use_reranker: Enable cross-encoder reranking
            cache_ttl: Default cache TTL in seconds
        """
        self.use_cache = use_cache
        self.use_reranker = use_reranker

        # Components
        self.cache = SearchCache() if use_cache else None
        self.vector_index = VectorIndex()
        self.bm25_index = BM25Index()
        self.sentence_store = AsyncSentenceStore()
        self.reranker = Reranker() if use_reranker else None

        # Stats
        self.stats = {"cache_hits": 0, "cache_misses": 0, "avg_latency_ms": 0}

    async def search(
        self,
        query: str,
        top_k: int = 5,
        alpha: float = 0.5,
        filter_doc_id: Optional[str] = None,
        use_cumulative: bool = False,
    ) -> List[Dict]:
        """
        Fast hybrid search with caching and parallel execution.

        Pipeline:
        1. Check cache (1-5ms)
        2. Parallel Vector + BM25 (100-200ms)
        3. Score fusion (10ms)
        4. Batch fetch context (50-100ms)
        5. Optional reranking (200-500ms)
        6. Cache results

        Args:
            query: Search query
            top_k: Number of results to return
            alpha: Weight for vector vs BM25 (0=BM25 only, 1=Vector only)
            filter_doc_id: Optional document filter
            use_cumulative: Whether to use cumulative context (slower)

        Returns:
            List of search results with context
        """
        start_time = time.time()

        filters = {"doc_id": filter_doc_id} if filter_doc_id else {}

        # 1. Check cache
        if self.use_cache and self.cache:
            cached = self.cache.get(query, filters)
            if cached is not None:
                self.stats["cache_hits"] += 1
                return cached[:top_k]
            self.stats["cache_misses"] += 1

        # 2. Parallel Vector + BM25 search
        fetch_k = max(top_k * 4, 20)  # Get more candidates for fusion

        vector_task = self._vector_search(query, fetch_k, filter_doc_id)
        bm25_task = self._bm25_search(query, fetch_k, filter_doc_id)

        vector_results, bm25_results = await asyncio.gather(
            vector_task, bm25_task, return_exceptions=True
        )

        # Handle errors
        if isinstance(vector_results, Exception):
            print(f"Vector search error: {vector_results}")
            vector_results = []
        if isinstance(bm25_results, Exception):
            print(f"BM25 search error: {bm25_results}")
            bm25_results = []

        # 3. Score fusion
        fused = self._fuse_scores(vector_results, bm25_results, alpha)

        # 4. Batch fetch context (optimized)
        candidate_ids = [r["sentence_id"] for r in fused[:fetch_k]]

        if use_cumulative:
            # Slower but more context
            contexts = await self.sentence_store.get_paragraph_context_batch(
                candidate_ids
            )
        else:
            # Just get the sentences themselves
            contexts = await self.sentence_store.get_sentences_by_ids_batch(
                candidate_ids
            )

        # Attach context to results
        for result in fused[:fetch_k]:
            sid = result["sentence_id"]
            if use_cumulative:
                result["context"] = contexts.get(sid, [])
                result["text"] = " ".join([s["text"] for s in result["context"]])
            else:
                sentence = contexts.get(sid)
                result["text"] = sentence["text"] if sentence else ""

        # 5. Reranking (optional)
        if self.use_reranker and self.reranker and fused:
            candidates = fused[: min(20, len(fused))]
            reranked = self.reranker.rerank(query, candidates, top_k=top_k)
        else:
            reranked = fused[:top_k]

        # 6. Cache results
        if self.use_cache and self.cache:
            self.cache.set(query, filters, reranked)

        # Update stats
        latency_ms = (time.time() - start_time) * 1000
        self._update_latency_stats(latency_ms)

        return reranked

    async def _vector_search(
        self, query: str, top_k: int, filter_doc_id: Optional[str]
    ) -> List[Dict]:
        """Async wrapper for vector search."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.vector_index.search, query, top_k, filter_doc_id
        )

    async def _bm25_search(
        self, query: str, top_k: int, filter_doc_id: Optional[str]
    ) -> List[Dict]:
        """Async wrapper for BM25 search."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.bm25_index.search, query, top_k, filter_doc_id
        )

    def _fuse_scores(
        self, vector_results: List[Dict], bm25_results: List[Dict], alpha: float
    ) -> List[Dict]:
        """
        Weighted score fusion.

        score = alpha * vector_score + (1 - alpha) * bm25_score
        """
        combined = defaultdict(lambda: {"score": 0, "metadata": {}})

        # Normalize vector scores
        if vector_results:
            max_vector = max(r["score"] for r in vector_results)
            for r in vector_results:
                sid = r["sentence_id"]
                normalized = r["score"] / max_vector if max_vector > 0 else 0
                combined[sid]["score"] += alpha * normalized
                combined[sid]["metadata"] = r.get("metadata", {})
                combined[sid]["sentence_id"] = sid

        # Normalize BM25 scores
        if bm25_results:
            max_bm25 = max(r["score"] for r in bm25_results)
            for r in bm25_results:
                sid = r["sentence_id"]
                normalized = r["score"] / max_bm25 if max_bm25 > 0 else 0
                combined[sid]["score"] += (1 - alpha) * normalized
                combined[sid]["metadata"] = r.get("metadata", {})
                combined[sid]["sentence_id"] = sid

        # Sort by combined score
        results = list(combined.values())
        results.sort(key=lambda x: x["score"], reverse=True)

        return results

    def _update_latency_stats(self, latency_ms: float):
        """Update running average latency."""
        n = self.stats["cache_hits"] + self.stats["cache_misses"]
        if n > 0:
            old_avg = self.stats["avg_latency_ms"]
            self.stats["avg_latency_ms"] = (old_avg * (n - 1) + latency_ms) / n

    def get_stats(self) -> Dict[str, Any]:
        """Get retrieval statistics."""
        total = self.stats["cache_hits"] + self.stats["cache_misses"]
        hit_rate = self.stats["cache_hits"] / total if total > 0 else 0

        return {
            "cache_hits": self.stats["cache_hits"],
            "cache_misses": self.stats["cache_misses"],
            "cache_hit_rate": f"{hit_rate:.1%}",
            "avg_latency_ms": f"{self.stats['avg_latency_ms']:.1f}",
        }

    def clear_cache(self):
        """Clear search cache."""
        if self.cache:
            self.cache.clear()


# Convenience function for simple usage
def create_fast_retrieval(
    use_cache: bool = True, use_reranker: bool = True
) -> FastRetrieval:
    """
    Factory function to create FastRetrieval instance.

    Usage:
        retriever = create_fast_retrieval()
        results = await retriever.search("your query")
    """
    return FastRetrieval(use_cache=use_cache, use_reranker=use_reranker)
