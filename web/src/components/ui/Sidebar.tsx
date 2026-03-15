'use client';

import { useState } from 'react';
import { StatusBadge } from './StatusBadge';
import type { ConnectionStatus, Document } from '@/types';

interface SidebarProps {
  connectionStatus: ConnectionStatus;
  documents: Document[];
  documentsLoading: boolean;
  documentsError: string | null;
  onUpload: (file: File) => void;
  onDelete: (id: string) => void;
  onRefreshDocuments: () => void;
  onClearChat: () => void;
}

export function Sidebar({
  connectionStatus,
  documents,
  documentsLoading,
  documentsError,
  onUpload,
  onDelete,
  onRefreshDocuments,
  onClearChat,
}: SidebarProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [isExpanded, setIsExpanded] = useState(true);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setIsUploading(true);
      onUpload(file);
      setTimeout(() => setIsUploading(false), 1000);
    }
  };

  return (
    <aside
      className={`flex h-full flex-col border-r border-white/10 bg-[#0d0d0d] transition-all duration-300 ${
        isExpanded ? 'w-72' : 'w-16'
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-3">
        {isExpanded ? (
          <>
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[#10a37f] to-[#19c59f]">
                <svg className="h-4 w-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                </svg>
              </div>
              <span className="font-semibold text-white">Aletheia</span>
            </div>
            <button
              onClick={() => setIsExpanded(false)}
              className="rounded-lg p-1.5 text-white/50 hover:bg-white/10 hover:text-white transition"
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M11 17l-5-5 5-5M18 17l-5-5 5-5" />
              </svg>
            </button>
          </>
        ) : (
          <button
            onClick={() => setIsExpanded(true)}
            className="mx-auto rounded-lg p-1.5 text-white/50 hover:bg-white/10 hover:text-white transition"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M13 17l5-5-5-5M6 17l5-5-5-5" />
            </svg>
          </button>
        )}
      </div>

      {/* New Chat Button */}
      {isExpanded && (
        <div className="px-3 pb-3">
          <button
            onClick={onClearChat}
            className="btn-glow flex w-full items-center gap-2 rounded-lg border border-white/20 bg-transparent px-3 py-2.5 text-sm text-white transition hover:bg-white/5"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 4v16m8-8H4" />
            </svg>
            New chat
          </button>
        </div>
      )}

      {/* Scrollable Content */}
      {isExpanded && (
        <div className="flex-1 overflow-y-auto px-3">
          {/* Connection Status */}
          <div className="mb-4">
            <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-white/40">
              Connection
            </p>
            <StatusBadge status={connectionStatus} />
          </div>

          {/* Documents Section */}
          <div className="mb-4">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-[10px] font-medium uppercase tracking-wider text-white/40">
                Documents
              </p>
              <button
                onClick={onRefreshDocuments}
                disabled={documentsLoading}
                className="rounded p-1 text-white/40 hover:bg-white/10 hover:text-white transition disabled:opacity-50"
              >
                <svg className={`h-3.5 w-3.5 ${documentsLoading ? 'animate-spin' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
            </div>

            {/* Upload Button */}
            <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-white/20 bg-white/5 px-3 py-2.5 text-sm text-white/70 transition hover:border-[#10a37f]/50 hover:bg-[#10a37f]/5 hover:text-white">
              <input
                type="file"
                accept=".pdf"
                onChange={handleFileChange}
                className="hidden"
              />
              {isUploading ? (
                <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              ) : (
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 4v16m8-8H4" />
                </svg>
              )}
              {isUploading ? 'Uploading...' : 'Upload PDF'}
            </label>

            {/* Documents List */}
            <div className="mt-2 space-y-1">
              {documentsError && (
                <p className="rounded-lg bg-red-500/10 px-2 py-1.5 text-xs text-red-400">
                  {documentsError}
                </p>
              )}
              
              {documents.length === 0 && !documentsLoading && !documentsError && (
                <p className="px-2 py-2 text-xs text-white/30 italic">
                  No documents yet
                </p>
              )}

              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="group flex items-center justify-between rounded-lg px-2 py-1.5 hover:bg-white/5 transition"
                >
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <svg className="h-4 w-4 flex-shrink-0 text-white/30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                    </svg>
                    <span className="truncate text-sm text-white/70">
                      {doc.filename}
                    </span>
                  </div>
                  <button
                    onClick={() => onDelete(doc.id)}
                    className="opacity-0 group-hover:opacity-100 rounded p-1 text-white/30 hover:bg-red-500/20 hover:text-red-400 transition"
                  >
                    <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      {isExpanded ? (
        <div className="border-t border-white/10 p-3">
          <div className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-white/5 transition cursor-pointer">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-purple-500 to-pink-500 text-sm font-semibold">
              U
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white">User</p>
              <p className="text-xs text-white/40 truncate">Free plan</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="border-t border-white/10 p-3">
          <button className="mx-auto flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-purple-500 to-pink-500 text-sm font-semibold text-white">
            U
          </button>
        </div>
      )}
    </aside>
  );
}
