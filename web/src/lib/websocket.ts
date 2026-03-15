/**
 * WebSocket client helper.
 *
 * Wraps the native WebSocket to provide a typed interface that matches the
 * Aletheia daemon WebSocket protocol (Phase 2).
 */

import type {
  WsClientMessage,
  WsServerMessage,
  WsChunkMessage,
  WsErrorMessage,
  LLMProvider,
} from '@/types';

export type WsEventHandlers = {
  onOpen?: () => void;
  onChunk?: (payload: WsChunkMessage['payload']) => void;
  onError?: (message: string) => void;
  onClose?: () => void;
};

export class AletheiaWebSocket {
  private ws: WebSocket | null = null;
  private readonly url: string;
  private handlers: WsEventHandlers;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = true;

  constructor(url: string, handlers: WsEventHandlers = {}) {
    this.url = url;
    this.handlers = handlers;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      this.handlers.onOpen?.();
    };

    this.ws.onmessage = (event: MessageEvent) => {
      let msg: WsServerMessage;
      try {
        msg = JSON.parse(event.data as string) as WsServerMessage;
      } catch {
        console.error('[AletheiaWS] Received non-JSON frame:', event.data);
        return;
      }

      if (msg.type === 'chat.chunk') {
        this.handlers.onChunk?.((msg as WsChunkMessage).payload);
      } else if (msg.type === 'error') {
        this.handlers.onError?.((msg as WsErrorMessage).payload.message);
      }
    };

    this.ws.onerror = () => {
      this.handlers.onError?.('WebSocket connection error');
    };

    this.ws.onclose = () => {
      this.handlers.onClose?.();
      if (this.shouldReconnect) {
        this.reconnectTimer = setTimeout(() => this.connect(), 3000);
      }
    };
  }

  sendMessage(message: string, sessionId?: string, provider?: LLMProvider): void {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket is not connected');
    }

    const frame: WsClientMessage = {
      type: 'chat.message',
      payload: { message, session_id: sessionId, provider },
    };
    this.ws.send(JSON.stringify(frame));
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
  }

  get readyState(): number {
    return this.ws?.readyState ?? WebSocket.CLOSED;
  }

  isOpen(): boolean {
    return this.readyState === WebSocket.OPEN;
  }
}
