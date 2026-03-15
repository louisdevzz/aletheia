'use client';

import { useState } from 'react';
import { Sidebar } from '@/components/ui/Sidebar';
import { ChatWindow } from '@/components/chat/ChatWindow';
import { ChatInput } from '@/components/chat/ChatInput';
import { ProviderSelector } from '@/components/ProviderSelector';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useDocuments } from '@/hooks/useDocuments';

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  
  const {
    messages,
    status,
    provider,
    setProvider,
    sendMessage,
    clearMessages,
  } = useWebSocket();

  const {
    documents,
    loading: docsLoading,
    error: docsError,
    upload,
    remove,
    refresh,
  } = useDocuments();

  const isConnected = status === 'connected';
  const isStreaming = messages.some((m) => m.streaming);

  return (
    <div className="flex h-full bg-[#0d0d0d]">
      {/* Sidebar */}
      {sidebarOpen && (
        <Sidebar
          connectionStatus={status}
          documents={documents}
          documentsLoading={docsLoading}
          documentsError={docsError}
          onUpload={upload}
          onDelete={remove}
          onRefreshDocuments={refresh}
          onClearChat={clearMessages}
        />
      )}

      {/* Main chat area */}
      <main className="flex flex-1 flex-col overflow-hidden relative">
        {/* Header */}
        <header className="flex items-center justify-between border-b border-white/10 px-4 py-3 bg-[#0d0d0d]">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="rounded-lg p-2 text-white/50 hover:bg-white/10 hover:text-white transition"
              title={sidebarOpen ? 'Ẩn sidebar' : 'Hiện sidebar'}
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                {sidebarOpen ? (
                  <path d="M11 17l-5-5 5-5M18 17l-5-5 5-5" />
                ) : (
                  <path d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-[#10a37f] to-[#19c59f]"
              >
                <svg className="h-4 w-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                >
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                </svg>
              </div>
              <span className="text-sm font-medium text-white">Aletheia RAG</span>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <ProviderSelector
              value={provider}
              onChange={setProvider}
              disabled={isStreaming}
            />
            {!isConnected && (
              <span className="rounded-lg bg-yellow-500/10 px-3 py-1 text-xs text-yellow-500 border border-yellow-500/20"
              >
                {status === 'connecting' ? 'Đang kết nối...' : 'Mất kết nối'}
              </span>
            )}
          </div>
        </header>

        {/* Messages */}
        <ChatWindow messages={messages} hasDocuments={documents.length > 0} />

        {/* Input */}
        <ChatInput
          onSend={sendMessage}
          disabled={!isConnected || isStreaming}
          placeholder={
            !isConnected
              ? 'Đang chờ kết nối...'
              : isStreaming
              ? 'Đang phản hồi...'
              : documents.length === 0
              ? 'Vui lòng upload tài liệu trước...'
              : 'Nhập câu hỏi về tài liệu...'
          }
        />
      </main>
    </div>
  );
}
