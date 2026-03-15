// ─── Domain types ────────────────────────────────────────────────────────────

export interface Source {
  filename: string;
  page_num: number;
  doc_id?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  timestamp: Date;
  /** True while the assistant is still streaming this message */
  streaming?: boolean;
}

export interface Document {
  id: string;
  filename: string;
  status: 'processing' | 'ready' | 'error';
  created_at: string;
  page_count?: number;
}

// ─── REST API response types ─────────────────────────────────────────────────

export interface HealthResponse {
  status: 'healthy' | 'unhealthy';
  version?: string;
}

export interface StorageStats {
  document_count: number;
  sentence_count: number;
}

export interface StatusResponse {
  status: string;
  storage: StorageStats;
}

export interface DocumentResponse extends Document {}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
}

// ─── WebSocket protocol types ─────────────────────────────────────────────────

export type LLMProvider = 'kimi';

export interface WsClientMessage {
  type: 'chat.message';
  payload: {
    message: string;
    session_id?: string;
    provider?: LLMProvider;
  };
}

export interface WsChunkPayload {
  content: string;
  done: boolean;
  sources?: Source[];
}

export interface WsChunkMessage {
  type: 'chat.chunk';
  payload: WsChunkPayload;
}

export interface WsErrorMessage {
  type: 'error';
  payload: {
    message: string;
  };
}

export type WsServerMessage = WsChunkMessage | WsErrorMessage;

// ─── UI state ────────────────────────────────────────────────────────────────

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';
