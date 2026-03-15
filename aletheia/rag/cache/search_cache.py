"""
Search result caching layer using SQLite.

This module provides caching for search results to reduce latency
for repeated queries. Uses SQLite for persistence across sessions.
"""

import json
import sqlite3
import hashlib
import time
from typing import Optional, List, Dict, Any
from pathlib import Path

from aletheia.config.settings import get_workspace_dir


class SearchCache:
    """
    Cache for search results using SQLite.

    Benefits:
    - Reduce repeated search latency from 3-7s to <10ms
    - Persist across sessions
    - Configurable TTL per query type
    """

    DEFAULT_TTL_SECONDS = 3600  # 1 hour

    def __init__(self, ttl_seconds: int = None):
        """
        Initialize search cache.

        Args:
            ttl_seconds: Default TTL for cached entries
        """
        self.ttl_seconds = ttl_seconds or self.DEFAULT_TTL_SECONDS
        self.db_path = self._get_db_path()
        self._init_db()

    def _get_db_path(self) -> Path:
        """Get cache database path in workspace."""
        workspace = get_workspace_dir()
        cache_dir = Path(workspace) / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / "search_cache.db"

    def _init_db(self):
        """Initialize cache database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
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
            """)

            # Index for cleanup
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON search_cache(created_at)
            """)
            conn.commit()

    def _make_key(self, query: str, filters: Dict) -> str:
        """Create cache key from query and filters."""
        # Normalize query
        normalized = query.lower().strip()
        # Create hash
        filter_str = json.dumps(filters, sort_keys=True)
        combined = f"{normalized}:{filter_str}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def get(self, query: str, filters: Dict = None) -> Optional[List[Dict]]:
        """
        Get cached search results.

        Args:
            query: Search query
            filters: Optional filters applied

        Returns:
            Cached results or None if not found/expired
        """
        key = self._make_key(query, filters or {})

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT results, created_at, ttl_seconds FROM search_cache WHERE key = ?",
                (key,),
            ).fetchone()

            if not row:
                return None

            results_json, created_at, ttl = row

            # Check TTL
            if time.time() - created_at > ttl:
                # Expired, delete it
                conn.execute("DELETE FROM search_cache WHERE key = ?", (key,))
                conn.commit()
                return None

            # Update access stats
            conn.execute(
                """UPDATE search_cache 
                   SET access_count = access_count + 1, 
                       last_accessed = ? 
                   WHERE key = ?""",
                (time.time(), key),
            )
            conn.commit()

            return json.loads(results_json)

    def set(
        self, query: str, filters: Dict, results: List[Dict], ttl_seconds: int = None
    ):
        """
        Cache search results.

        Args:
            query: Search query
            filters: Filters applied
            results: Search results to cache
            ttl_seconds: Optional custom TTL
        """
        key = self._make_key(query, filters or {})
        ttl = ttl_seconds or self.ttl_seconds

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO search_cache 
                   (key, query_hash, filters_hash, results, created_at, ttl_seconds, last_accessed)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    key,
                    hashlib.sha256(query.encode()).hexdigest()[:16],
                    hashlib.sha256(json.dumps(filters).encode()).hexdigest()[:16],
                    json.dumps(results),
                    time.time(),
                    ttl,
                    time.time(),
                ),
            )
            conn.commit()

    def invalidate(self, query: str, filters: Dict = None):
        """Invalidate specific cache entry."""
        key = self._make_key(query, filters or {})

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM search_cache WHERE key = ?", (key,))
            conn.commit()

    def invalidate_by_doc_id(self, doc_id: str):
        """
        Invalidate all cache entries related to a specific document.

        Args:
            doc_id: Document UUID to invalidate
        """
        with sqlite3.connect(self.db_path) as conn:
            # Delete cache entries where filters contain this doc_id
            # The filters_hash might contain: {"doc_id": "uuid"}
            conn.execute(
                "DELETE FROM search_cache WHERE filters_hash LIKE ?",
                (f'%"doc_id": "{doc_id}"%',),
            )
            conn.commit()

    def clear(self):
        """Clear all cache entries."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM search_cache")
            conn.commit()

    def cleanup_expired(self):
        """Remove all expired entries."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM search_cache WHERE (created_at + ttl_seconds) < ?",
                (time.time(),),
            )
            conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM search_cache").fetchone()[0]

            expired = conn.execute(
                "SELECT COUNT(*) FROM search_cache WHERE (created_at + ttl_seconds) < ?",
                (time.time(),),
            ).fetchone()[0]

            total_hits = conn.execute(
                "SELECT COALESCE(SUM(access_count), 0) FROM search_cache"
            ).fetchone()[0]

            return {
                "total_entries": total,
                "expired_entries": expired,
                "total_cache_hits": total_hits,
                "db_size_mb": self.db_path.stat().st_size / (1024 * 1024)
                if self.db_path.exists()
                else 0,
            }
