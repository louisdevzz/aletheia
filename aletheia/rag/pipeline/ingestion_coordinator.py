"""
Ingestion Coordinator - Manages transactional integrity across storage layers.
Ensures all-or-nothing semantics for document ingestion with retry logic.
"""

import time
import traceback
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from enum import Enum


class StorageLayer(Enum):
    POSTGRESQL = "postgresql"
    MILVUS = "milvus"
    ELASTICSEARCH = "elasticsearch"


@dataclass
class IngestionBatch:
    """Represents a batch of sentences to be ingested."""

    doc_id: str
    page_num: int
    sentences: List[Dict]
    retry_count: int = 0

    def get_sentence_ids(self) -> List[str]:
        return [s["id"] for s in self.sentences]


class TransactionalIngestion:
    """
    Coordinates ingestion across multiple storage layers with transactional semantics.

    Strategy:
    1. Try to insert into all 3 layers
    2. If any layer fails, retry with exponential backoff
    3. If still failing after max retries, rollback successful layers and mark batch as failed
    4. Failed batches are logged for manual inspection
    """

    def __init__(
        self,
        sentence_store,
        vector_index,
        bm25_index,
        max_retries: int = 3,
        retry_delay_base: float = 1.0,
    ):
        self.sentence_store = sentence_store
        self.vector_index = vector_index
        self.bm25_index = bm25_index
        self.max_retries = max_retries
        self.retry_delay_base = retry_delay_base
        self.failed_batches: List[IngestionBatch] = []

    def ingest_batch(self, batch: IngestionBatch) -> bool:
        """
        Ingest a batch transactionally across all storage layers.

        Returns:
            True if successful, False if failed after all retries
        """
        doc_id = batch.doc_id
        page_num = batch.page_num
        sentences = batch.sentences

        print(
            f"  [Coordinator] Ingesting batch for Page {page_num} ({len(sentences)} sentences)"
        )

        # Track which layers succeeded (for potential rollback)
        pg_success = False
        milvus_success = False
        es_success = False

        for attempt in range(self.max_retries + 1):
            try:
                # Attempt 0 is initial try, attempts 1+ are retries
                if attempt > 0:
                    delay = self.retry_delay_base * (2 ** (attempt - 1))
                    print(
                        f"  [Coordinator] Retry {attempt}/{self.max_retries} after {delay:.1f}s..."
                    )
                    time.sleep(delay)

                # Step 1: SQLite (Ground Truth)
                if not pg_success:
                    try:
                        self.sentence_store.insert_sentences(doc_id, sentences)
                        pg_success = True
                        print(f"    ✅ SQLite: {len(sentences)} sentences")
                    except Exception as e:
                        print(f"    ❌ SQLite failed: {e}")
                        raise

                # Step 2: Milvus (Vector Index)
                if not milvus_success:
                    try:
                        self.vector_index.insert_vectors(sentences, doc_id)
                        milvus_success = True
                        print(f"    ✅ Milvus: {len(sentences)} vectors")
                    except Exception as e:
                        print(f"    ❌ Milvus failed: {e}")
                        raise

                # Step 3: Elasticsearch (BM25)
                if not es_success:
                    try:
                        self.bm25_index.index_sentences(sentences, doc_id)
                        es_success = True
                        print(f"    ✅ Elasticsearch: {len(sentences)} docs")
                    except Exception as e:
                        print(f"    ❌ Elasticsearch failed: {e}")
                        raise

                # All layers succeeded
                print(f"  [Coordinator] ✓ Batch completed successfully")
                return True

            except Exception as e:
                print(f"  [Coordinator] ⚠️  Attempt {attempt + 1} failed: {e}")

                if attempt < self.max_retries:
                    continue  # Retry
                else:
                    # Max retries exceeded - need to handle failure
                    print(f"  [Coordinator] ❌ Max retries exceeded")
                    break

        # If we get here, all retries failed
        # Rollback any successful layers to maintain consistency
        print(f"  [Coordinator] Rolling back successful layers...")
        self._rollback_batch(batch, pg_success, milvus_success, es_success)

        # Add to failed batches for manual inspection
        batch.retry_count = self.max_retries
        self.failed_batches.append(batch)

        return False

    def _rollback_batch(
        self,
        batch: IngestionBatch,
        pg_success: bool,
        milvus_success: bool,
        es_success: bool,
    ):
        """
        Rollback successfully inserted data to maintain consistency.
        """
        doc_id = batch.doc_id
        sentence_ids = batch.get_sentence_ids()

        if pg_success:
            try:
                print(f"    [Rollback] Removing from SQLite...")
                # Delete specific sentences
                for sid in sentence_ids:
                    self.sentence_store.delete_sentence(sid)
            except Exception as e:
                print(f"    [Rollback] SQLite cleanup failed: {e}")

        if milvus_success:
            try:
                print(f"    [Rollback] Removing from Milvus...")
                self.vector_index.client.delete(
                    collection_name=self.vector_index.collection_name, ids=sentence_ids
                )
            except Exception as e:
                print(f"    [Rollback] Milvus cleanup failed: {e}")

        if es_success:
            try:
                print(f"    [Rollback] Removing from Elasticsearch...")
                for sid in sentence_ids:
                    try:
                        self.bm25_index.es.delete(
                            index=self.bm25_index.index_name, id=sid
                        )
                    except:
                        pass  # May not exist
            except Exception as e:
                print(f"    [Rollback] ES cleanup failed: {e}")

    def get_failed_batches(self) -> List[IngestionBatch]:
        """Get list of batches that failed after all retries."""
        return self.failed_batches

    def retry_failed_batches(self) -> int:
        """
        Retry all previously failed batches.
        Returns number of successfully recovered batches.
        """
        if not self.failed_batches:
            return 0

        print(f"\n[Coordinator] Retrying {len(self.failed_batches)} failed batches...")

        recovered = 0
        still_failed = []

        for batch in self.failed_batches:
            batch.retry_count = 0  # Reset retry count
            if self.ingest_batch(batch):
                recovered += 1
            else:
                still_failed.append(batch)

        self.failed_batches = still_failed
        print(
            f"[Coordinator] Recovered {recovered}/{recovered + len(still_failed)} batches"
        )
        return recovered


class IdempotentIngestion(TransactionalIngestion):
    """
    Extended version that checks for existing data before inserting.
    Prevents duplicates and handles partial ingestion scenarios.
    """

    def ingest_batch(self, batch: IngestionBatch) -> bool:
        """
        Idempotent batch ingestion - skips already existing sentences.
        """
        doc_id = batch.doc_id
        page_num = batch.page_num
        sentences = batch.sentences

        print(f"  [Idempotent] Checking Page {page_num}...")

        # Check which sentences already exist
        sentence_ids = batch.get_sentence_ids()

        # Check SQLite
        existing_pg = self._check_existing_sqlite(sentence_ids)
        # Check Milvus
        existing_milvus = self._check_existing_milvus(sentence_ids)
        # Check ES
        existing_es = self._check_existing_es(sentence_ids)

        # Filter to only new sentences
        all_existing = existing_pg | existing_milvus | existing_es
        new_sentences = [s for s in sentences if s["id"] not in all_existing]

        if not new_sentences:
            print(f"    ⏭️  All {len(sentences)} sentences already indexed")
            return True

        if all_existing:
            print(
                f"    ℹ️  {len(all_existing)} already exist, processing {len(new_sentences)} new"
            )

        # Create new batch with only new sentences
        new_batch = IngestionBatch(
            doc_id=doc_id, page_num=page_num, sentences=new_sentences
        )

        # Use parent class logic
        return super().ingest_batch(new_batch)

    def _check_existing_sqlite(self, sentence_ids: List[str]) -> set:
        """Check which sentence IDs exist in SQLite."""
        existing = set()
        try:
            # Batch check with IN clause
            for i in range(0, len(sentence_ids), 1000):
                batch = sentence_ids[i : i + 1000]
                # SQLite uses placeholders with ? and IN clause
                placeholders = ",".join("?" for _ in batch)
                query = f"SELECT id FROM sentences WHERE id IN ({placeholders})"
                with self.sentence_store._get_connection() as conn:
                    cursor = conn.execute(query, batch)
                    existing.update(row[0] for row in cursor.fetchall())
        except Exception as e:
            print(f"    ⚠️  Could not check SQLite: {e}")
        return existing

    def _check_existing_milvus(self, sentence_ids: List[str]) -> set:
        """Check which sentence IDs exist in Milvus."""
        existing = set()
        try:
            # Query Milvus for existing IDs
            results = self.vector_index.client.get(
                collection_name=self.vector_index.collection_name, ids=sentence_ids
            )
            for r in results:
                if r.get("sentence_id"):
                    existing.add(r["sentence_id"])
        except Exception as e:
            print(f"    ⚠️  Could not check Milvus: {e}")
        return existing

    def _check_existing_es(self, sentence_ids: List[str]) -> set:
        """Check which sentence IDs exist in Elasticsearch."""
        existing = set()
        try:
            # Use mget for batch retrieval
            result = self.bm25_index.es.mget(
                index=self.bm25_index.index_name, ids=sentence_ids, _source=False
            )
            for doc in result.get("docs", []):
                if doc.get("found"):
                    existing.add(doc["_id"])
        except Exception as e:
            print(f"    ⚠️  Could not check ES: {e}")
        return existing
