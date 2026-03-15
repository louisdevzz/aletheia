"""
Storage Module - Data persistence layer

Contains:
- SQLiteStore: SQLite ground truth storage
- VectorIndex: Milvus vector search index
- BM25Index: Elasticsearch BM25 search index

Usage:
    from aletheia.rag.storage import SQLiteStore, get_storage
    
    store = get_storage()  # Returns SQLiteStore instance
"""

from .sqlite_store import SQLiteStore, create_sqlite_store
from .vector_index import VectorIndex
from .bm25_index import BM25Index


def get_storage():
    """
    Factory function to get storage instance.
    Always returns SQLiteStore.
    
    Usage:
        store = get_storage()
    """
    return SQLiteStore()


__all__ = [
    'SQLiteStore',
    'create_sqlite_store',
    'get_storage',
    'VectorIndex',
    'BM25Index',
]
