/**
 * REST API client for the Aletheia daemon.
 *
 * All methods use Next.js rewrite rules so the browser talks to /api/v1/*
 * (no CORS issue) which Next.js proxies to http://localhost:8000/api/v1/*.
 */

import type {
  HealthResponse,
  StatusResponse,
  Document,
  DocumentListResponse,
} from '@/types';

const BASE = '/api/v1';

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ─── System ──────────────────────────────────────────────────────────────────

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch('/health');
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}

export async function fetchStatus(): Promise<StatusResponse> {
  return request<StatusResponse>('/status');
}

// ─── Documents ───────────────────────────────────────────────────────────────

export async function listDocuments(): Promise<DocumentListResponse> {
  return request<DocumentListResponse>('/documents');
}

export async function getDocument(id: string): Promise<Document> {
  return request<Document>(`/documents/${id}`);
}

export async function uploadDocument(file: File): Promise<Document> {
  const form = new FormData();
  form.append('file', file);
  return request<Document>('/documents', { method: 'POST', body: form });
}

export async function deleteDocument(id: string): Promise<void> {
  await request<unknown>(`/documents/${id}`, { method: 'DELETE' });
}

// ─── Chat (HTTP SSE fallback) ─────────────────────────────────────────────────

/**
 * Send a chat message and receive a streaming SSE response.
 *
 * @param message     User message text.
 * @param onChunk     Called for each streamed text chunk.
 * @param onDone      Called when streaming is complete with optional sources.
 * @param onError     Called on error.
 */
export async function sendChatSSE(
  message: string,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (err: string) => void,
  sessionId?: string,
): Promise<void> {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId, stream: true }),
  });

  if (!res.ok || !res.body) {
    onError(`HTTP ${res.status}`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const raw = decoder.decode(value, { stream: true });
    for (const line of raw.split('\n')) {
      if (!line.startsWith('data: ')) continue;
      try {
        const payload = JSON.parse(line.slice(6));
        if (payload.error) {
          onError(payload.error);
          return;
        }
        if (payload.done) {
          onDone();
          return;
        }
        if (payload.content) {
          onChunk(payload.content);
        }
      } catch {
        // malformed line – skip
      }
    }
  }

  onDone();
}
