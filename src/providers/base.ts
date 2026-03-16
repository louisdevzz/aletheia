export interface ChatMessage {
  readonly role: "system" | "user" | "assistant" | "tool";
  readonly content: string;
  readonly toolCalls?: readonly ToolCallData[];
  readonly toolCallId?: string;
}

export interface ToolCallData {
  readonly id: string;
  readonly name: string;
  readonly arguments: string;
}

export interface ChatRequest {
  readonly messages: readonly ChatMessage[];
  readonly tools?: readonly Record<string, unknown>[];
  readonly toolChoice?: string;
  readonly temperature?: number;
  readonly stream?: boolean;
}

export interface ChatResponse {
  readonly text: string | null;
  readonly toolCalls: readonly ToolCallData[] | null;
  readonly usage: { promptTokens: number; completionTokens: number } | null;
  readonly rawResponse?: unknown;
}

export interface Provider {
  readonly name: string;
  chat(request: ChatRequest): Promise<ChatResponse>;
}
