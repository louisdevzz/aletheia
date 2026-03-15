'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';

import { AletheiaWebSocket } from '@/lib/websocket';
import type { ConnectionStatus, Message, Source, LLMProvider } from '@/types';

const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL
    ? `${process.env.NEXT_PUBLIC_WS_URL}/ws/chat`
    : 'ws://localhost:8000/ws/chat';

export function useWebSocket() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [sessionId] = useState<string>(() => uuidv4());
  const [isPageReady, setIsPageReady] = useState(false);
  const [provider, setProvider] = useState<LLMProvider>('kimi');

  const wsRef = useRef<AletheiaWebSocket | null>(null);
  // Track the id of the assistant message currently being streamed
  const streamingIdRef = useRef<string | null>(null);

  // Wait for page to be fully loaded before connecting WebSocket
  useEffect(() => {
    // Small delay to ensure page is fully hydrated
    const timer = setTimeout(() => {
      setIsPageReady(true);
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!isPageReady) return;

    setStatus('connecting');

    const ws = new AletheiaWebSocket(WS_URL, {
      onOpen: () => setStatus('connected'),

      onChunk: (payload) => {
        console.log('[WebSocket] Chunk received:', { done: payload.done, content: payload.content?.slice(0, 20), streamingId: streamingIdRef.current });
        
        if (payload.done) {
          // Finalise the streaming message
          if (streamingIdRef.current) {
            const messageId = streamingIdRef.current;
            setMessages((prev) => {
              const updated = prev.map((m) =>
                m.id === messageId
                  ? { ...m, streaming: false, sources: (payload.sources ?? []) as Source[] }
                  : m,
              );
              console.log('[WebSocket] Message finalized:', messageId, 'streaming count:', updated.filter(m => m.streaming).length);
              return updated;
            });
            streamingIdRef.current = null;
          }
          return;
        }

        if (streamingIdRef.current === null) {
          // Start a new streaming assistant message
          const id = uuidv4();
          streamingIdRef.current = id;
          console.log('[WebSocket] Creating new assistant message:', id, 'with content:', payload.content);
          setMessages((prev) => {
            const updated = [
              ...prev,
              {
                id,
                role: 'assistant',
                content: payload.content,
                timestamp: new Date(),
                streaming: true,
              },
            ];
            console.log('[WebSocket] Messages after create:', updated.map(m => ({ id: m.id.slice(0,8), role: m.role, content: m.content.slice(0,20) })));
            return updated;
          });
        } else {
          // Append chunk to the existing streaming message
          const messageId = streamingIdRef.current;
          console.log('[WebSocket] Appending to message:', messageId, 'chunk:', payload.content);
          setMessages((prev) => {
            const updated = prev.map((m) =>
              m.id === messageId
                ? { ...m, content: m.content + payload.content }
                : m,
            );
            const targetMsg = updated.find(m => m.id === messageId);
            console.log('[WebSocket] Messages after append:', updated.map(m => ({ id: m.id.slice(0,8), role: m.role, content: m.content.slice(0,30) })), 'target:', targetMsg?.content.slice(0,30));
            return updated;
          });
        }
      },

      onError: (msg) => {
        setStatus('error');
        setMessages((prev) => [
          ...prev,
          {
            id: uuidv4(),
            role: 'assistant',
            content: `Error: ${msg}`,
            timestamp: new Date(),
          },
        ]);
        streamingIdRef.current = null;
      },

      onClose: () => setStatus('disconnected'),
    });

    ws.connect();
    wsRef.current = ws;

    return () => {
      ws.disconnect();
    };
  }, [isPageReady]);

  const sendMessage = useCallback(
    (text: string) => {
      const ws = wsRef.current;
      if (!ws?.isOpen()) {
        setStatus('error');
        return;
      }

      // Add user message immediately
      setMessages((prev) => [
        ...prev,
        {
          id: uuidv4(),
          role: 'user',
          content: text,
          timestamp: new Date(),
        },
      ]);

      ws.sendMessage(text, sessionId, provider);
    },
    [sessionId, provider],
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    streamingIdRef.current = null;
  }, []);

  return { 
    messages, 
    status, 
    sessionId, 
    provider,
    setProvider,
    sendMessage, 
    clearMessages 
  };
}
