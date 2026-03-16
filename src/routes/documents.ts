import { Hono } from "hono";
import { existsSync, mkdirSync, unlinkSync } from "fs";
import { join } from "path";
import { randomUUID } from "crypto";
import { SQLiteStore } from "../rag/storage/sqlite-store.js";
import { IngestionPipeline } from "../rag/pipeline/ingestion-pipeline.js";

const documents = new Hono();

const UPLOAD_DIR = "./uploads";
if (!existsSync(UPLOAD_DIR)) {
  mkdirSync(UPLOAD_DIR, { recursive: true });
}

// Broadcast function for WebSocket notifications
let broadcastFn: ((data: Record<string, unknown>) => void) | null = null;
export function setBroadcast(fn: (data: Record<string, unknown>) => void): void {
  broadcastFn = fn;
}

documents.post("/documents", async (c) => {
  const body = await c.req.parseBody();
  const file = body.file;

  if (!file || typeof file === "string") {
    return c.json({ error: "File is required" }, 400);
  }

  const filename = (file as File).name;
  if (!filename.endsWith(".pdf")) {
    return c.json({ error: "Only PDF files are supported" }, 400);
  }

  const tempDocId = randomUUID();
  const filePath = join(UPLOAD_DIR, `${tempDocId}_${filename}`);

  try {
    const arrayBuffer = await (file as File).arrayBuffer();
    await Bun.write(filePath, arrayBuffer);
  } catch (e) {
    return c.json({ error: `Failed to save file: ${e instanceof Error ? e.message : String(e)}` }, 500);
  }

  const storage = new SQLiteStore();
  const docId = storage.insertDocument(filename, 0, { source_path: filePath }, "processing");

  const newFilePath = join(UPLOAD_DIR, `${docId}_${filename}`);
  try {
    const { renameSync } = await import("fs");
    renameSync(filePath, newFilePath);
  } catch {
    // If rename fails, use original path
  }

  // Background ingestion
  ingestDocumentTask(newFilePath, docId, filename).catch(console.error);

  storage.close();

  return c.json({
    doc_id: docId,
    filename,
    total_pages: 0,
    created_at: new Date().toISOString(),
    status: "processing",
  }, 201);
});

async function ingestDocumentTask(filePath: string, docId: string, filename: string): Promise<void> {
  const storage = new SQLiteStore();
  try {
    const pipeline = new IngestionPipeline();
    await pipeline.setupIndices(false);
    const resultDocId = await pipeline.ingestDocument(filePath, filename, docId);
    storage.updateDocumentStatus(docId, "completed");
    console.log(`[documents] Ingested: ${filename} (ID: ${resultDocId})`);

    broadcastFn?.({
      type: "document.ingested",
      doc_id: docId,
      filename,
      status: "completed",
    });

    pipeline.close();
  } catch (e) {
    storage.updateDocumentStatus(docId, "failed");
    console.error(`[documents] Failed to ingest ${filename}:`, e);

    broadcastFn?.({
      type: "document.ingested",
      doc_id: docId,
      filename,
      status: "failed",
      error: e instanceof Error ? e.message : String(e),
    });
  } finally {
    storage.close();
    try {
      unlinkSync(filePath);
    } catch {
      // ignore cleanup errors
    }
  }
}

documents.get("/documents", async (c) => {
  const storage = new SQLiteStore();
  try {
    const docs = storage.getAllDocuments();
    return c.json({
      documents: docs.map((doc) => ({
        doc_id: doc.doc_id,
        filename: doc.filename,
        total_pages: doc.total_pages,
        created_at: doc.created_at,
        status: doc.status ?? "completed",
      })),
    });
  } catch (e) {
    return c.json({ error: String(e) }, 500);
  } finally {
    storage.close();
  }
});

documents.get("/documents/:docId", async (c) => {
  const docId = c.req.param("docId");
  const storage = new SQLiteStore();
  try {
    const doc = storage.getDocument(docId);
    if (!doc) {
      return c.json({ error: "Document not found" }, 404);
    }
    return c.json({
      doc_id: doc.doc_id,
      filename: doc.filename,
      total_pages: doc.total_pages,
      created_at: doc.created_at,
      status: doc.status ?? "completed",
    });
  } catch (e) {
    return c.json({ error: String(e) }, 500);
  } finally {
    storage.close();
  }
});

documents.delete("/documents/:docId", async (c) => {
  const docId = c.req.param("docId");
  try {
    const pipeline = new IngestionPipeline();
    await pipeline.deleteDocument(docId);
    pipeline.close();
    return c.json({ message: "Document deleted successfully" });
  } catch (e) {
    return c.json({ error: String(e) }, 500);
  }
});

export { documents };
