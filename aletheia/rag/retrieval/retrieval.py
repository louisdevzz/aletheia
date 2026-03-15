"""
Hybrid Retrieval System
Combines vector search (Milvus) and BM25 search (Elasticsearch) with score fusion.
"""

from typing import List, Dict, Optional
from collections import defaultdict

from aletheia.rag.storage.vector_index import VectorIndex
from aletheia.rag.storage.bm25_index import BM25Index
from aletheia.rag.storage.sqlite_store import SQLiteStore as SentenceStore
from aletheia.rag.retrieval.reranker import Reranker


class HybridRetrieval:
    """Hybrid search combining vector similarity and BM25 keyword matching."""

    def __init__(self):
        """Initialize retriever with all search layers."""
        self.vector_index = VectorIndex()
        self.bm25_index = BM25Index()
        self.sentence_store = SentenceStore()
        self.reranker = Reranker()

    def vector_search(
        self, query: str, top_k: int = 10, filter_doc_id: str = None
    ) -> List[Dict]:
        """
        Semantic search using vector similarity.

        Args:
            query: Search query
            top_k: Number of results
            filter_doc_id: Optional document filter

        Returns:
            List of results with sentence IDs and scores
        """
        return self.vector_index.search(
            query=query, top_k=top_k, filter_doc_id=filter_doc_id
        )

    def bm25_search(
        self, query: str, top_k: int = 10, filter_doc_id: str = None
    ) -> List[Dict]:
        """
        Keyword search using BM25.

        Args:
            query: Search query
            top_k: Number of results
            filter_doc_id: Optional document filter

        Returns:
            List of results with sentence IDs and scores
        """
        return self.bm25_index.search(
            query=query, top_k=top_k, filter_doc_id=filter_doc_id
        )

    def hybrid_search(
        self,
        query: str,
        top_k: int = 3,
        alpha: float = 0.5,
        filter_doc_id: str = None,
        rerank_method: str = "weighted",
        use_cumulative_context: bool = False,
        generator: object = None,
    ) -> List[Dict]:
        """
        Redesigned Hybrid Search with Cumulative Context.

        NEW Workflow:
        1. Hybrid Search → Rerank → Top K (user-configurable, default=3)
        2. Group by document (prevent cross-contamination)
        3. For each document group:
           a. Fetch preceding paragraphs
           b. Classify content (text/table/formula)
           c. Apply strategies:
              - Text → Batch incremental summarization
              - Table → Decoupled indexing (preserve with caption)
              - Formula → Context enrichment (LaTeX + context)
           d. Assemble enriched context
        4. Return multi-document contexts with isolation

        Args:
            query: Search query
            top_k: Number of final results (default=3, configurable)
            alpha: Weight for vector search (0-1)
            filter_doc_id: Optional document filter
            rerank_method: "weighted" or "rrf"
            use_cumulative_context: Enable cumulative mode
            generator: LLMGenerator instance (required for cumulative mode)

        Returns:
            List of top-k results with enriched context
        """
        from aletheia.rag.retrieval.cumulative_summarizer import CumulativeSummarizer
        from collections import defaultdict

        # Phase 1: Initial Retrieval
        # Fetch fewer candidates (top_k * 2 instead of 50)
        candidate_k = max(top_k * 2, 10)  # At least 10 for diversity
        fetch_k = candidate_k * 2

        # Vector search
        vector_results = self.vector_search(
            query, top_k=fetch_k, filter_doc_id=filter_doc_id
        )

        # BM25 search
        bm25_results = self.bm25_search(
            query, top_k=fetch_k, filter_doc_id=filter_doc_id
        )

        # Score fusion
        if rerank_method == "rrf":
            combined_scores = self._reciprocal_rank_fusion(vector_results, bm25_results)
        else:
            combined_scores = self._weighted_fusion(vector_results, bm25_results, alpha)

        # Rank and get top candidates
        ranked_sentence_ids = sorted(
            combined_scores.items(), key=lambda x: x[1], reverse=True
        )[:candidate_k]

        if not ranked_sentence_ids:
            return []

        # Phase 2: Context Expansion (Simple paragraph for reranking)
        candidates = []
        for sentence_id, score in ranked_sentence_ids:
            sentence_data = self.sentence_store.get_sentence_by_id(sentence_id)
            if not sentence_data:
                continue

            # Get simple paragraph context for reranking
            # (NOT cumulative yet - that happens after reranking)
            window = self.sentence_store.get_paragraph_context(
                doc_id=sentence_data["doc_id"],
                paragraph_id=sentence_data["paragraph_id"],
            )
            paragraph_text = " ".join([s["text"] for s in window])

            candidates.append(
                {
                    "sentence_id": sentence_id,
                    "text": paragraph_text,
                    "score": score,
                    "metadata": {
                        "doc_id": sentence_data["doc_id"],
                        "page_num": sentence_data["page_num"],
                        "paragraph_id": sentence_data["paragraph_id"],
                        "char_offset_start": sentence_data["char_offset_start"],
                        "char_offset_end": sentence_data["char_offset_end"],
                        "item_type": sentence_data.get("item_type", "paragraph"),
                    },
                }
            )

        # Phase 3: Reranking with Cross-Encoder
        if candidates and self.reranker:
            reranked_candidates = self.reranker.rerank(query, candidates, top_k=top_k)
        else:
            reranked_candidates = candidates[:top_k]

        # Phase 4: Cumulative Context Building (AFTER reranking)
        if not use_cumulative_context or not generator:
            # Standard mode: just return reranked results
            return reranked_candidates

        # Cumulative mode: Build enriched contexts
        summarizer = CumulativeSummarizer(generator)

        # Group results by document
        doc_groups = defaultdict(list)
        for result in reranked_candidates:
            doc_id = result["metadata"]["doc_id"]
            doc_groups[doc_id].append(result)

        # Process each document group
        final_results = []

        for doc_id, doc_results in doc_groups.items():
            # Get document metadata
            doc_info = self.sentence_store.get_document(doc_id)
            doc_name = doc_info.get("filename", doc_id) if doc_info else doc_id

            for result in doc_results:
                para_id = result["metadata"]["paragraph_id"]

                # Fetch all preceding paragraphs (1 to N)
                all_paras = self.sentence_store.get_preceding_paragraphs(
                    doc_id=doc_id, target_paragraph_id=para_id
                )

                if not all_paras:
                    # Fallback: use simple paragraph
                    final_results.append(result)
                    continue

                # Sort by rank to ensure order
                all_paras.sort(key=lambda x: x.get("rank", 0))

                # Classify and separate content types
                text_chunks = []
                table_chunks = []
                formula_chunks = []

                for idx, para in enumerate(all_paras[:-1]):  # Exclude target chunk
                    content_type = summarizer.detect_content_type(para)

                    if content_type == "table":
                        table_info = summarizer.apply_table_strategy(para)
                        table_chunks.append(table_info)
                    elif content_type == "formula":
                        formula_info = summarizer.apply_formula_strategy(
                            para, all_paras, idx
                        )
                        formula_chunks.append(formula_info)
                    else:
                        text_chunks.append(para)

                # Target chunk (N)
                target_chunk = all_paras[-1]

                # Batch incremental summarization for text
                summary = ""
                if text_chunks:
                    try:
                        summary = summarizer.summarize_batch(text_chunks)
                    except Exception as e:
                        print(f"⚠️ Summarization failed: {e}")
                        summary = summarizer._create_fallback_summary(
                            text_chunks, "text"
                        )

                # Assemble enriched context
                enriched_context = summarizer.assemble_context(
                    summary=summary,
                    tables=table_chunks,
                    formulas=formula_chunks,
                    current_chunk=target_chunk,
                )

                # Update result with enriched context
                result["text"] = enriched_context
                result["metadata"]["doc_name"] = doc_name
                result["metadata"]["cumulative"] = True
                result["metadata"]["summary_chunks"] = len(text_chunks)
                result["metadata"]["table_count"] = len(table_chunks)
                result["metadata"]["formula_count"] = len(formula_chunks)

                final_results.append(result)

        return final_results

    def _weighted_fusion(
        self, vector_results: List[Dict], bm25_results: List[Dict], alpha: float
    ) -> Dict[str, float]:
        """
        Weighted score fusion.

        Args:
            vector_results: Results from vector search
            bm25_results: Results from BM25 search
            alpha: Weight for vector scores

        Returns:
            Dictionary mapping sentence_id to combined score
        """
        combined_scores = defaultdict(float)

        # Normalize vector scores
        if vector_results:
            max_vector_score = max(r["score"] for r in vector_results)
            for result in vector_results:
                normalized_score = (
                    result["score"] / max_vector_score if max_vector_score > 0 else 0
                )
                combined_scores[result["sentence_id"]] += alpha * normalized_score

        # Normalize BM25 scores
        if bm25_results:
            max_bm25_score = max(r["score"] for r in bm25_results)
            for result in bm25_results:
                normalized_score = (
                    result["score"] / max_bm25_score if max_bm25_score > 0 else 0
                )
                combined_scores[result["sentence_id"]] += (1 - alpha) * normalized_score

        return combined_scores

    def _reciprocal_rank_fusion(
        self, vector_results: List[Dict], bm25_results: List[Dict], k: int = 60
    ) -> Dict[str, float]:
        """
        Reciprocal Rank Fusion (RRF).

        Args:
            vector_results: Results from vector search
            bm25_results: Results from BM25 search
            k: RRF constant (default 60)

        Returns:
            Dictionary mapping sentence_id to RRF score
        """
        rrf_scores = defaultdict(float)

        # Add vector ranks
        for rank, result in enumerate(vector_results, start=1):
            rrf_scores[result["sentence_id"]] += 1 / (k + rank)

        # Add BM25 ranks
        for rank, result in enumerate(bm25_results, start=1):
            rrf_scores[result["sentence_id"]] += 1 / (k + rank)

        return rrf_scores

    def close(self):
        """Close all connections."""
        self.vector_index.close()
        self.bm25_index.close()
        self.sentence_store.close()
