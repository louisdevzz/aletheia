"""
Aletheia RAG System - Document retrieval and search.

This package contains the complete RAG (Retrieval-Augmented Generation) system:
- retrieval: Hybrid search (Vector + BM25)
- storage: Data persistence (SQLite, Milvus, Elasticsearch)
- pipeline: Document ingestion pipeline
- parsers: Document parsing (Vision LLM, OCR)
- models: Database models
- cache: Search result caching
"""

# Retrieval
from .retrieval.retrieval import HybridRetrieval

# Storage
from .storage.sqlite_store import SQLiteStore
from .storage.vector_index import VectorIndex
from .storage.bm25_index import BM25Index

# Pipeline
from .pipeline.ingestion_pipeline import IngestionPipeline

# Parsers
from .parsers.vision_llm_parse import IngestionParser, VisionLLMParser

# Models
from .models.models import Document, Sentence, ChatHistory

__all__ = [
    # Retrieval
    "HybridRetrieval",
    # Storage
    "SQLiteStore",
    "VectorIndex",
    "BM25Index",
    # Pipeline
    "IngestionPipeline",
    # Parsers
    "IngestionParser",
    "VisionLLMParser",
    # Models
    "Document",
    "Sentence",
    "ChatHistory",
]
