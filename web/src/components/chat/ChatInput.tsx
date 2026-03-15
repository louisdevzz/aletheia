'use client';

import { KeyboardEvent, useRef, useState } from 'react';

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({
  onSend,
  disabled = false,
  placeholder = 'Nhập câu hỏi về tài liệu...',
}: ChatInputProps) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  };

  return (
    <div className="border-t border-white/10 bg-[#0d0d0d] px-4 py-4">
      <div className="mx-auto max-w-3xl">
        <div className="flex items-end gap-2 rounded-2xl border border-white/20 bg-white/5 px-4 py-3 focus-within:border-[#10a37f]/50 focus-within:ring-1 focus-within:ring-[#10a37f]/20 transition">
          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={handleInput}
            placeholder={placeholder}
            disabled={disabled}
            className="flex-1 resize-none bg-transparent text-sm text-white placeholder-white/40 outline-none disabled:cursor-not-allowed min-h-[20px] max-h-[200px]"
          />
          <button
            onClick={handleSend}
            disabled={disabled || !value.trim()}
            aria-label="Gửi"
            className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-[#10a37f] text-white transition hover:bg-[#0d8c6d] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
              <path d="M3.105 2.288a.75.75 0 0 0-.826.95l1.313 4.37H15l-11.408.001 1.313 4.37a.75.75 0 0 0 .826.95l13-5a.75.75 0 0 0 0-1.4l-13-5Z" />
            </svg>
          </button>
        </div>
        <p className="mt-2 text-center text-xs text-white/30">
          Nhấn <kbd className="rounded bg-white/10 px-1 py-0.5 font-mono">Enter</kbd> để gửi · <kbd className="rounded bg-white/10 px-1 py-0.5 font-mono">Shift+Enter</kbd> xuống dòng
        </p>
      </div>
    </div>
  );
}
