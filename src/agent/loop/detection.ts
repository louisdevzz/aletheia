import { createHash } from "crypto";
import type { ToolResult } from "../../tools/base.js";

export enum LoopVerdict {
  CONTINUE = "CONTINUE",
  INJECT_WARNING = "INJECT_WARNING",
  HARD_STOP = "HARD_STOP",
}

export interface ToolCallRecord {
  readonly toolName: string;
  readonly argsHash: string;
  readonly resultHash: string;
  readonly success: boolean;
  readonly iteration: number;
}

export interface LoopDetectionConfig {
  readonly noProgressThreshold: number;
  readonly pingPongCycles: number;
  readonly failureStreakThreshold: number;
}

const DEFAULT_CONFIG: LoopDetectionConfig = {
  noProgressThreshold: 3,
  pingPongCycles: 2,
  failureStreakThreshold: 3,
};

export class LoopDetector {
  private readonly config: LoopDetectionConfig;
  private history: readonly ToolCallRecord[] = [];
  private warningInjected = false;

  constructor(config?: Partial<LoopDetectionConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  recordCall(
    toolName: string,
    args: Record<string, unknown>,
    result: ToolResult,
    iteration: number,
  ): void {
    const record: ToolCallRecord = {
      toolName: toolName.toLowerCase(),
      argsHash: hashDict(args),
      resultHash: hashResult(result),
      success: result.success,
      iteration,
    };
    this.history = [...this.history, record];
  }

  check(): { verdict: LoopVerdict; message: string | null } {
    if (this.history.length < 2) {
      return { verdict: LoopVerdict.CONTINUE, message: null };
    }

    const noProgress = this.checkNoProgress();
    if (noProgress.verdict !== LoopVerdict.CONTINUE) return noProgress;

    const pingPong = this.checkPingPong();
    if (pingPong.verdict !== LoopVerdict.CONTINUE) return pingPong;

    const failureStreak = this.checkFailureStreak();
    if (failureStreak.verdict !== LoopVerdict.CONTINUE) return failureStreak;

    return { verdict: LoopVerdict.CONTINUE, message: null };
  }

  private checkNoProgress(): { verdict: LoopVerdict; message: string | null } {
    const threshold = this.config.noProgressThreshold;
    if (threshold === 0 || this.history.length < threshold) {
      return { verdict: LoopVerdict.CONTINUE, message: null };
    }

    const recent = this.history.slice(-threshold);
    const first = recent[0];

    const allSame = recent.every(
      (r) =>
        r.toolName === first.toolName &&
        r.argsHash === first.argsHash &&
        r.resultHash === first.resultHash,
    );

    if (allSame) {
      if (!this.warningInjected) {
        this.warningInjected = true;
        return {
          verdict: LoopVerdict.INJECT_WARNING,
          message:
            `Warning: Tool '${first.toolName}' was called ${threshold} times ` +
            `with the same arguments and produced identical results. ` +
            `This suggests a loop. Please reconsider your approach or provide different parameters.`,
        };
      }
      return {
        verdict: LoopVerdict.HARD_STOP,
        message:
          `Loop detected: Tool '${first.toolName}' continues to be called with the same arguments ` +
          `without making progress. Stopping to prevent infinite loop.`,
      };
    }

    return { verdict: LoopVerdict.CONTINUE, message: null };
  }

  private checkPingPong(): { verdict: LoopVerdict; message: string | null } {
    const cycles = this.config.pingPongCycles;
    if (cycles === 0 || this.history.length < cycles * 2) {
      return { verdict: LoopVerdict.CONTINUE, message: null };
    }

    const recent = this.history.slice(-cycles * 2);

    if (recent.length >= 4) {
      const tools = recent.map((r) => r.toolName);
      const uniqueTools = new Set(tools);

      if (uniqueTools.size === 2 && tools[0] !== tools[1]) {
        const pattern = tools.slice(0, 2);
        const isPingPong = tools.every((t, i) => t === pattern[i % 2]);

        if (isPingPong) {
          if (!this.warningInjected) {
            this.warningInjected = true;
            return {
              verdict: LoopVerdict.INJECT_WARNING,
              message:
                `Warning: Detected ping-pong pattern between '${pattern[0]}' and '${pattern[1]}'. ` +
                `The tools appear to be calling each other without converging. ` +
                `Please break this cycle with a direct answer.`,
            };
          }
          return {
            verdict: LoopVerdict.HARD_STOP,
            message:
              `Ping-pong loop detected. The conversation is cycling between tools ` +
              `without resolution. Terminating to prevent infinite loop.`,
          };
        }
      }
    }

    return { verdict: LoopVerdict.CONTINUE, message: null };
  }

  private checkFailureStreak(): { verdict: LoopVerdict; message: string | null } {
    const threshold = this.config.failureStreakThreshold;
    if (threshold === 0) {
      return { verdict: LoopVerdict.CONTINUE, message: null };
    }

    const failuresByTool: Record<string, number> = {};

    for (let i = this.history.length - 1; i >= 0; i--) {
      const record = this.history[i];
      if (!record.success) {
        failuresByTool[record.toolName] = (failuresByTool[record.toolName] ?? 0) + 1;
      } else {
        break;
      }
    }

    for (const [tool, count] of Object.entries(failuresByTool)) {
      if (count >= threshold) {
        if (!this.warningInjected) {
          this.warningInjected = true;
          return {
            verdict: LoopVerdict.INJECT_WARNING,
            message:
              `Warning: Tool '${tool}' has failed ${count} consecutive times. ` +
              `Consider alternative approaches or ask for clarification.`,
          };
        }
        return {
          verdict: LoopVerdict.HARD_STOP,
          message: `Tool '${tool}' continues to fail. Stopping to prevent further errors.`,
        };
      }
    }

    return { verdict: LoopVerdict.CONTINUE, message: null };
  }
}

function hashDict(d: Record<string, unknown>): string {
  return createHash("md5").update(JSON.stringify(d, Object.keys(d).sort())).digest("hex").slice(0, 16);
}

function hashResult(result: ToolResult): string {
  const content = result.success ? result.output : (result.error ?? "");
  return createHash("md5").update(content).digest("hex").slice(0, 16);
}
