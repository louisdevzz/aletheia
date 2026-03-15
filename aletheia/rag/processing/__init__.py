"""
Processing utilities for RAG pipeline.

This module provides tools for content processing:
- deduplicator: Remove duplicate content
- smart_filter: Heuristic-based metadata filtering
- cross_references: IEEE-style citation resolution
- semantic_chunker: Semantic chunking with MiniLM
- token_manager: Tiktoken-based token management
- query_cache: SQLite-based query embedding cache
- precomputed_summaries: Pre-computed document summaries
- batch_embeddings: Optimized batch embedding client
"""

from .deduplicator import ContentDeduplicator, DocumentLevelDeduplicator
from .smart_filter import SmartMetadataFilter
from .cross_references import (
    CrossReferenceResolver,
    ReferenceGraphStorage,
    Reference,
    ReferenceTarget,
    ReferenceType,
)
from .semantic_chunker import SemanticChunker
from .token_manager import TokenManager
from .query_cache import QueryEmbeddingCache
from .precomputed_summaries import PrecomputedSummarizer, SummaryStorage
from .batch_embeddings import BatchEmbeddingClient

__all__ = [
    # Phase 1: Data Quality
    "ContentDeduplicator",
    "DocumentLevelDeduplicator",
    "SmartMetadataFilter",
    # Phase 2: Enrichment
    "CrossReferenceResolver",
    "ReferenceGraphStorage",
    "Reference",
    "ReferenceTarget",
    "ReferenceType",
    "SemanticChunker",
    "TokenManager",
    "PrecomputedSummarizer",
    "SummaryStorage",
    "QueryEmbeddingCache",
    # Phase 3: Performance
    "BatchEmbeddingClient",
]
