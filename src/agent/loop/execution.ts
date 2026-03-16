import { createToolResult } from "../../tools/base.js";
import type { ToolCall, ToolResult } from "../../tools/base.js";
import type { ToolRegistry } from "../../tools/registry.js";

export interface ExecutionResult {
  readonly call: ToolCall;
  readonly result: ToolResult;
  readonly durationMs: number;
  readonly approved: boolean;
}

export interface ExecutionConfig {
  readonly timeoutSeconds: number;
  readonly enableApproval: boolean;
  readonly parallelExecution: boolean;
}

const DEFAULT_EXECUTION_CONFIG: ExecutionConfig = {
  timeoutSeconds: 30.0,
  enableApproval: false,
  parallelExecution: true,
};

export class ToolExecutor {
  private readonly registry: ToolRegistry;
  private readonly config: ExecutionConfig;

  constructor(registry: ToolRegistry, config?: Partial<ExecutionConfig>) {
    this.registry = registry;
    this.config = { ...DEFAULT_EXECUTION_CONFIG, ...config };
  }

  async executeSingle(call: ToolCall, timeout?: number): Promise<ExecutionResult> {
    const timeoutMs = (timeout ?? this.config.timeoutSeconds) * 1000;
    const startTime = performance.now();

    try {
      const result = await Promise.race<ToolResult>([
        this.registry.execute(call),
        new Promise<ToolResult>((_, reject) =>
          setTimeout(() => reject(new Error(`Tool execution timed out after ${timeoutMs / 1000}s`)), timeoutMs),
        ),
      ]);

      return {
        call,
        result,
        durationMs: performance.now() - startTime,
        approved: true,
      };
    } catch (e) {
      const error = e instanceof Error ? e.message : String(e);
      return {
        call,
        result: createToolResult(false, "", error),
        durationMs: performance.now() - startTime,
        approved: true,
      };
    }
  }

  async executeMany(calls: readonly ToolCall[], timeout?: number): Promise<ExecutionResult[]> {
    if (this.config.parallelExecution && calls.length > 1) {
      return Promise.all(calls.map((call) => this.executeSingle(call, timeout)));
    }

    const results: ExecutionResult[] = [];
    for (const call of calls) {
      results.push(await this.executeSingle(call, timeout));
    }
    return results;
  }

  formatResultsForLlm(results: readonly ExecutionResult[]): Record<string, unknown>[] {
    return results.map((execResult, idx) => ({
      role: "tool",
      tool_call_id: execResult.call.callId ?? `call_${idx}`,
      name: execResult.call.name,
      content: execResult.result.success
        ? execResult.result.output
        : `Error: ${execResult.result.error}`,
    }));
  }
}

export class ApprovalManager {
  private approvedTools: ReadonlySet<string> = new Set();
  private deniedTools: ReadonlySet<string> = new Set();

  isApproved(toolName: string): boolean {
    return !this.deniedTools.has(toolName);
  }

  approveTool(toolName: string): void {
    const approved = new Set(this.approvedTools);
    approved.add(toolName);
    this.approvedTools = approved;

    const denied = new Set(this.deniedTools);
    denied.delete(toolName);
    this.deniedTools = denied;
  }

  denyTool(toolName: string): void {
    const denied = new Set(this.deniedTools);
    denied.add(toolName);
    this.deniedTools = denied;

    const approved = new Set(this.approvedTools);
    approved.delete(toolName);
    this.approvedTools = approved;
  }
}
