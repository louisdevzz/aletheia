export interface ToolSpec {
  readonly name: string;
  readonly description: string;
  readonly parameters: Record<string, unknown>;
}

export interface ToolCall {
  readonly name: string;
  readonly arguments: Record<string, unknown>;
  readonly callId?: string;
}

export interface ToolResult {
  readonly success: boolean;
  readonly output: string;
  readonly error?: string;
  readonly timestamp: string;
}

export function createToolResult(
  success: boolean,
  output: string,
  error?: string
): ToolResult {
  return { success, output, error, timestamp: new Date().toISOString() };
}

export interface Tool {
  readonly name: string;
  readonly description: string;
  readonly parametersSchema: Record<string, unknown>;
  spec(): ToolSpec;
  execute(args: Record<string, unknown>): Promise<ToolResult>;
  toOpenAIFunction(): Record<string, unknown>;
}

export abstract class BaseTool implements Tool {
  abstract readonly name: string;
  abstract readonly description: string;

  get parametersSchema(): Record<string, unknown> {
    return { type: "object", properties: {}, required: [] };
  }

  spec(): ToolSpec {
    return {
      name: this.name,
      description: this.description,
      parameters: this.parametersSchema,
    };
  }

  abstract execute(args: Record<string, unknown>): Promise<ToolResult>;

  toOpenAIFunction(): Record<string, unknown> {
    return {
      type: "function",
      function: {
        name: this.name,
        description: this.description,
        parameters: this.parametersSchema,
      },
    };
  }
}
