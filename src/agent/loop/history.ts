import type { ChatMessage } from "../../providers/base.js";

export interface CompactionResult {
  readonly success: boolean;
  readonly summary: string;
  readonly messagesRemoved: number;
  readonly messagesKept: number;
}

export class HistoryManager {
  private readonly maxMessages: number;
  private readonly compactionThreshold: number;
  private readonly keepRecent: number;
  private compactionCount = 0;

  constructor(maxMessages = 20, compactionThreshold = 10, keepRecent = 4) {
    this.maxMessages = maxMessages;
    this.compactionThreshold = compactionThreshold;
    this.keepRecent = keepRecent;
  }

  maybeCompact(messages: readonly ChatMessage[]): {
    result: CompactionResult;
    messages: readonly ChatMessage[];
  } {
    if (messages.length <= this.maxMessages) {
      return {
        result: {
          success: false,
          summary: "",
          messagesRemoved: 0,
          messagesKept: messages.length,
        },
        messages,
      };
    }

    const totalToCompact = messages.length - this.keepRecent;
    const toCompact = messages.slice(0, totalToCompact);
    const toKeep = messages.slice(totalToCompact);

    const summary = this.simpleSummary(toCompact);
    const summaryMsg: ChatMessage = {
      role: "system",
      content: `[Previous conversation summary]\n${summary}`,
    };

    this.compactionCount++;

    const newMessages: readonly ChatMessage[] = [summaryMsg, ...toKeep];
    return {
      result: {
        success: true,
        summary,
        messagesRemoved: totalToCompact,
        messagesKept: newMessages.length,
      },
      messages: newMessages,
    };
  }

  trimToLimit(messages: readonly ChatMessage[]): {
    removed: number;
    messages: readonly ChatMessage[];
  } {
    if (messages.length <= this.maxMessages) {
      return { removed: 0, messages };
    }

    const hasSystem = messages.length > 0 && messages[0].role === "system";

    if (hasSystem) {
      const keepCount = this.maxMessages - 1;
      const newMessages: readonly ChatMessage[] = [messages[0], ...messages.slice(-keepCount)];
      return {
        removed: messages.length - newMessages.length,
        messages: newMessages,
      };
    }

    const newMessages = messages.slice(-this.maxMessages);
    return {
      removed: messages.length - this.maxMessages,
      messages: newMessages,
    };
  }

  private simpleSummary(messages: readonly ChatMessage[]): string {
    const userMsgs = messages.filter((m) => m.role === "user");
    const assistantMsgs = messages.filter((m) => m.role === "assistant");
    const toolMsgs = messages.filter((m) => m.role === "tool");

    const parts: string[] = [];
    if (userMsgs.length > 0) parts.push(`${userMsgs.length} user queries`);
    if (assistantMsgs.length > 0) parts.push(`${assistantMsgs.length} assistant responses`);
    if (toolMsgs.length > 0) parts.push(`${toolMsgs.length} tool results`);

    return `Previous conversation: ${parts.join(", ")}.`;
  }

  getCompactionCount(): number {
    return this.compactionCount;
  }
}
