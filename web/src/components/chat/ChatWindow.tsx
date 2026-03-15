'use client';

import { useEffect, useRef } from 'react';
import { MessageBubble } from './MessageBubble';
import type { Message } from '@/types';

interface ChatWindowProps {
  messages: Message[];
  hasDocuments: boolean;
}

export function ChatWindow({ messages, hasDocuments }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center px-4 py-8">
        <div className="text-center max-w-md">
          <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-[#10a37f] to-[#19c59f] mx-auto">
            <svg className="h-8 w-8 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
          </div>
          <h2 className="mb-2 text-2xl font-semibold text-white">Aletheia RAG</h2>
          <p className="mb-4 text-white/60">
            {hasDocuments 
              ? 'Hệ thống đã sẵn sàng. Hãy đặt câu hỏi về tài liệu của bạn.'
              : 'Vui lòng upload PDF để bắt đầu trò chuyện với tài liệu.'}
          </p>
          {!hasDocuments && (
            <div className="rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-sm text-white/50">
              📎 Sử dụng sidebar bên trái để upload tài liệu
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div 
      ref={containerRef}
      className="flex-1 overflow-y-auto"
    >
      <div className="mx-auto max-w-3xl px-4 py-6 space-y-6">
        {messages.map((msg, index) => (
          <MessageBubble 
            key={msg.id} 
            message={msg}
            isLatest={index === messages.length - 1}
          />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
