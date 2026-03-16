import { Database } from "bun:sqlite";
import { randomUUID } from "crypto";
import { join } from "path";
import { mkdirSync, existsSync } from "fs";
import { getWorkspaceDir } from "../../config/settings.js";

export interface SentenceRow {
  readonly id: string;
  readonly doc_id: string;
  readonly page_num: number;
  readonly paragraph_id: string;
  readonly sentence_id: string;
  readonly text: string;
  readonly char_offset_start: number;
  readonly char_offset_end: number;
  readonly item_type: string;
  readonly created_at: string;
  readonly filename?: string;
}

export interface DocumentRow {
  readonly doc_id: string;
  readonly filename: string;
  readonly total_pages: number;
  readonly status: string;
  readonly doc_metadata: Record<string, unknown>;
  readonly created_at: string;
}

export interface ChatMessageRow {
  readonly id: string;
  readonly session_id: string;
  readonly role: string;
  readonly content: string;
  readonly sources: Record<string, unknown>[] | null;
  readonly created_at: string;
}

export class SQLiteStore {
  private readonly db: Database;

  constructor(dbPath?: string) {
    const resolvedPath = dbPath ?? this.defaultDbPath();
    this.db = new Database(resolvedPath);
    this.db.exec("PRAGMA journal_mode = WAL");
    this.db.exec("PRAGMA foreign_keys = ON");
    this.initDb();
    console.log(`[sqlite] Connected to ${resolvedPath}`);
  }

  private defaultDbPath(): string {
    const workspace = getWorkspaceDir();
    const dbDir = join(workspace, "database");
    if (!existsSync(dbDir)) {
      mkdirSync(dbDir, { recursive: true });
    }
    return join(dbDir, "aletheia.db");
  }

  private initDb(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS documents (
        doc_id TEXT PRIMARY KEY,
        filename TEXT NOT NULL,
        total_pages INTEGER NOT NULL,
        status TEXT DEFAULT 'processing',
        doc_metadata TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    this.db.exec(`
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
    `);

    this.db.exec(`
      CREATE TABLE IF NOT EXISTS chat_messages (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        sources TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    this.db.exec(`CREATE INDEX IF NOT EXISTS idx_sentences_doc_id ON sentences(doc_id)`);
    this.db.exec(`CREATE INDEX IF NOT EXISTS idx_sentences_page_num ON sentences(doc_id, page_num)`);
    this.db.exec(`CREATE INDEX IF NOT EXISTS idx_sentences_paragraph ON sentences(doc_id, paragraph_id)`);
    this.db.exec(`CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_messages(session_id)`);
    this.db.exec(`CREATE INDEX IF NOT EXISTS idx_sentences_offset ON sentences(doc_id, char_offset_start)`);

    // Migration: Add status column if not exists
    try {
      const columns = this.db.prepare("PRAGMA table_info(documents)").all() as { name: string }[];
      const hasStatus = columns.some((c) => c.name === "status");
      if (!hasStatus) {
        this.db.exec("ALTER TABLE documents ADD COLUMN status TEXT DEFAULT 'processing'");
        console.log("[sqlite] Migrated: Added status column to documents table");
      }
    } catch {
      // Ignore migration errors for fresh databases
    }
  }

  // ============== Document Operations ==============

  insertDocument(filename: string, totalPages: number, metadata?: Record<string, unknown>, status = "processing"): string {
    const docId = randomUUID();
    this.db.prepare(`
      INSERT INTO documents (doc_id, filename, total_pages, status, doc_metadata)
      VALUES (?, ?, ?, ?, ?)
    `).run(docId, filename, totalPages, status, JSON.stringify(metadata ?? {}));
    console.log(`[sqlite] Inserted document: ${filename} (${docId}, status: ${status})`);
    return docId;
  }

  updateDocumentStatus(docId: string, status: string): void {
    this.db.prepare("UPDATE documents SET status = ? WHERE doc_id = ?").run(status, docId);
    console.log(`[sqlite] Updated document ${docId} status to: ${status}`);
  }

  getDocument(docId: string): DocumentRow | null {
    const row = this.db.prepare(`
      SELECT doc_id, filename, total_pages, status, doc_metadata, created_at
      FROM documents WHERE doc_id = ?
    `).get(docId) as { doc_id: string; filename: string; total_pages: number; status: string; doc_metadata: string; created_at: string } | null;

    if (!row) return null;
    return {
      doc_id: row.doc_id,
      filename: row.filename,
      total_pages: row.total_pages,
      status: row.status ?? "processing",
      doc_metadata: row.doc_metadata ? JSON.parse(row.doc_metadata) : {},
      created_at: row.created_at,
    };
  }

  deleteDocument(docId: string): void {
    this.db.prepare("DELETE FROM documents WHERE doc_id = ?").run(docId);
    console.log(`[sqlite] Deleted document: ${docId}`);
  }

  getAllDocuments(): DocumentRow[] {
    const rows = this.db.prepare(`
      SELECT doc_id, filename, total_pages, status, doc_metadata, created_at
      FROM documents ORDER BY created_at DESC
    `).all() as { doc_id: string; filename: string; total_pages: number; status: string; doc_metadata: string; created_at: string }[];

    return rows.map((row) => ({
      doc_id: row.doc_id,
      filename: row.filename,
      total_pages: row.total_pages,
      status: row.status ?? "processing",
      doc_metadata: row.doc_metadata ? JSON.parse(row.doc_metadata) : {},
      created_at: row.created_at,
    }));
  }

  // ============== Sentence Operations ==============

  insertSentences(docId: string, sentences: readonly { id: string; page_num: number; paragraph_id: string; sentence_id: string; text: string; char_offset_start: number; char_offset_end: number; item_type?: string }[]): void {
    const stmt = this.db.prepare(`
      INSERT INTO sentences (id, doc_id, page_num, paragraph_id, sentence_id, text, char_offset_start, char_offset_end, item_type)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    const insertAll = this.db.transaction(() => {
      for (const s of sentences) {
        stmt.run(s.id, docId, s.page_num, s.paragraph_id, s.sentence_id, s.text, s.char_offset_start, s.char_offset_end, s.item_type ?? "paragraph");
      }
    });

    insertAll();
    console.log(`[sqlite] Inserted ${sentences.length} sentences for doc_id: ${docId}`);
  }

  getSentenceById(sentenceId: string): SentenceRow | null {
    const row = this.db.prepare(`
      SELECT s.id, s.doc_id, s.page_num, s.paragraph_id, s.sentence_id, s.text,
             s.char_offset_start, s.char_offset_end, s.item_type, s.created_at,
             d.filename
      FROM sentences s
      JOIN documents d ON s.doc_id = d.doc_id
      WHERE s.id = ?
    `).get(sentenceId) as SentenceRow | null;
    return row ?? null;
  }

  getSentencesByDoc(docId: string, pageNum?: number): SentenceRow[] {
    if (pageNum !== undefined) {
      return this.db.prepare(`
        SELECT id, doc_id, page_num, paragraph_id, sentence_id, text,
               char_offset_start, char_offset_end, item_type, created_at
        FROM sentences WHERE doc_id = ? AND page_num = ?
        ORDER BY page_num, char_offset_start
      `).all(docId, pageNum) as SentenceRow[];
    }

    return this.db.prepare(`
      SELECT id, doc_id, page_num, paragraph_id, sentence_id, text,
             char_offset_start, char_offset_end, item_type, created_at
      FROM sentences WHERE doc_id = ?
      ORDER BY page_num, char_offset_start
    `).all(docId) as SentenceRow[];
  }

  getSentencesByIds(sentenceIds: readonly string[]): SentenceRow[] {
    if (sentenceIds.length === 0) return [];

    const placeholders = sentenceIds.map(() => "?").join(",");
    return this.db.prepare(`
      SELECT s.id, s.doc_id, s.page_num, s.paragraph_id, s.sentence_id, s.text,
             s.char_offset_start, s.char_offset_end, s.item_type, s.created_at,
             d.filename
      FROM sentences s
      JOIN documents d ON s.doc_id = d.doc_id
      WHERE s.id IN (${placeholders})
    `).all(...sentenceIds) as SentenceRow[];
  }

  deleteSentence(sentenceId: string): boolean {
    try {
      this.db.prepare("DELETE FROM sentences WHERE id = ?").run(sentenceId);
      return true;
    } catch (e) {
      console.error(`[sqlite] Failed to delete sentence ${sentenceId}:`, e);
      return false;
    }
  }

  pageExists(docId: string, pageNum: number): boolean {
    const row = this.db.prepare(`
      SELECT EXISTS(SELECT 1 FROM sentences WHERE doc_id = ? AND page_num = ?) as exists_flag
    `).get(docId, pageNum) as { exists_flag: number } | null;
    return (row?.exists_flag ?? 0) === 1;
  }

  // ============== Context Retrieval ==============

  getContextWindow(docId: string, sentenceId: string, windowSize = 2): SentenceRow[] {
    return this.db.prepare(`
      WITH OrderedSentences AS (
        SELECT id, doc_id, page_num, paragraph_id, sentence_id, text,
               char_offset_start, char_offset_end, item_type, created_at,
               ROW_NUMBER() OVER (ORDER BY page_num, char_offset_start) as rn
        FROM sentences WHERE doc_id = ?
      ),
      TargetSentence AS (
        SELECT rn FROM OrderedSentences WHERE id = ?
      )
      SELECT os.id, os.doc_id, os.page_num, os.paragraph_id, os.sentence_id, os.text,
             os.char_offset_start, os.char_offset_end, os.item_type, os.created_at
      FROM OrderedSentences os, TargetSentence ts
      WHERE os.rn BETWEEN ts.rn - ? AND ts.rn + ?
      ORDER BY os.rn ASC
    `).all(docId, sentenceId, windowSize, windowSize) as SentenceRow[];
  }

  getParagraphContext(docId: string, paragraphId: string): SentenceRow[] {
    return this.db.prepare(`
      SELECT id, doc_id, page_num, paragraph_id, sentence_id, text,
             char_offset_start, char_offset_end, item_type, created_at
      FROM sentences
      WHERE doc_id = ? AND paragraph_id = ?
      ORDER BY page_num ASC, char_offset_start ASC
    `).all(docId, paragraphId) as SentenceRow[];
  }

  getPrecedingParagraphs(docId: string, targetParagraphId: string): { paragraph_id: string; page_num: number; text: string; rank: number }[] {
    return this.db.prepare(`
      WITH OrderedParagraphs AS (
        SELECT paragraph_id,
               MIN(page_num) as page_num,
               MIN(char_offset_start) as start_offset,
               GROUP_CONCAT(text, ' ') as full_text,
               ROW_NUMBER() OVER (ORDER BY MIN(page_num), MIN(char_offset_start)) as rn
        FROM sentences WHERE doc_id = ?
        GROUP BY paragraph_id
      ),
      TargetRank AS (
        SELECT rn FROM OrderedParagraphs WHERE paragraph_id = ?
      )
      SELECT op.paragraph_id, op.page_num, op.full_text as text, op.rn as rank
      FROM OrderedParagraphs op, TargetRank tr
      WHERE op.rn <= tr.rn
      ORDER BY op.rn ASC
    `).all(docId, targetParagraphId) as { paragraph_id: string; page_num: number; text: string; rank: number }[];
  }

  // ============== Batch Operations ==============

  getParagraphContextBatch(sentenceIds: readonly string[]): Record<string, SentenceRow[]> {
    if (sentenceIds.length === 0) return {};

    const placeholders = sentenceIds.map(() => "?").join(",");
    try {
      const rows = this.db.prepare(`
        WITH target_sentences AS (
          SELECT id, doc_id, paragraph_id FROM sentences WHERE id IN (${placeholders})
        )
        SELECT t.id as target_id,
               s.id, s.doc_id, s.page_num, s.paragraph_id, s.sentence_id, s.text,
               s.char_offset_start, s.char_offset_end, s.item_type, s.created_at
        FROM target_sentences t
        JOIN sentences s ON (s.doc_id = t.doc_id AND s.paragraph_id = t.paragraph_id)
        ORDER BY t.id, s.char_offset_start
      `).all(...sentenceIds) as (SentenceRow & { target_id: string })[];

      const result: Record<string, SentenceRow[]> = {};
      for (const row of rows) {
        const targetId = row.target_id;
        if (!result[targetId]) {
          result[targetId] = [];
        }
        result[targetId].push({
          id: row.id,
          doc_id: row.doc_id,
          page_num: row.page_num,
          paragraph_id: row.paragraph_id,
          sentence_id: row.sentence_id,
          text: row.text,
          char_offset_start: row.char_offset_start,
          char_offset_end: row.char_offset_end,
          item_type: row.item_type,
          created_at: row.created_at,
        });
      }
      return result;
    } catch (e) {
      console.error("[sqlite] Batch context fetch error:", e);
      return Object.fromEntries(sentenceIds.map((sid) => [sid, []]));
    }
  }

  getSentencesByIdsBatch(sentenceIds: readonly string[]): Record<string, SentenceRow | null> {
    if (sentenceIds.length === 0) return {};

    const placeholders = sentenceIds.map(() => "?").join(",");
    try {
      const rows = this.db.prepare(`
        SELECT s.id, s.doc_id, s.page_num, s.paragraph_id, s.sentence_id, s.text,
               s.char_offset_start, s.char_offset_end, s.item_type, s.created_at,
               d.filename
        FROM sentences s
        JOIN documents d ON s.doc_id = d.doc_id
        WHERE s.id IN (${placeholders})
      `).all(...sentenceIds) as SentenceRow[];

      const result: Record<string, SentenceRow | null> = {};
      for (const row of rows) {
        result[row.id] = row;
      }
      for (const sid of sentenceIds) {
        if (!(sid in result)) {
          result[sid] = null;
        }
      }
      return result;
    } catch (e) {
      console.error("[sqlite] Batch sentence fetch error:", e);
      const result: Record<string, SentenceRow | null> = {};
      for (const sid of sentenceIds) {
        result[sid] = this.getSentenceById(sid);
      }
      return result;
    }
  }

  // ============== Chat History ==============

  insertChatMessage(sessionId: string, role: string, content: string, sources?: Record<string, unknown>[]): string {
    const msgId = randomUUID();
    this.db.prepare(`
      INSERT INTO chat_messages (id, session_id, role, content, sources)
      VALUES (?, ?, ?, ?, ?)
    `).run(msgId, sessionId, role, content, sources ? JSON.stringify(sources) : null);
    return msgId;
  }

  getChatHistory(sessionId: string, limit = 50): ChatMessageRow[] {
    const rows = this.db.prepare(`
      SELECT id, session_id, role, content, sources, created_at
      FROM chat_messages WHERE session_id = ?
      ORDER BY created_at ASC LIMIT ?
    `).all(sessionId, limit) as { id: string; session_id: string; role: string; content: string; sources: string | null; created_at: string }[];

    return rows.map((row) => ({
      id: row.id,
      session_id: row.session_id,
      role: row.role,
      content: row.content,
      sources: row.sources ? JSON.parse(row.sources) : null,
      created_at: row.created_at,
    }));
  }

  deleteChatSession(sessionId: string): void {
    this.db.prepare("DELETE FROM chat_messages WHERE session_id = ?").run(sessionId);
  }

  // ============== Utility ==============

  getStats(): { documents: number; sentences: number; chat_messages: number } {
    const docs = this.db.prepare("SELECT COUNT(*) as count FROM documents").get() as { count: number };
    const sents = this.db.prepare("SELECT COUNT(*) as count FROM sentences").get() as { count: number };
    const chats = this.db.prepare("SELECT COUNT(*) as count FROM chat_messages").get() as { count: number };

    return {
      documents: docs.count,
      sentences: sents.count,
      chat_messages: chats.count,
    };
  }

  vacuum(): void {
    this.db.exec("VACUUM");
    console.log("[sqlite] Database optimized");
  }

  close(): void {
    this.db.close();
    console.log("[sqlite] Connection closed");
  }
}

export function createSqliteStore(dbPath?: string): SQLiteStore {
  return new SQLiteStore(dbPath);
}
