import type { Tool, ToolCall, ToolResult } from "./base.js";
import { createToolResult } from "./base.js";

export class ToolRegistry {
  private readonly tools: Map<string, Tool> = new Map();

  register(tool: Tool): this {
    this.tools.set(tool.name, tool);
    return this;
  }

  unregister(name: string): this {
    this.tools.delete(name);
    return this;
  }

  get(name: string): Tool | undefined {
    return this.tools.get(name);
  }

  listTools(): string[] {
    return [...this.tools.keys()];
  }

  getAll(): Tool[] {
    return [...this.tools.values()];
  }

  getAllSpecs(): Record<string, unknown>[] {
    return [...this.tools.values()].map((t) => t.toOpenAIFunction());
  }

  async execute(call: ToolCall): Promise<ToolResult> {
    const tool = this.get(call.name);
    if (!tool) {
      return createToolResult(false, "", `Tool '${call.name}' not found`);
    }
    try {
      return await tool.execute(call.arguments);
    } catch (e) {
      return createToolResult(false, "", `Error executing tool: ${String(e)}`);
    }
  }

  async executeMany(calls: readonly ToolCall[]): Promise<ToolResult[]> {
    return Promise.all(calls.map((c) => this.execute(c)));
  }
}
