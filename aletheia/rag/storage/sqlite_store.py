"""
SQLite Storage Layer - Ground Truth Layer

Stores full text with character offsets for precise citations.
All data persisted to ~/.aletheia/database/aletheia.db
"""

import sqlite3
import json
import uuid
from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

from aletheia.config.settings import get_workspace_dir


class SQLiteStore:
    """
    SQLite-based sentence store with full text and offset tracking.
    Optimized for single-user desktop usage with local database file.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize connection to SQLite.

        Args:
            db_path: Path to SQLite database. If None, uses ~/.aletheia/database/aletheia.db
        """
        if db_path is None:
            workspace = get_workspace_dir()
            db_dir = Path(workspace) / "database"
            db_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(db_dir / "aletheia.db")
        else:
            self.db_path = db_path

        self._init_db()
        print(f"✓ Connected to SQLite at {self.db_path}")

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            # Documents table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    total_pages INTEGER NOT NULL,
                    status TEXT DEFAULT 'processing',
                    doc_metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Sentences table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sentences (
                    id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    page_num INTEGER NOT NULL,
                    paragraph_id TEXT NOT NULL,
                    sentence_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    char_offset_start INTEGER NOT NULL,
                    char_offset_end INTEGER NOT NULL,
                    item_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
                )
            """)

            # Chat messages table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sources TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Indexes for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sentences_doc_id 
                ON sentences(doc_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sentences_page_num 
                ON sentences(doc_id, page_num)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sentences_paragraph 
                ON sentences(doc_id, paragraph_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_session 
                ON chat_messages(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sentences_offset 
                ON sentences(doc_id, char_offset_start)
            """)

            # Migration: Add status column if not exists (for existing databases)
            try:
                cursor = conn.execute("PRAGMA table_info(documents)")
                columns = [row[1] for row in cursor.fetchall()]
                if "status" not in columns:
                    conn.execute(
                        "ALTER TABLE documents ADD COLUMN status TEXT DEFAULT 'processing'"
                    )
                    print("✓ Migrated database: Added status column to documents table")
            except sqlite3.Error as e:
                print(f"Warning: Could not migrate database: {e}")

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection with proper cleanup."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
        finally:
            conn.close()

    def _execute_query(
        self,
        query: str,
        params: tuple = None,
        fetch_all: bool = False,
        many: bool = False,
        data: List[tuple] = None,
    ) -> Any:
        """Execute a query with error handling."""
        with self._get_connection() as conn:
            try:
                cur = conn.cursor()

                if many and data:
                    cur.executemany(query, data)
                    conn.commit()
                    return cur.rowcount
                else:
                    cur.execute(query, params or ())

                    if fetch_all:
                        result = cur.fetchall()
                    else:
                        result = cur.fetchone()

                    conn.commit()
                    return result

            except sqlite3.Error as e:
                conn.rollback()
                raise e

    # ============== Document Operations ==============

    def insert_document(
        self,
        filename: str,
        total_pages: int,
        metadata: dict = None,
        status: str = "processing",
    ) -> str:
        """
        Insert a new document record.

        Args:
            filename: Name of the PDF file
            total_pages: Total number of pages
            metadata: Optional metadata as dict
            status: Document status (processing, completed, failed)

        Returns:
            doc_id: UUID of the inserted document
        """
        doc_id = str(uuid.uuid4())

        query = """
            INSERT INTO documents (doc_id, filename, total_pages, status, doc_metadata)
            VALUES (?, ?, ?, ?, ?)
        """

        self._execute_query(
            query, (doc_id, filename, total_pages, status, json.dumps(metadata or {}))
        )
        print(f"✓ Inserted document: {filename} (doc_id: {doc_id}, status: {status})")
        return doc_id

    def update_document_status(self, doc_id: str, status: str):
        """
        Update document status.

        Args:
            doc_id: Document UUID
            status: New status (processing, completed, failed)
        """
        query = "UPDATE documents SET status = ? WHERE doc_id = ?"
        self._execute_query(query, (status, doc_id))
        print(f"✓ Updated document {doc_id} status to: {status}")

    def get_document(self, doc_id: str) -> Optional[Dict]:
        """
        Get document metadata by ID.

        Args:
            doc_id: Document UUID

        Returns:
            Document dict or None
        """
        query = """
            SELECT doc_id, filename, total_pages, status, doc_metadata, created_at
            FROM documents 
            WHERE doc_id = ?
        """
        row = self._execute_query(query, (doc_id,))

        if row:
            return {
                "doc_id": row[0],
                "filename": row[1],
                "total_pages": row[2],
                "status": row[3] if row[3] else "processing",
                "doc_metadata": json.loads(row[4]) if row[4] else {},
                "created_at": row[5],
            }
        return None

    def delete_document(self, doc_id: str):
        """
        Delete a document and all its sentences (cascade).
        Also invalidates related search cache entries.

        Args:
            doc_id: Document UUID
        """
        # Import here to avoid circular dependency
        try:
            from aletheia.rag.cache.search_cache import SearchCache

            cache = SearchCache()
            cache.invalidate_by_doc_id(doc_id)
            print(f"  🗑️  Invalidated search cache for doc_id: {doc_id}")
        except Exception as e:
            print(f"  ⚠️  Could not invalidate cache: {e}")

        query = "DELETE FROM documents WHERE doc_id = ?"
        self._execute_query(query, (doc_id,))
        print(f"✓ Deleted document: {doc_id}")

    def get_all_documents(self) -> List[Dict]:
        """
        Get all documents.

        Returns:
            List of document dicts
        """
        query = """
            SELECT doc_id, filename, total_pages, status, doc_metadata, created_at
            FROM documents
            ORDER BY created_at DESC
        """
        rows = self._execute_query(query, fetch_all=True)

        return [
            {
                "doc_id": row[0],
                "filename": row[1],
                "total_pages": row[2],
                "status": row[3] if row[3] else "processing",
                "doc_metadata": json.loads(row[4]) if row[4] else {},
                "created_at": row[5],
            }
            for row in rows
        ]

    # ============== Sentence Operations ==============

    def insert_sentences(self, doc_id: str, sentences: List[Dict]):
        """
        Batch insert sentences for a document.

        Args:
            doc_id: Document UUID
            sentences: List of sentence dictionaries
        """
        query = """
            INSERT INTO sentences 
            (id, doc_id, page_num, paragraph_id, sentence_id, text, 
             char_offset_start, char_offset_end, item_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        data = [
            (
                s["id"],
                doc_id,
                s["page_num"],
                s["paragraph_id"],
                s["sentence_id"],
                s["text"],
                s["char_offset_start"],
                s["char_offset_end"],
                s.get("item_type", "paragraph"),
            )
            for s in sentences
        ]

        self._execute_query(query, many=True, data=data)
        print(f"✓ Inserted {len(sentences)} sentences for doc_id: {doc_id}")

    def get_sentence_by_id(self, sentence_id: str) -> Optional[Dict]:
        """
        Retrieve a sentence by its ID.

        Args:
            sentence_id: Sentence ID

        Returns:
            Dictionary with sentence data or None
        """
        query = """
            SELECT s.id, s.doc_id, s.page_num, s.paragraph_id, s.sentence_id, s.text,
                   s.char_offset_start, s.char_offset_end, s.item_type, s.created_at,
                   d.filename
            FROM sentences s
            JOIN documents d ON s.doc_id = d.doc_id
            WHERE s.id = ?
        """

        row = self._execute_query(query, (sentence_id,))

        if row:
            return {
                "id": row[0],
                "doc_id": row[1],
                "page_num": row[2],
                "paragraph_id": row[3],
                "sentence_id": row[4],
                "text": row[5],
                "char_offset_start": row[6],
                "char_offset_end": row[7],
                "item_type": row[8],
                "created_at": row[9],
                "filename": row[10],
            }
        return None

    def get_sentences_by_doc(self, doc_id: str, page_num: int = None) -> List[Dict]:
        """
        Retrieve all sentences for a document, optionally filtered by page.

        Args:
            doc_id: Document UUID
            page_num: Optional page number filter

        Returns:
            List of sentence dictionaries
        """
        if page_num is not None:
            query = """
                SELECT id, doc_id, page_num, paragraph_id, sentence_id, text,
                       char_offset_start, char_offset_end, item_type, created_at
                FROM sentences
                WHERE doc_id = ? AND page_num = ?
                ORDER BY page_num, char_offset_start
            """
            params = (doc_id, page_num)
        else:
            query = """
                SELECT id, doc_id, page_num, paragraph_id, sentence_id, text,
                       char_offset_start, char_offset_end, item_type, created_at
                FROM sentences
                WHERE doc_id = ?
                ORDER BY page_num, char_offset_start
            """
            params = (doc_id,)

        rows = self._execute_query(query, params, fetch_all=True)

        return [
            {
                "id": row[0],
                "doc_id": row[1],
                "page_num": row[2],
                "paragraph_id": row[3],
                "sentence_id": row[4],
                "text": row[5],
                "char_offset_start": row[6],
                "char_offset_end": row[7],
                "item_type": row[8],
                "created_at": row[9],
            }
            for row in rows
        ]

    def get_sentences_by_ids(self, sentence_ids: List[str]) -> List[Dict]:
        """
        Retrieve multiple sentences by their IDs.

        Args:
            sentence_ids: List of sentence IDs

        Returns:
            List of sentence dictionaries
        """
        if not sentence_ids:
            return []

        # SQLite doesn't support ANY, use IN with placeholders
        placeholders = ",".join(["?" for _ in sentence_ids])
        query = f"""
            SELECT s.id, s.doc_id, s.page_num, s.paragraph_id, s.sentence_id, s.text,
                   s.char_offset_start, s.char_offset_end, s.item_type, s.created_at,
                   d.filename
            FROM sentences s
            JOIN documents d ON s.doc_id = d.doc_id
            WHERE s.id IN ({placeholders})
        """

        rows = self._execute_query(query, tuple(sentence_ids), fetch_all=True)

        return [
            {
                "id": row[0],
                "doc_id": row[1],
                "page_num": row[2],
                "paragraph_id": row[3],
                "sentence_id": row[4],
                "text": row[5],
                "char_offset_start": row[6],
                "char_offset_end": row[7],
                "item_type": row[8],
                "created_at": row[9],
                "filename": row[10],
            }
            for row in rows
        ]

    def delete_sentence(self, sentence_id: str) -> bool:
        """
        Delete a single sentence by ID.

        Args:
            sentence_id: Sentence UUID

        Returns:
            True if deleted
        """
        query = "DELETE FROM sentences WHERE id = ?"
        try:
            self._execute_query(query, (sentence_id,))
            return True
        except Exception as e:
            print(f"⚠️ Failed to delete sentence {sentence_id}: {e}")
            return False

    def page_exists(self, doc_id: str, page_num: int) -> bool:
        """
        Check if sentences already exist for a specific page.

        Args:
            doc_id: Document UUID
            page_num: Page number

        Returns:
            True if sentences exist
        """
        query = """
            SELECT EXISTS(
                SELECT 1 FROM sentences 
                WHERE doc_id = ? AND page_num = ?
            )
        """

        result = self._execute_query(query, (doc_id, page_num))
        return bool(result[0]) if result else False

    # ============== Context Retrieval ==============

    def get_context_window(
        self, doc_id: str, sentence_id: str, window_size: int = 2
    ) -> List[Dict]:
        """
        Retrieve a window of sentences surrounding a specific sentence.
        Uses ROW_NUMBER() equivalent via subquery.

        Args:
            doc_id: Document UUID
            sentence_id: The ID of the center sentence
            window_size: Number of sentences before and after

        Returns:
            List of sentence dictionaries
        """
        query = """
            WITH OrderedSentences AS (
                SELECT 
                    id, doc_id, page_num, paragraph_id, sentence_id, text,
                    char_offset_start, char_offset_end, item_type, created_at,
                    ROW_NUMBER() OVER (ORDER BY page_num, char_offset_start) as rn
                FROM sentences
                WHERE doc_id = ?
            ),
            TargetSentence AS (
                SELECT rn FROM OrderedSentences WHERE id = ?
            )
            SELECT 
                os.id, os.doc_id, os.page_num, os.paragraph_id, os.sentence_id, os.text,
                os.char_offset_start, os.char_offset_end, os.item_type, os.created_at
            FROM OrderedSentences os, TargetSentence ts
            WHERE os.rn BETWEEN ts.rn - ? AND ts.rn + ?
            ORDER BY os.rn ASC
        """

        rows = self._execute_query(
            query, (doc_id, sentence_id, window_size, window_size), fetch_all=True
        )

        return [
            {
                "id": row[0],
                "doc_id": row[1],
                "page_num": row[2],
                "paragraph_id": row[3],
                "sentence_id": row[4],
                "text": row[5],
                "char_offset_start": row[6],
                "char_offset_end": row[7],
                "item_type": row[8],
                "created_at": row[9],
            }
            for row in rows
        ]

    def get_paragraph_context(self, doc_id: str, paragraph_id: str) -> List[Dict]:
        """
        Retrieve ALL sentences belonging to a specific paragraph.

        Args:
            doc_id: Document UUID
            paragraph_id: Paragraph ID

        Returns:
            List of sentence dictionaries
        """
        query = """
            SELECT 
                id, doc_id, page_num, paragraph_id, sentence_id, text,
                char_offset_start, char_offset_end, item_type, created_at
            FROM sentences
            WHERE doc_id = ? AND paragraph_id = ?
            ORDER BY page_num ASC, char_offset_start ASC
        """

        rows = self._execute_query(query, (doc_id, paragraph_id), fetch_all=True)

        return [
            {
                "id": row[0],
                "doc_id": row[1],
                "page_num": row[2],
                "paragraph_id": row[3],
                "sentence_id": row[4],
                "text": row[5],
                "char_offset_start": row[6],
                "char_offset_end": row[7],
                "item_type": row[8],
                "created_at": row[9],
            }
            for row in rows
        ]

    def get_preceding_paragraphs(
        self, doc_id: str, target_paragraph_id: str
    ) -> List[Dict]:
        """
        Retrieve ALL paragraphs from the start up to target paragraph.

        Args:
            doc_id: Document UUID
            target_paragraph_id: Target paragraph ID

        Returns:
            List of paragraph dictionaries
        """
        query = """
            WITH OrderedParagraphs AS (
                SELECT 
                    paragraph_id,
                    MIN(page_num) as page_num,
                    MIN(char_offset_start) as start_offset,
                    GROUP_CONCAT(text, ' ') as full_text,
                    ROW_NUMBER() OVER (ORDER BY MIN(page_num), MIN(char_offset_start)) as rn
                FROM sentences
                WHERE doc_id = ?
                GROUP BY paragraph_id
            ),
            TargetRank AS (
                SELECT rn FROM OrderedParagraphs WHERE paragraph_id = ?
            )
            SELECT op.paragraph_id, op.page_num, op.full_text, op.rn
            FROM OrderedParagraphs op, TargetRank tr
            WHERE op.rn <= tr.rn
            ORDER BY op.rn ASC
        """

        rows = self._execute_query(query, (doc_id, target_paragraph_id), fetch_all=True)

        return [
            {"paragraph_id": row[0], "page_num": row[1], "text": row[2], "rank": row[3]}
            for row in rows
        ]

    # ============== Batch Operations (Optimized) ==============

    def get_paragraph_context_batch(
        self, sentence_ids: List[str]
    ) -> Dict[str, List[Dict]]:
        """
        Fetch paragraph context for N sentences in a single query.

        Args:
            sentence_ids: List of sentence IDs

        Returns:
            Dict mapping sentence_id -> list of context sentences
        """
        if not sentence_ids:
            return {}

        placeholders = ",".join(["?" for _ in sentence_ids])
        query = f"""
            WITH target_sentences AS (
                SELECT id, doc_id, paragraph_id
                FROM sentences
                WHERE id IN ({placeholders})
            )
            SELECT 
                t.id as target_id,
                s.id, s.doc_id, s.page_num, s.paragraph_id, 
                s.sentence_id, s.text, s.char_offset_start, 
                s.char_offset_end, s.item_type, s.created_at
            FROM target_sentences t
            JOIN sentences s ON (
                s.doc_id = t.doc_id 
                AND s.paragraph_id = t.paragraph_id
            )
            ORDER BY t.id, s.char_offset_start
        """

        try:
            rows = self._execute_query(query, tuple(sentence_ids), fetch_all=True)

            from collections import defaultdict

            result = defaultdict(list)
            for row in rows:
                target_id = row[0]
                sentence = {
                    "id": row[1],
                    "doc_id": row[2],
                    "page_num": row[3],
                    "paragraph_id": row[4],
                    "sentence_id": row[5],
                    "text": row[6],
                    "char_offset_start": row[7],
                    "char_offset_end": row[8],
                    "item_type": row[9],
                    "created_at": row[10],
                }
                result[target_id].append(sentence)

            return dict(result)

        except Exception as e:
            print(f"Batch context fetch error: {e}")
            # Fallback
            return {sid: [] for sid in sentence_ids}

    def get_sentences_by_ids_batch(
        self, sentence_ids: List[str]
    ) -> Dict[str, Optional[Dict]]:
        """
        Fetch multiple sentences in a single query.

        Args:
            sentence_ids: List of sentence IDs

        Returns:
            Dict mapping sentence_id -> sentence data
        """
        if not sentence_ids:
            return {}

        placeholders = ",".join(["?" for _ in sentence_ids])
        query = f"""
            SELECT s.id, s.doc_id, s.page_num, s.paragraph_id, 
                   s.sentence_id, s.text, s.char_offset_start, 
                   s.char_offset_end, s.item_type, s.created_at,
                   d.filename
            FROM sentences s
            JOIN documents d ON s.doc_id = d.doc_id
            WHERE s.id IN ({placeholders})
        """

        try:
            rows = self._execute_query(query, tuple(sentence_ids), fetch_all=True)

            result = {}
            for row in rows:
                sentence_id = row[0]
                result[sentence_id] = {
                    "id": sentence_id,
                    "doc_id": row[1],
                    "page_num": row[2],
                    "paragraph_id": row[3],
                    "sentence_id": row[4],
                    "text": row[5],
                    "char_offset_start": row[6],
                    "char_offset_end": row[7],
                    "item_type": row[8],
                    "created_at": row[9],
                    "filename": row[10],
                }

            # Add None for missing IDs
            for sid in sentence_ids:
                if sid not in result:
                    result[sid] = None

            return result

        except Exception as e:
            print(f"Batch sentence fetch error: {e}")
            return {sid: self.get_sentence_by_id(sid) for sid in sentence_ids}

    # ============== Chat History ==============

    def insert_chat_message(
        self, session_id: str, role: str, content: str, sources: List[Dict] = None
    ) -> str:
        """
        Insert a chat message.

        Args:
            session_id: Session UUID
            role: 'user' or 'assistant'
            content: Message content
            sources: Optional source citations

        Returns:
            message_id: UUID of inserted message
        """
        msg_id = str(uuid.uuid4())

        query = """
            INSERT INTO chat_messages (id, session_id, role, content, sources)
            VALUES (?, ?, ?, ?, ?)
        """

        self._execute_query(
            query,
            (
                msg_id,
                session_id,
                role,
                content,
                json.dumps(sources) if sources else None,
            ),
        )
        return msg_id

    def get_chat_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        """
        Get chat history for a session.

        Args:
            session_id: Session UUID
            limit: Max messages to return

        Returns:
            List of message dictionaries
        """
        query = """
            SELECT id, session_id, role, content, sources, created_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY created_at ASC
            LIMIT ?
        """

        rows = self._execute_query(query, (session_id, limit), fetch_all=True)

        return [
            {
                "id": row[0],
                "session_id": row[1],
                "role": row[2],
                "content": row[3],
                "sources": json.loads(row[4]) if row[4] else None,
                "created_at": row[5],
            }
            for row in rows
        ]

    def delete_chat_session(self, session_id: str):
        """Delete all messages for a session."""
        query = "DELETE FROM chat_messages WHERE session_id = ?"
        self._execute_query(query, (session_id,))

    # ============== Utility ==============

    def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        with self._get_connection() as conn:
            doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            sentence_count = conn.execute("SELECT COUNT(*) FROM sentences").fetchone()[
                0
            ]
            chat_count = conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[
                0
            ]

        return {
            "documents": doc_count,
            "sentences": sentence_count,
            "chat_messages": chat_count,
        }

    def vacuum(self):
        """Optimize database (VACUUM)."""
        with self._get_connection() as conn:
            conn.execute("VACUUM")
        print("✓ Database optimized")

    def close(self):
        """Close database (no-op for SQLite, kept for API compatibility)."""
        print("✓ SQLite connection closed")


# Factory function for easy usage
def create_sqlite_store(db_path: Optional[str] = None) -> SQLiteStore:
    """
    Factory function to create SQLiteStore instance.

    Usage:
        store = create_sqlite_store()
        # or
        store = create_sqlite_store("/custom/path/db.sqlite")
    """
    return SQLiteStore(db_path)
