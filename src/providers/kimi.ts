import OpenAI from "openai";
import type { ChatCompletionCreateParamsNonStreaming } from "openai/resources/chat/completions";
import { getKimiConfig } from "../config/settings.js";
import type { Provider, ChatRequest, ChatResponse, ChatMessage, ToolCallData } from "./base.js";

export class KimiProvider implements Provider {
  readonly name = "kimi";
  private readonly client: OpenAI;
  private readonly model: string;

  constructor(apiKey?: string, model?: string) {
    const config = getKimiConfig();
    this.model = model ?? config.model;
    this.client = new OpenAI({
      apiKey: apiKey ?? config.apiKey,
      baseURL: config.baseUrl,
      defaultHeaders: { "User-Agent": config.userAgent },
    });
  }

  async chat(request: ChatRequest): Promise<ChatResponse> {
    const messages = request.messages.map((msg) => this.formatMessage(msg));

    const params: ChatCompletionCreateParamsNonStreaming = {
      model: this.model,
      messages: messages as unknown as ChatCompletionCreateParamsNonStreaming["messages"],
      temperature: request.temperature ?? 0.7,
      stream: false,
    };

    if (request.tools && request.tools.length > 0) {
      params.tools = request.tools as unknown as ChatCompletionCreateParamsNonStreaming["tools"];
      params.tool_choice = (request.toolChoice ?? "auto") as ChatCompletionCreateParamsNonStreaming["tool_choice"];
      const toolNames = (request.tools as Array<{ function?: { name?: string } }>).map(
        (t) => t.function?.name ?? "unknown"
      );
      console.log(`[kimi] Sending ${request.tools.length} tools: ${toolNames.join(", ")}`);
    }

    console.log(`[kimi] Messages: ${messages.length}, last: ${messages.at(-1)?.content?.toString().slice(0, 80) ?? "N/A"}...`);

    const response = await this.client.chat.completions.create(params);

    const choice = response.choices[0];
    const text = choice.message.content ?? null;

    const toolCalls: ToolCallData[] = [];
    if (choice.message.tool_calls) {
      for (const tc of choice.message.tool_calls) {
        toolCalls.push({
          id: tc.id,
          name: tc.function.name,
          arguments: tc.function.arguments,
        });
      }
    }

    const hasTools = toolCalls.length > 0;
    console.log(`[kimi] Response: has_tools=${hasTools}, content_len=${text?.length ?? 0}`);

    return {
      text,
      toolCalls: hasTools ? toolCalls : null,
      usage: response.usage
        ? {
            promptTokens: response.usage.prompt_tokens,
            completionTokens: response.usage.completion_tokens,
          }
        : null,
      rawResponse: response,
    };
  }

  private formatMessage(msg: ChatMessage): Record<string, unknown> {
    if (msg.role === "assistant" && msg.toolCalls && msg.toolCalls.length > 0) {
      const reasoning = `I need to use the ${msg.toolCalls[0].name} tool to help answer the user's question.`;
      return {
        role: "assistant",
        content: msg.content,
        reasoning_content: reasoning,
        tool_calls: msg.toolCalls.map((tc) => ({
          id: tc.id,
          type: "function",
          function: { name: tc.name, arguments: tc.arguments },
        })),
      };
    }

    if (msg.role === "tool") {
      return {
        role: "tool",
        tool_call_id: msg.toolCallId,
        content: msg.content,
      };
    }

    return { role: msg.role, content: msg.content };
  }
}
