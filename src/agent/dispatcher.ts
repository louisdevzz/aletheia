import type { ToolCall } from "../tools/base.js";

export interface ToolDispatcher {
  shouldSendToolSpecs(): boolean;
  toProviderMessages(history: readonly Record<string, unknown>[]): Record<string, unknown>[];
  parseResponse(response: unknown): { text: string; toolCalls: ToolCall[] };
}

export class NativeToolDispatcher implements ToolDispatcher {
  shouldSendToolSpecs(): boolean {
    return true;
  }

  toProviderMessages(history: readonly Record<string, unknown>[]): Record<string, unknown>[] {
    return history.map((msg) => {
      if (msg.role === "assistant" && msg.tool_calls) {
        return {
          role: "assistant",
          content: (msg.content as string) ?? "",
          tool_calls: msg.tool_calls,
        };
      }
      if (msg.role === "tool") {
        return {
          role: "tool",
          tool_call_id: msg.tool_call_id,
          content: (msg.content as string) ?? "",
        };
      }
      return {
        role: (msg.role as string) ?? "user",
        content: (msg.content as string) ?? "",
      };
    });
  }

  parseResponse(response: unknown): { text: string; toolCalls: ToolCall[] } {
    let text = "";
    const toolCalls: ToolCall[] = [];

    const resp = response as {
      choices?: { message: { content?: string; tool_calls?: { type: string; id: string; function: { name: string; arguments: string } }[] } }[];
    };

    if (resp.choices?.[0]?.message) {
      const message = resp.choices[0].message;
      if (message.content) text = message.content;

      if (message.tool_calls) {
        for (const tc of message.tool_calls) {
          if (tc.type === "function") {
            let args: Record<string, unknown> = {};
            try {
              args = JSON.parse(tc.function.arguments) as Record<string, unknown>;
            } catch {
              // ignore parse errors
            }
            toolCalls.push({
              name: tc.function.name,
              arguments: args,
              callId: tc.id,
            });
          }
        }
      }
    }

    return { text, toolCalls };
  }
}

export class XmlToolDispatcher implements ToolDispatcher {
  shouldSendToolSpecs(): boolean {
    return false;
  }

  promptInstructions(tools: readonly Record<string, unknown>[]): string {
    let instructions = "\n\n## Tool Use Protocol\n\n";
    instructions += 'You can use tools by writing JSON inside <tool_call> tags:\n\n';
    instructions += "<tool_call>\n";
    instructions += '{"name": "tool_name", "arguments": {"arg1": "value1"}}\n';
    instructions += "</tool_call>\n\n";
    instructions += "Available tools:\n\n";

    for (const tool of tools) {
      const func = (tool.function ?? {}) as Record<string, unknown>;
      const name = (func.name as string) ?? "unknown";
      const desc = (func.description as string) ?? "";
      instructions += `- ${name}: ${desc}\n`;
    }

    return instructions;
  }

  toProviderMessages(history: readonly Record<string, unknown>[]): Record<string, unknown>[] {
    return history.map((msg) => ({
      role: (msg.role as string) ?? "user",
      content: (msg.content as string) ?? "",
    }));
  }

  parseResponse(response: unknown): { text: string; toolCalls: ToolCall[] } {
    let text = "";
    const toolCalls: ToolCall[] = [];

    const resp = response as {
      choices?: { message: { content?: string } }[];
    };

    if (resp.choices?.[0]?.message?.content) {
      text = resp.choices[0].message.content;
    } else if (typeof response === "string") {
      text = response;
    }

    const pattern = /<tool_call>\s*(.*?)\s*<\/tool_call>/gs;
    let match: RegExpExecArray | null;

    while ((match = pattern.exec(text)) !== null) {
      try {
        const data = JSON.parse(match[1].trim()) as { name?: string; arguments?: Record<string, unknown> };
        if (data.name) {
          toolCalls.push({
            name: data.name,
            arguments: data.arguments ?? {},
          });
        }
      } catch {
        continue;
      }
    }

    const cleanText = text.replace(/<tool_call>\s*.*?\s*<\/tool_call>/gs, "").trim();
    return { text: cleanText, toolCalls };
  }
}
