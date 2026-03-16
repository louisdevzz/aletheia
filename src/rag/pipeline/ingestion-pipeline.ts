import { existsSync } from "fs";
import { basename } from "path";
import { VisionLLMParser, IngestionParser } from "../parsers/vision-llm-parser.js";
import { SQLiteStore } from "../storage/sqlite-store.js";
import { VectorIndex } from "../storage/vector-index.js";
import { BM25Index } from "../storage/bm25-index.js";
import { SmartMetadataFilter } from "../processing/smart-filter.js";
import { ContentDeduplicator } from "../processing/deduplicator.js";
import { TransactionalIngestion, createIngestionBatch } from "./ingestion-coordinator.js";
import type { Paragraph, DisplayMath, Table as TableType, Figure, PageItem } from "../parsers/types.js";
import { isParagraph, isDisplayMath, isTable, isFigure } from "../parsers/types.js";

export class IngestionPipeline {
  private readonly visionParser: VisionLLMParser;
  private readonly ingestionParser: IngestionParser;
  private readonly sentenceStore: SQLiteStore;
  private readonly vectorIndex: VectorIndex;
  private readonly bm25Index: BM25Index;
  private readonly metadataFilter: SmartMetadataFilter;
  private readonly deduplicator: ContentDeduplicator;
  private readonly coordinator: TransactionalIngestion;

  constructor(visionModel?: string) {
    this.visionParser = new VisionLLMParser(visionModel);
    this.ingestionParser = new IngestionParser();
    this.sentenceStore = new SQLiteStore();
    this.vectorIndex = new VectorIndex();
    this.bm25Index = new BM25Index();
    this.metadataFilter = new SmartMetadataFilter();
    this.deduplicator = new ContentDeduplicator({ exactMatch: true, fuzzyMatch: true, similarityThreshold: 0.95, minTextLength: 20 });
    this.coordinator = new TransactionalIngestion(this.sentenceStore, this.vectorIndex, this.bm25Index, 3, 1.0);

    console.log("[pipeline] Ingestion pipeline initialized");
  }

  async setupIndices(dropExisting = false): Promise<void> {
    await this.vectorIndex.createCollection(dropExisting);
    await this.bm25Index.createIndex(dropExisting);
    console.log("[pipeline] Indices setup complete");
  }

  async ingestDocument(pdfPath: string, originalFilename?: string, docId?: string): Promise<string> {
    if (!existsSync(pdfPath)) {
      throw new Error(`PDF file not found: ${pdfPath}`);
    }

    const filename = originalFilename ?? basename(pdfPath);
    const startTime = performance.now();

    console.log(`\n${"=".repeat(60)}`);
    console.log(`Starting ingestion: ${filename}`);
    console.log(`${"=".repeat(60)}\n`);

    // Step 1: Get PDF info
    const totalPages = await this.visionParser.getPdfPageCount(pdfPath);
    console.log(`  Found ${totalPages} pages.`);

    // Step 2: Create document record
    if (!docId) {
      docId = this.sentenceStore.insertDocument(filename, totalPages, { source_path: pdfPath }, "processing");
    }

    // Step 3-7: Process pages (sequential with max 2 concurrent)
    const allSentencesData: Record<string, unknown>[] = [];
    const concurrency = 2;

    for (let i = 0; i < totalPages; i += concurrency) {
      const pagePromises: Promise<Record<string, unknown>[]>[] = [];

      for (let j = i; j < Math.min(i + concurrency, totalPages); j++) {
        pagePromises.push(this.processSinglePage(pdfPath, j + 1, docId!, totalPages));
      }

      const results = await Promise.allSettled(pagePromises);

      for (let j = 0; j < results.length; j++) {
        const pageNum = i + j + 1;
        const result = results[j];

        if (result.status === "fulfilled" && result.value.length > 0) {
          allSentencesData.push(...result.value);
          const batch = createIngestionBatch(docId!, pageNum, result.value);
          const success = await this.coordinator.ingestBatch(batch);

          if (success) {
            console.log(`  Page ${pageNum} complete (${result.value.length} sentences)`);
          } else {
            console.error(`  Page ${pageNum} failed after retries.`);
          }
        } else if (result.status === "rejected") {
          console.error(`  Page ${pageNum} error:`, result.reason);
        }
      }
    }

    // Update document status
    this.sentenceStore.updateDocumentStatus(docId!, "completed");

    const totalTime = ((performance.now() - startTime) / 1000).toFixed(1);
    const failedBatches = this.coordinator.getFailedBatches();

    console.log(`\n${"=".repeat(60)}`);
    console.log(`Ingestion complete!`);
    console.log(`  Document ID: ${docId}`);
    console.log(`  Total pages: ${totalPages}`);
    console.log(`  Total sentences: ${allSentencesData.length}`);
    console.log(`  Total time: ${totalTime}s`);

    if (failedBatches.length > 0) {
      console.log(`  WARNING: ${failedBatches.length} page(s) failed ingestion`);
    } else {
      console.log(`  All pages indexed successfully`);
    }
    console.log(`${"=".repeat(60)}\n`);

    return docId!;
  }

  private async processSinglePage(
    pdfPath: string,
    pageNum: number,
    docId: string,
    totalPages: number,
  ): Promise<Record<string, unknown>[]> {
    console.log(`\n[Page ${pageNum}/${totalPages}] Started processing`);

    // Check existing
    if (this.sentenceStore.pageExists(docId, pageNum)) {
      console.log(`  Page ${pageNum} already exists. Skipping.`);
      return [];
    }

    // Vision LLM
    const base64Image = await this.visionParser.getPageImageBase64(pdfPath, pageNum);
    const pageContent = await this.visionParser.parseImage(base64Image, pageNum);

    // Parse
    const pageObj = this.ingestionParser.parseCanonicalMarkdown(pageContent, pageNum);

    // Extract sentences
    let sentences = this.extractSentencesFromPage(docId, pageObj.items, pageNum);

    // Filter metadata
    const preFilterCount = sentences.length;
    sentences = this.filterSentencesMetadata(sentences);
    const filtered = preFilterCount - sentences.length;
    if (filtered > 0) {
      console.log(`  [Page ${pageNum}] Filtered ${filtered} metadata items`);
    }

    // Deduplicate
    const preDedup = sentences.length;
    sentences = this.deduplicator.deduplicate(sentences);
    if (sentences.length < preDedup) {
      console.log(`  [Page ${pageNum}] Deduplicated ${preDedup - sentences.length} items`);
    }

    console.log(`  [Page ${pageNum}] COMPLETE (${sentences.length} unique sentences)`);
    return sentences;
  }

  private extractSentencesFromPage(
    docId: string,
    items: readonly PageItem[],
    pageNum: number,
  ): { id: string; page_num: number; paragraph_id: string; sentence_id: string; text: string; char_offset_start: number; char_offset_end: number; item_type: string }[] {
    const sentences: { id: string; page_num: number; paragraph_id: string; sentence_id: string; text: string; char_offset_start: number; char_offset_end: number; item_type: string }[] = [];

    for (const item of items) {
      if (isParagraph(item)) {
        for (const sentence of item.sentences) {
          sentences.push({
            id: `${docId}_${sentence.id}`,
            page_num: pageNum,
            paragraph_id: item.id,
            sentence_id: sentence.id,
            text: sentence.text,
            char_offset_start: sentence.offsetStart,
            char_offset_end: sentence.offsetEnd,
            item_type: "paragraph",
          });
        }
      } else if (isDisplayMath(item)) {
        sentences.push({
          id: `${docId}_${item.id}`,
          page_num: pageNum,
          paragraph_id: item.id,
          sentence_id: item.id,
          text: item.latex,
          char_offset_start: 0,
          char_offset_end: item.latex.length,
          item_type: "display_math",
        });
      } else if (isTable(item)) {
        sentences.push({
          id: `${docId}_${item.id}`,
          page_num: pageNum,
          paragraph_id: item.id,
          sentence_id: item.id,
          text: item.html,
          char_offset_start: 0,
          char_offset_end: item.html.length,
          item_type: "table",
        });
      } else if (isFigure(item)) {
        sentences.push({
          id: `${docId}_${item.id}`,
          page_num: pageNum,
          paragraph_id: item.id,
          sentence_id: item.id,
          text: item.description,
          char_offset_start: 0,
          char_offset_end: item.description.length,
          item_type: "figure",
        });
      }
    }

    return sentences;
  }

  private filterSentencesMetadata(
    sentences: { id: string; page_num: number; paragraph_id: string; sentence_id: string; text: string; char_offset_start: number; char_offset_end: number; item_type: string }[],
  ): typeof sentences {
    return sentences.filter((s) => {
      const filteredText = this.metadataFilter.filterContent(s.text);
      if (filteredText.trim().length < 10) return false;
      s.text = filteredText;
      return true;
    });
  }

  async deleteDocument(docId: string): Promise<void> {
    console.log(`Deleting document: ${docId}`);
    this.sentenceStore.deleteDocument(docId);
    await this.vectorIndex.deleteByDocId(docId);
    await this.bm25Index.deleteByDocId(docId);
    console.log(`Document deleted from all layers`);
  }

  close(): void {
    this.sentenceStore.close();
  }
}
