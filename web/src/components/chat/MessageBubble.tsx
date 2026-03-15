import type { Message } from '@/types';
import { MarkdownMessage } from './MarkdownMessage';

interface MessageBubbleProps {
  message: Message;
  isLatest?: boolean;
}

export function MessageBubble({ message, isLatest = false }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div 
      className={`message-enter flex gap-4 ${isUser ? 'flex-row-reverse' : ''}`}
      style={{ animationDelay: isLatest ? '0ms' : '0ms' }}
    >
      {/* Avatar */}
      <div className="flex-shrink-0">
        {isUser ? (
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-purple-500 to-pink-500 text-sm font-semibold text-white">
            U
          </div>
        ) : (
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-[#10a37f] to-[#19c59f]"
          >
            <svg className="h-4 w-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
          </div>
        )}
      </div>

      {/* Message Content */}
      <div className={`flex-1 min-w-0 ${isUser ? 'text-right' : ''}`}>
        {/* Header */}
        <div className="mb-1 flex items-center gap-2">
          <span className="text-sm font-medium text-white/90">
            {isUser ? 'Bạn' : 'Aletheia'}
          </span>
          <span className="text-xs text-white/40">
            {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>

        {/* Content */}
        <div className={`inline-block max-w-full rounded-2xl px-4 py-3 text-left ${
          isUser 
            ? 'bg-[#10a37f]/20 text-white' 
            : 'bg-white/5 text-white/90'
        }`}>
          {isUser ? (
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
          ) : (
            <div className="markdown-content text-sm">
              <MarkdownMessage content={message.content} />
            </div>
          )}

          {/* Streaming indicator */}
          {message.streaming && (
            <span className="ml-1 inline-flex gap-1">
              <span className="typing-dot h-1.5 w-1.5 rounded-full bg-white/50"></span>
              <span className="typing-dot h-1.5 w-1.5 rounded-full bg-white/50"></span>
              <span className="typing-dot h-1.5 w-1.5 rounded-full bg-white/50"></span>
            </span>
          )}
        </div>

        {/* Sources */}
        {!message.streaming && message.sources && message.sources.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="text-xs text-white/40">Nguồn:</span>
            {message.sources.slice(0, 3).map((src, i) => (
              <span 
                key={i} 
                className="source-chip"
                title={`${src.filename} - Trang ${src.page_num}`}
              >
                <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                </svg>
                [{i + 1}] {src.filename} (p.{src.page_num})
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
