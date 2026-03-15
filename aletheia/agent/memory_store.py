"""
SQLite Memory Store

Implements the Memory protocol using SQLite for persistent storage.
Stores memories with embedding-based similarity search.
"""

import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer

from .memory_loader import Memory, MemoryEntry


class SQLiteMemoryStore(Memory):
    """
    SQLite-based memory store with sentence-transformer embeddings.

    Features:
    - Persistent storage in SQLite
    - Semantic search using embeddings
    - Category-based organization
    - Session-scoped memories
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize SQLite memory store.

        Args:
            db_path: Path to SQLite database. If None, uses ~/.aletheia/memory/memory.db
        """
        if db_path is None:
            from aletheia.config.settings import get_workspace_dir

            workspace = get_workspace_dir()
            memory_dir = workspace / "memory"
            memory_dir.mkdir(exist_ok=True)
            db_path = str(memory_dir / "memory.db")

        self.db_path = db_path
        self._init_db()

        # Initialize embedding model (lightweight, CPU-only to avoid CUDA errors)
        self.model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2", device="cpu"
        )

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    key TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    timestamp TEXT NOT NULL,
                    session_id TEXT,
                    embedding BLOB,
                    metadata TEXT
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_session ON memories(session_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_timestamp ON memories(timestamp)
            """)

    def _generate_id(self, key: str, timestamp: str) -> str:
        """Generate unique ID for memory entry."""
        return hashlib.md5(f"{key}:{timestamp}".encode()).hexdigest()

    def _get_embedding(self, text: str) -> bytes:
        """Generate embedding and serialize to bytes."""
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tobytes()

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    async def store(
        self,
        key: str,
        content: str,
        category: str = "general",
        session_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Store a memory entry.

        Args:
            key: Memory key/topic
            content: Memory content
            category: Memory category (core, conversation, daily, etc.)
            session_id: Optional session ID for scoping
            metadata: Optional additional metadata
        """
        timestamp = datetime.now().isoformat()
        memory_id = self._generate_id(key, timestamp)

        # Generate embedding for the content
        embedding = self._get_embedding(f"{key}: {content}")

        # Serialize metadata
        metadata_json = json.dumps(metadata) if metadata else None

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO memories (id, key, content, category, timestamp, session_id, embedding, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    key,
                    content,
                    category,
                    timestamp,
                    session_id,
                    embedding,
                    metadata_json,
                ),
            )

    async def recall(
        self, query: str, limit: int = 5, session_id: Optional[str] = None
    ) -> List[MemoryEntry]:
        """
        Recall memories matching query using semantic search.

        Args:
            query: Search query
            limit: Maximum number of results
            session_id: Optional session ID to filter by

        Returns:
            List of MemoryEntry objects sorted by relevance
        """
        # Generate query embedding
        query_embedding = self.model.encode(query, convert_to_numpy=True)

        with sqlite3.connect(self.db_path) as conn:
            # Build query
            if session_id:
                cursor = conn.execute(
                    "SELECT id, key, content, category, timestamp, embedding FROM memories WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (session_id, limit * 3),  # Get more for ranking
                )
            else:
                cursor = conn.execute(
                    "SELECT id, key, content, category, timestamp, embedding FROM memories ORDER BY timestamp DESC LIMIT ?",
                    (limit * 3,),  # Get more for ranking
                )

            rows = cursor.fetchall()

        # Calculate similarities and rank
        scored_entries = []
        for row in rows:
            memory_id, key, content, category, timestamp, embedding_blob = row

            # Deserialize embedding
            memory_embedding = np.frombuffer(embedding_blob, dtype=np.float32)

            # Calculate similarity
            similarity = self._cosine_similarity(query_embedding, memory_embedding)

            entry = MemoryEntry(
                id=memory_id,
                key=key,
                content=content,
                category=category,
                timestamp=timestamp,
                score=similarity,
            )
            scored_entries.append((entry, similarity))

        # Sort by score and return top results
        scored_entries.sort(key=lambda x: x[1], reverse=True)
        return [entry for entry, _ in scored_entries[:limit]]

    async def get_by_category(
        self, category: str, limit: int = 10
    ) -> List[MemoryEntry]:
        """
        Get memories by category.

        Args:
            category: Category to filter by
            limit: Maximum number of results

        Returns:
            List of MemoryEntry objects
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id, key, content, category, timestamp FROM memories WHERE category = ? ORDER BY timestamp DESC LIMIT ?",
                (category, limit),
            )
            rows = cursor.fetchall()

        return [
            MemoryEntry(
                id=row[0], key=row[1], content=row[2], category=row[3], timestamp=row[4]
            )
            for row in rows
        ]

    async def delete_old_memories(self, days: int = 30) -> int:
        """
        Delete memories older than specified days.

        Args:
            days: Delete memories older than this many days

        Returns:
            Number of deleted memories
        """
        from datetime import timedelta

        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM memories WHERE timestamp < ? AND category != 'core'",
                (cutoff_date,),
            )
            deleted_count = cursor.rowcount
            conn.commit()

        return deleted_count

    async def get_stats(self) -> dict:
        """Get memory store statistics."""
        with sqlite3.connect(self.db_path) as conn:
            # Total count
            cursor = conn.execute("SELECT COUNT(*) FROM memories")
            total = cursor.fetchone()[0]

            # Count by category
            cursor = conn.execute(
                "SELECT category, COUNT(*) FROM memories GROUP BY category"
            )
            by_category = {row[0]: row[1] for row in cursor.fetchall()}

            # Oldest and newest
            cursor = conn.execute("SELECT MIN(timestamp), MAX(timestamp) FROM memories")
            oldest, newest = cursor.fetchone()

        return {
            "total_memories": total,
            "by_category": by_category,
            "oldest_memory": oldest,
            "newest_memory": newest,
            "db_path": self.db_path,
        }


# Global memory store instance
_memory_store: Optional[SQLiteMemoryStore] = None


def get_memory_store() -> SQLiteMemoryStore:
    """Get or create global memory store instance."""
    global _memory_store
    if _memory_store is None:
        _memory_store = SQLiteMemoryStore()
    return _memory_store
