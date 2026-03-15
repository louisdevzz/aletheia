"""
Unified Ingestion Pipeline
Orchestrates Vision LLM parsing, sentence storage, vector indexing, and BM25 indexing.
"""

import os
import time
from pathlib import Path
from typing import List, Dict, Optional
import uuid

from aletheia.rag.parsers.vision_llm_parse import (
    VisionLLMParser,
    IngestionParser,
    Paragraph,
    Sentence,
    DisplayMath,
    Table,
    Figure,
)
from aletheia.rag.storage.sqlite_store import SQLiteStore
from aletheia.rag.storage.vector_index import VectorIndex
from aletheia.rag.storage.bm25_index import BM25Index
from aletheia.rag.processing import (
    ContentDeduplicator,
    SmartMetadataFilter,
    CrossReferenceResolver,
    ReferenceGraphStorage,
    SemanticChunker,
    TokenManager,
    PrecomputedSummarizer,
    SummaryStorage,
)


from aletheia.config.settings import kimi_config
from aletheia.rag.pipeline.ingestion_coordinator import (
    TransactionalIngestion,
    IngestionBatch,
)


class IngestionPipeline:
    """Orchestrates the complete document ingestion pipeline."""

    def __init__(self, vision_model: Optional[str] = None):
        """
        Initialize the ingestion pipeline with Kimi as the only provider.

        Args:
            vision_model: Model name (optional, defaults to kimi-k2.5)
        """
        # Initialize Vision LLM Parser with Kimi only
        if not vision_model:
            vision_model = "kimi-k2.5"

        self.vision_parser = VisionLLMParser(model_name=vision_model, provider="kimi")
        self.ingestion_parser = IngestionParser()

        # Initialize storage and indexing layers
        self.sentence_store = SQLiteStore()
        self.vector_index = VectorIndex()
        self.bm25_index = BM25Index()

        # Initialize content processing layers (Phase 1)
        self.metadata_filter = SmartMetadataFilter()
        self.deduplicator = ContentDeduplicator(
            exact_match=True,
            fuzzy_match=True,
            similarity_threshold=0.95,
            min_text_length=20,
        )

        # Initialize enrichment layers (Phase 2)
        self.cross_ref_resolver = CrossReferenceResolver()
        self.semantic_chunker = SemanticChunker(
            model_name="all-MiniLM-L6-v2", similarity_threshold=0.7, max_tokens=512
        )
        self.token_manager = TokenManager(model="text-embedding-3-small")
        self.summarizer = PrecomputedSummarizer(llm_generator=None)
        self.summary_storage = SummaryStorage()

        # Initialize transactional coordinator
        self.coordinator = TransactionalIngestion(
            sentence_store=self.sentence_store,
            vector_index=self.vector_index,
            bm25_index=self.bm25_index,
            max_retries=3,
            retry_delay_base=1.0,
        )

        print(
            "✓ Ingestion pipeline initialized (with transactional coordinator, deduplication, and metadata filtering)"
        )

    def setup_indices(self, drop_existing: bool = False):
        """
        Setup Milvus and Elasticsearch indices.

        Args:
            drop_existing: If True, drop existing indices before creating
        """
        self.vector_index.create_collection(drop_existing=drop_existing)
        self.bm25_index.create_index(drop_existing=drop_existing)
        print("✓ Indices setup complete")

    def ingest_document(
        self,
        pdf_path: str,
        original_filename: Optional[str] = None,
        doc_id: Optional[str] = None,
    ) -> str:
        """
        Ingest a PDF document through the complete pipeline.

        Args:
            pdf_path: Path to PDF file
            original_filename: Original filename (if pdf_path is temp)
            doc_id: Existing document ID (if already created)

        Returns:
            doc_id: UUID of the ingested document
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        filename = original_filename if original_filename else Path(pdf_path).name
        ingestion_start = time.time()

        print(f"\n{'=' * 60}")
        print(f"\n{'=' * 60}")
        print(f"Starting ingestion: {filename}")
        print(
            f"Vision Provider: {self.vision_parser.provider.upper()} | Model: {self.vision_parser.model_name}"
        )
        print(f"{'=' * 60}\n")

        # Step 1: Get PDF Info (Lazy)
        print("Step 1: Analyzing PDF structure...")
        total_pages = self.vision_parser.get_pdf_info(pdf_path)
        print(f"  Found {total_pages} pages.")

        # Step 2: Insert or update document record
        if doc_id is None:
            print(f"\nStep 2: Creating document record...")
            doc_id = self.sentence_store.insert_document(
                filename=filename,
                total_pages=total_pages,
                metadata={"source_path": pdf_path},
                status="processing",
            )
        else:
            print(f"\nStep 2: Updating document record...")
            # Update total_pages for existing document
            self.sentence_store._execute_query(
                "UPDATE documents SET total_pages = ? WHERE doc_id = ?",
                (total_pages, doc_id),
            )

        import concurrent.futures

        # Step 3-7: Process pages in parallel
        # Quota Protection: Reduced max_workers to 2 to respect API rate limits
        print(
            f"\nStep 3-7: Processing {total_pages} pages in parallel (Max Workers: 2)...\n"
        )

        # Results container
        all_sentences_data = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # Create a future for each page (Lazy Load Image inside thread or helper)
            # Note: We pass pdf_path instead of image object to avoid pickling large objects or holding them in RAM
            future_to_page = {
                executor.submit(
                    self._process_single_page, pdf_path, i + 1, doc_id, total_pages
                ): (i + 1)
                for i in range(total_pages)
            }

            # Process as they complete
            for future in concurrent.futures.as_completed(future_to_page):
                page_num = future_to_page[future]
                try:
                    sentences_data = future.result()
                    if sentences_data:
                        all_sentences_data.extend(sentences_data)

                        # Use transactional coordinator for atomic ingestion
                        batch = IngestionBatch(
                            doc_id=doc_id, page_num=page_num, sentences=sentences_data
                        )

                        success = self.coordinator.ingest_batch(batch)

                        if success:
                            print(
                                f"  ✓ Page {page_num} complete ({len(sentences_data)} sentences)\n"
                            )
                        else:
                            print(
                                f"  ❌ Page {page_num} failed after retries. Batch logged for manual recovery.\n"
                            )

                except Exception as exc:
                    print(f"  ❌ Page {page_num} generated an exception: {exc}")

        # ============================================================
        # PHASE 2 & 3: Post-processing enrichment
        # ============================================================
        if all_sentences_data:
            print(f"\n{'=' * 60}")
            print("Phase 2: Document Enrichment")
            print(f"{'=' * 60}")

            # Step A: Semantic Chunking (optional - for long paragraphs)
            try:
                print("  Step A: Semantic chunking...")
                enriched_sentences = []
                for item in all_sentences_data:
                    if item.get("item_type") == "paragraph":
                        text = item.get("text", "")
                        token_count = self.token_manager.count_tokens(text)

                        # If text too long, chunk it semantically
                        if token_count > 512:
                            chunks = self.semantic_chunker.chunk(text, max_tokens=512)
                            for i, chunk in enumerate(chunks):
                                new_item = item.copy()
                                new_item["text"] = chunk["text"]
                                new_item["id"] = f"{item['id']}_chunk{i}"
                                new_item["tokens"] = chunk["token_count"]
                                enriched_sentences.append(new_item)
                        else:
                            item["tokens"] = token_count
                            enriched_sentences.append(item)
                    else:
                        enriched_sentences.append(item)

                all_sentences_data = enriched_sentences
                print(f"    ✓ Processed {len(all_sentences_data)} sentences/chunks")
            except Exception as e:
                print(f"    ⚠️ Semantic chunking failed: {e}")

            # Step B: Cross-reference Resolution
            try:
                print("  Step B: Building cross-reference graph...")
                graph = self.cross_ref_resolver.build_graph(all_sentences_data)

                # Store cross-references
                ref_storage = ReferenceGraphStorage(self.sentence_store.db_path)

                # Extract and save references
                references = []
                for item in all_sentences_data:
                    if item.get("type") == "paragraph":
                        refs = self.cross_ref_resolver._extract_references(item, graph)
                        references.extend(refs)

                if references:
                    ref_storage.save_references(doc_id, references)
                    print(f"    ✓ Found {len(references)} cross-references")
                else:
                    print(f"    ℹ No cross-references found")
            except Exception as e:
                print(f"    ⚠️ Cross-reference resolution failed: {e}")

            # Step C: Token Validation
            try:
                print("  Step C: Validating token limits...")
                oversized = []
                for item in all_sentences_data:
                    tokens = item.get("tokens", 0) or self.token_manager.count_tokens(
                        item.get("text", "")
                    )
                    if tokens > 8191:  # OpenAI limit
                        oversized.append((item["id"], tokens))

                if oversized:
                    print(f"    ⚠️ {len(oversized)} items exceed token limit")
                    for id, tokens in oversized[:5]:  # Show first 5
                        print(f"      - {id}: {tokens} tokens")
                else:
                    print(f"    ✓ All items within token limits")
            except Exception as e:
                print(f"    ⚠️ Token validation failed: {e}")

            # Step D: Precomputed Summaries
            try:
                print("  Step D: Computing document summaries...")
                summaries = self.summarizer.compute_document_summaries(
                    all_sentences_data, doc_id
                )
                if summaries:
                    self.summary_storage.save_summaries(doc_id, summaries)
                    print(f"    ✓ Generated {len(summaries)} summaries")
                else:
                    print(f"    ℹ No summaries generated")
            except Exception as e:
                print(f"    ⚠️ Summary computation failed: {e}")

            print(f"{'=' * 60}\n")

        total_time = time.time() - ingestion_start
        total_sentences = len(all_sentences_data)
        avg_time_per_page = total_time / total_pages if total_pages > 0 else 0

        # Check for failed batches
        failed_batches = self.coordinator.get_failed_batches()

        print(f"\n{'=' * 60}")
        print(f"✓ Ingestion complete!")
        print(f"  Document ID: {doc_id}")
        print(f"  Total pages: {total_pages}")
        print(f"  Total sentences: {total_sentences}")
        print(f"  Total time: {total_time:.1f}s")
        print(f"  Avg time/page: {avg_time_per_page:.1f}s")

        if failed_batches:
            print(f"\n  ⚠️  WARNING: {len(failed_batches)} page(s) failed ingestion")
            print(
                f"     Document is INCOMPLETE - only {total_pages - len(failed_batches)}/{total_pages} pages indexed"
            )
            for batch in failed_batches:
                print(
                    f"     - Page {batch.page_num}: {len(batch.sentences)} sentences not indexed"
                )
        else:
            print(f"  ✅ All pages indexed successfully")

        print(f"{'=' * 60}\n")

        return doc_id

    def _process_single_page(self, pdf_path, page_num, doc_id, total_pages):
        """Helper method to process a single page (Lazy Load -> Vision -> Clean -> Parse -> Extract)."""
        page_start_time = time.time()
        print(
            f"\n[Page {page_num}/{total_pages}] 🚀 Started processing at {time.strftime('%H:%M:%S')}"
        )

        # Check existing first
        pg_exists = self.sentence_store.page_exists(doc_id, page_num)
        if pg_exists:
            print(f"  ⚠ Page {page_num} already exists in DB. Skipping processing.")
            return []

        # Step 3a: Lazy Load Image
        img_start = time.time()
        print(f"  [Page {page_num}] 📄 Loading image from PDF...")
        image = self.vision_parser.get_page_image(pdf_path, page_num)
        img_time = time.time() - img_start
        if not image:
            print(f"  ❌ [Page {page_num}] Failed to load image after {img_time:.1f}s")
            return []
        print(
            f"  [Page {page_num}] ✅ Image loaded in {img_time:.1f}s (Size: {image.size})"
        )

        # Step 3b: Vision LLM (This is usually the slowest part)
        llm_start = time.time()
        print(
            f"  [Page {page_num}] 🤖 Calling Vision LLM API ({self.vision_parser.model_name})..."
        )
        try:
            page_content = self.vision_parser.parse_image_with_logging(image, page_num)
            llm_time = time.time() - llm_start
            print(f"  [Page {page_num}] ✅ Vision LLM completed in {llm_time:.1f}s")
            if len(page_content) < 50:
                print(
                    f"  ⚠️  [Page {page_num}] Warning: Very short response ({len(page_content)} chars)"
                )
        except Exception as e:
            llm_time = time.time() - llm_start
            print(
                f"  ❌ [Page {page_num}] Vision LLM failed after {llm_time:.1f}s: {type(e).__name__}: {e}"
            )
            raise

        # Step 4: Clean
        # clean_content = self.cleaner.clean(page_content)
        # DotsOCR handles cleaning internally now

        # Step 5: Parse Objects
        parse_start = time.time()
        print(f"  [Page {page_num}] 📝 Parsing markdown to objects...")
        page_obj = self.ingestion_parser.parse_canonical_markdown(
            page_content, page_index=page_num
        )
        parse_time = time.time() - parse_start
        print(
            f"  [Page {page_num}] ✅ Parsing completed in {parse_time:.2f}s ({len(page_obj.items)} items)"
        )

        # Step 6: Extract Sentences
        extract_start = time.time()
        sentences_data = self._extract_sentences_from_page(doc_id, page_obj, page_num)
        extract_time = time.time() - extract_start
        print(
            f"  [Page {page_num}] ✅ Extracted {len(sentences_data)} raw sentences in {extract_time:.2f}s"
        )

        # Step 7: Filter metadata and boilerplate
        pre_filter_count = len(sentences_data)
        filter_start = time.time()
        sentences_data = self._filter_sentences_metadata(sentences_data)
        filter_time = time.time() - filter_start
        filtered_count = pre_filter_count - len(sentences_data)
        if filtered_count > 0:
            print(
                f"  [Page {page_num}] 🧹 Filtered {filtered_count} metadata/boilerplate items in {filter_time:.2f}s"
            )

        # Step 8: Deduplicate content
        dedup_start = time.time()
        original_count = len(sentences_data)
        sentences_data = self.deduplicator.deduplicate(sentences_data)
        dedup_time = time.time() - dedup_start
        if len(sentences_data) < original_count:
            print(
                f"  [Page {page_num}] 🧹 Deduplicated {original_count - len(sentences_data)} items in {dedup_time:.2f}s"
            )

        total_time = time.time() - page_start_time
        print(
            f"  [Page {page_num}] ✅ COMPLETE in {total_time:.1f}s ({len(sentences_data)} unique sentences)"
        )

        return sentences_data

    def _extract_sentences_from_page(
        self, doc_id: str, page_obj, page_num: int
    ) -> List[Dict]:
        """
        Extract sentences from a Page object.

        Args:
            doc_id: Document UUID (for unique ID generation)
            page_obj: Page object with items
            page_num: Page number

        Returns:
            List of sentence dictionaries
        """
        sentences = []

        for item in page_obj.items:
            if isinstance(item, Paragraph):
                for sentence in item.sentences:
                    # Construct globally unique ID: {doc_id}_{local_id}
                    unique_id = f"{doc_id}_{sentence.id}"

                    sentences.append(
                        {
                            "id": unique_id,
                            "page_num": page_num,
                            "paragraph_id": item.id,
                            "sentence_id": sentence.id,
                            "text": sentence.text,
                            "char_offset_start": sentence.offset_start,
                            "char_offset_end": sentence.offset_end,
                            "item_type": "paragraph",
                        }
                    )

            elif isinstance(item, DisplayMath):
                # Handle display math blocks (LaTeX formulas)
                unique_id = f"{doc_id}_{item.id}"

                sentences.append(
                    {
                        "id": unique_id,
                        "page_num": page_num,
                        "paragraph_id": item.id,
                        "sentence_id": item.id,
                        "text": item.latex,
                        "char_offset_start": 0,
                        "char_offset_end": len(item.latex),
                        "item_type": "display_math",
                    }
                )

            elif isinstance(item, Table):
                # Handle tables - store HTML representation
                unique_id = f"{doc_id}_{item.id}"

                sentences.append(
                    {
                        "id": unique_id,
                        "page_num": page_num,
                        "paragraph_id": item.id,
                        "sentence_id": item.id,
                        "text": item.html,
                        "char_offset_start": 0,
                        "char_offset_end": len(item.html),
                        "item_type": "table",
                    }
                )

            elif isinstance(item, Figure):
                # Handle figures - store description
                unique_id = f"{doc_id}_{item.id}"

                sentences.append(
                    {
                        "id": unique_id,
                        "page_num": page_num,
                        "paragraph_id": item.id,
                        "sentence_id": item.id,
                        "text": item.description,
                        "char_offset_start": 0,
                        "char_offset_end": len(item.description),
                        "item_type": "figure",
                    }
                )

        return sentences

    def _filter_sentences_metadata(self, sentences: List[Dict]) -> List[Dict]:
        """
        Filter metadata and boilerplate from extracted sentences.

        Args:
            sentences: List of sentence dictionaries

        Returns:
            Filtered list with metadata removed
        """
        filtered = []

        for sentence in sentences:
            text = sentence.get("text", "")

            # Apply metadata filtering
            filtered_text = self.metadata_filter.filter_content(text)

            # Skip if text is too short after filtering
            if len(filtered_text.strip()) < 10:
                continue

            # Update sentence with filtered text
            sentence["text"] = filtered_text
            filtered.append(sentence)

        return filtered

    def delete_document(self, doc_id: str):
        """
        Delete a document from all layers.

        Args:
            doc_id: Document UUID
        """
        print(f"Deleting document: {doc_id}")

        # Delete from SQLite (cascade to sentences)
        self.sentence_store.delete_document(doc_id)

        # Delete from Milvus
        self.vector_index.delete_by_doc_id(doc_id)

        # Delete from Elasticsearch
        self.bm25_index.delete_by_doc_id(doc_id)

        print(f"✓ Document deleted from all layers")

    def close(self):
        """Close all connections."""
        self.sentence_store.close()
        self.vector_index.close()
        self.bm25_index.close()
        print("✓ All connections closed")
