import type { SQLiteStore } from "../storage/sqlite-store.js";
import type { VectorIndex } from "../storage/vector-index.js";
import type { BM25Index } from "../storage/bm25-index.js";

export interface IngestionBatch {
  readonly docId: string;
  readonly pageNum: number;
  readonly sentences: readonly Record<string, unknown>[];
  retryCount: number;
}

export function createIngestionBatch(
  docId: string,
  pageNum: number,
  sentences: readonly Record<string, unknown>[],
): IngestionBatch {
  return { docId, pageNum, sentences, retryCount: 0 };
}

export class TransactionalIngestion {
  private readonly sentenceStore: SQLiteStore;
  private readonly vectorIndex: VectorIndex;
  private readonly bm25Index: BM25Index;
  private readonly maxRetries: number;
  private readonly retryDelayBase: number;
  private failedBatches: IngestionBatch[] = [];

  constructor(
    sentenceStore: SQLiteStore,
    vectorIndex: VectorIndex,
    bm25Index: BM25Index,
    maxRetries = 3,
    retryDelayBase = 1.0,
  ) {
    this.sentenceStore = sentenceStore;
    this.vectorIndex = vectorIndex;
    this.bm25Index = bm25Index;
    this.maxRetries = maxRetries;
    this.retryDelayBase = retryDelayBase;
  }

  async ingestBatch(batch: IngestionBatch): Promise<boolean> {
    const { docId, pageNum, sentences } = batch;
    console.log(`  [coordinator] Ingesting batch for Page ${pageNum} (${sentences.length} sentences)`);

    let sqliteSuccess = false;
    let milvusSuccess = false;
    let esSuccess = false;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      try {
        if (attempt > 0) {
          const delay = this.retryDelayBase * Math.pow(2, attempt - 1) * 1000;
          console.log(`  [coordinator] Retry ${attempt}/${this.maxRetries} after ${(delay / 1000).toFixed(1)}s...`);
          await new Promise((r) => setTimeout(r, delay));
        }

        // Step 1: SQLite
        if (!sqliteSuccess) {
          this.sentenceStore.insertSentences(docId, sentences as { id: string; page_num: number; paragraph_id: string; sentence_id: string; text: string; char_offset_start: number; char_offset_end: number; item_type?: string }[]);
          sqliteSuccess = true;
          console.log(`    [sqlite] ${sentences.length} sentences`);
        }

        // Step 2: Milvus
        if (!milvusSuccess) {
          await this.vectorIndex.insertVectors(
            sentences as { id: string; text: string; page_num: number; paragraph_id: string }[],
            docId,
          );
          milvusSuccess = true;
          console.log(`    [milvus] ${sentences.length} vectors`);
        }

        // Step 3: Elasticsearch
        if (!esSuccess) {
          await this.bm25Index.indexSentences(
            sentences as { id: string; text: string; page_num: number; paragraph_id: string; item_type?: string }[],
            docId,
          );
          esSuccess = true;
          console.log(`    [elasticsearch] ${sentences.length} docs`);
        }

        console.log(`  [coordinator] Batch completed successfully`);
        return true;
      } catch (e) {
        console.error(`  [coordinator] Attempt ${attempt + 1} failed:`, e);
        if (attempt < this.maxRetries) continue;
      }
    }

    // Rollback
    console.log(`  [coordinator] Rolling back successful layers...`);
    await this.rollbackBatch(batch, sqliteSuccess, milvusSuccess, esSuccess);

    const failedBatch: IngestionBatch = { ...batch, retryCount: this.maxRetries };
    this.failedBatches = [...this.failedBatches, failedBatch];

    return false;
  }

  private async rollbackBatch(
    batch: IngestionBatch,
    sqliteSuccess: boolean,
    milvusSuccess: boolean,
    esSuccess: boolean,
  ): Promise<void> {
    const sentenceIds = batch.sentences.map((s) => s.id as string);

    if (sqliteSuccess) {
      try {
        for (const sid of sentenceIds) {
          this.sentenceStore.deleteSentence(sid);
        }
      } catch (e) {
        console.error("    [rollback] SQLite cleanup failed:", e);
      }
    }

    if (milvusSuccess) {
      try {
        await this.vectorIndex.deleteByDocId(batch.docId);
      } catch (e) {
        console.error("    [rollback] Milvus cleanup failed:", e);
      }
    }

    if (esSuccess) {
      try {
        await this.bm25Index.deleteByDocId(batch.docId);
      } catch (e) {
        console.error("    [rollback] ES cleanup failed:", e);
      }
    }
  }

  getFailedBatches(): readonly IngestionBatch[] {
    return this.failedBatches;
  }

  async retryFailedBatches(): Promise<number> {
    if (this.failedBatches.length === 0) return 0;

    console.log(`[coordinator] Retrying ${this.failedBatches.length} failed batches...`);
    let recovered = 0;
    const stillFailed: IngestionBatch[] = [];

    for (const batch of this.failedBatches) {
      const retryBatch: IngestionBatch = { ...batch, retryCount: 0 };
      if (await this.ingestBatch(retryBatch)) {
        recovered++;
      } else {
        stillFailed.push(batch);
      }
    }

    this.failedBatches = stillFailed;
    console.log(`[coordinator] Recovered ${recovered}/${recovered + stillFailed.length} batches`);
    return recovered;
  }
}
