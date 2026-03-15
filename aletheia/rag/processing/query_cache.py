"""
Query Embedding Cache Module

Caches query embeddings to reduce API calls and latency.
Uses SQLite for persistence (no Redis setup required).

Usage:
    cache = QueryEmbeddingCache()
    embedding = cache.get_or_compute("query", embed_fn)
"""

import json
import sqlite3
import hashlib
import time
from typing import Optional, List, Dict, Callable
from pathlib import Path

from aletheia.config.settings import get_workspace_dir


class QueryEmbeddingCache:
    """
    SQLite-based cache for query embeddings.
    """

    DEFAULT_TTL_SECONDS = 3600 * 24  # 24 hours

    def __init__(
        self, ttl_seconds: Optional[int] = None, db_path: Optional[str] = None
    ):
        """
        Initialize query embedding cache.

        Args:
            ttl_seconds: Time-to-live for cache entries
            db_path: Custom database path (optional)
        """
        self.ttl_seconds = ttl_seconds or self.DEFAULT_TTL_SECONDS

        if db_path:
            self.db_path = Path(db_path)
        else:
            workspace = get_workspace_dir()
            cache_dir = Path(workspace) / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = cache_dir / "query_embeddings.db"

        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_embeddings (
                    query_hash TEXT PRIMARY KEY,
                    query_text TEXT,
                    embedding TEXT,  -- JSON array
                    model TEXT,
                    created_at REAL,
                    ttl_seconds INTEGER,
                    access_count INTEGER DEFAULT 0,
                    last_accessed REAL
                )
            """)

            # Indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON query_embeddings(created_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_model 
                ON query_embeddings(model)
            """)

            conn.commit()

    def _make_hash(self, query: str, model: str) -> str:
        """Create unique hash for query + model combination."""
        normalized = query.lower().strip()
        combined = f"{normalized}:{model}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def get(
        self, query: str, model: str = "text-embedding-3-small"
    ) -> Optional[List[float]]:
        """
        Get cached embedding for query.

        Args:
            query: Search query
            model: Embedding model name

        Returns:
            Embedding vector or None if not found/expired
        """
        query_hash = self._make_hash(query, model)

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT embedding, created_at, ttl_seconds 
                   FROM query_embeddings 
                   WHERE query_hash = ? AND model = ?""",
                (query_hash, model),
            ).fetchone()

            if not row:
                return None

            embedding_json, created_at, ttl = row

            # Check TTL
            if time.time() - created_at > ttl:
                # Expired, delete it
                conn.execute(
                    "DELETE FROM query_embeddings WHERE query_hash = ?", (query_hash,)
                )
                conn.commit()
                return None

            # Update access stats
            conn.execute(
                """UPDATE query_embeddings 
                   SET access_count = access_count + 1, last_accessed = ?
                   WHERE query_hash = ?""",
                (time.time(), query_hash),
            )
            conn.commit()

            return json.loads(embedding_json)

    def set(
        self,
        query: str,
        embedding: List[float],
        model: str = "text-embedding-3-small",
        ttl_seconds: Optional[int] = None,
    ):
        """
        Cache embedding for query.

        Args:
            query: Search query
            embedding: Embedding vector
            model: Embedding model name
            ttl_seconds: Optional custom TTL
        """
        query_hash = self._make_hash(query, model)
        ttl = ttl_seconds or self.ttl_seconds

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO query_embeddings 
                   (query_hash, query_text, embedding, model, created_at, ttl_seconds, last_accessed)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    query_hash,
                    query[:1000],  # Store truncated query for debugging
                    json.dumps(embedding),
                    model,
                    time.time(),
                    ttl,
                    time.time(),
                ),
            )
            conn.commit()

    def get_or_compute(
        self,
        query: str,
        compute_fn: Callable[[str], List[float]],
        model: str = "text-embedding-3-small",
    ) -> List[float]:
        """
        Get embedding from cache or compute and cache it.

        Args:
            query: Search query
            compute_fn: Function to compute embedding if not cached
            model: Embedding model name

        Returns:
            Embedding vector
        """
        # Try cache first
        cached = self.get(query, model)
        if cached:
            return cached

        # Compute
        embedding = compute_fn(query)

        # Cache
        self.set(query, embedding, model)

        return embedding

    def invalidate(self, query: str, model: str = "text-embedding-3-small"):
        """Invalidate specific cache entry."""
        query_hash = self._make_hash(query, model)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM query_embeddings WHERE query_hash = ?", (query_hash,)
            )
            conn.commit()

    def clear_model(self, model: str):
        """Clear all entries for a specific model."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM query_embeddings WHERE model = ?", (model,))
            conn.commit()

    def clear_all(self):
        """Clear all cache entries."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM query_embeddings")
            conn.commit()

    def cleanup_expired(self) -> int:
        """
        Remove expired entries.

        Returns:
            Number of entries removed
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM query_embeddings WHERE (created_at + ttl_seconds) < ?",
                (time.time(),),
            )
            conn.commit()
            return cursor.rowcount

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            # Total entries
            total = conn.execute("SELECT COUNT(*) FROM query_embeddings").fetchone()[0]

            # Expired entries
            expired = conn.execute(
                """SELECT COUNT(*) FROM query_embeddings 
                   WHERE (created_at + ttl_seconds) < ?""",
                (time.time(),),
            ).fetchone()[0]

            # Total hits
            total_hits = conn.execute(
                "SELECT COALESCE(SUM(access_count), 0) FROM query_embeddings"
            ).fetchone()[0]

            # Entries by model
            models = conn.execute(
                """SELECT model, COUNT(*) as count 
                   FROM query_embeddings 
                   GROUP BY model"""
            ).fetchall()

            # Database size
            db_size = 0
            if self.db_path.exists():
                db_size = self.db_path.stat().st_size / (1024 * 1024)  # MB

            return {
                "total_entries": total,
                "expired_entries": expired,
                "total_cache_hits": total_hits,
                "entries_by_model": {model: count for model, count in models},
                "db_size_mb": round(db_size, 2),
            }

    def get_popular_queries(self, limit: int = 10) -> List[Dict]:
        """
        Get most frequently accessed queries.

        Args:
            limit: Number of queries to return

        Returns:
            List of query info dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT query_text, access_count, model, last_accessed
                   FROM query_embeddings
                   ORDER BY access_count DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()

            return [
                {
                    "query": row[0],
                    "access_count": row[1],
                    "model": row[2],
                    "last_accessed": row[3],
                }
                for row in rows
            ]


class SemanticQueryCache(QueryEmbeddingCache):
    """
    Extended cache with semantic similarity matching.

    If exact query not found, check for semantically similar queries.
    """

    def __init__(self, similarity_threshold: float = 0.95, **kwargs):
        super().__init__(**kwargs)
        self.similarity_threshold = similarity_threshold

    def get_with_similarity(
        self,
        query: str,
        model: str = "text-embedding-3-small",
        embedding_fn: Optional[Callable[[str], List[float]]] = None,
    ) -> Optional[List[float]]:
        """
        Get embedding, checking for semantically similar queries.

        Args:
            query: Search query
            model: Embedding model
            embedding_fn: Function to compute embedding for similarity check

        Returns:
            Embedding vector or None
        """
        # Try exact match first
        exact = self.get(query, model)
        if exact:
            return exact

        # If no embedding_fn provided, can't do semantic matching
        if not embedding_fn:
            return None

        # Compute query embedding for similarity comparison
        query_embedding = embedding_fn(query)

        # Get all cached embeddings for this model
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT query_text, embedding FROM query_embeddings 
                   WHERE model = ? AND (created_at + ttl_seconds) > ?""",
                (model, time.time()),
            ).fetchall()

        # Check similarity
        for cached_query, cached_embedding_json in rows:
            cached_embedding = json.loads(cached_embedding_json)

            # Compute cosine similarity
            similarity = self._cosine_similarity(query_embedding, cached_embedding)

            if similarity >= self.similarity_threshold:
                print(
                    f"  🎯 Semantic cache hit: '{query[:50]}...' ~ '{cached_query[:50]}...'"
                )
                return cached_embedding

        return None

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        import numpy as np

        a_vec = np.array(a)
        b_vec = np.array(b)

        dot = np.dot(a_vec, b_vec)
        norm_a = np.linalg.norm(a_vec)
        norm_b = np.linalg.norm(b_vec)

        return dot / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0.0
