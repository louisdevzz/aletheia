import type { BaseTool, ToolResult } from "../tools/base.js";

export interface ResearchFinding {
  readonly source: string;
  readonly content: string;
  readonly confidence: number;
  readonly metadata: Record<string, unknown>;
}

export interface ResearchResult {
  readonly findings: readonly ResearchFinding[];
  readonly durationMs: number;
  readonly success: boolean;
  readonly error?: string;
}

export class ResearchPhase {
  private readonly maxIterations: number;

  constructor(maxIterations = 3) {
    this.maxIterations = maxIterations;
  }

  async conductResearch(
    query: string,
    tools: readonly BaseTool[],
  ): Promise<ResearchResult> {
    const startTime = performance.now();

    try {
      const findings: ResearchFinding[] = [];

      const ragTool = this.findTool(tools, "document_search");
      if (ragTool) {
        const result: ToolResult = await ragTool.execute({ query, top_k: 5 });
        if (result.success) {
          findings.push({
            source: "document_search",
            content: result.output,
            confidence: 0.9,
            metadata: {},
          });
        }
      }

      return {
        findings,
        durationMs: performance.now() - startTime,
        success: true,
      };
    } catch (e) {
      return {
        findings: [],
        durationMs: performance.now() - startTime,
        success: false,
        error: e instanceof Error ? e.message : String(e),
      };
    }
  }

  formatFindings(findings: readonly ResearchFinding[]): string {
    if (findings.length === 0) return "";

    const parts = ["\n\n## Research Findings\n"];

    for (let i = 0; i < findings.length; i++) {
      const finding = findings[i];
      parts.push(`\n### Source ${i + 1}: ${finding.source}\n`);
      const content = finding.content.length > 500
        ? finding.content.slice(0, 500) + "..."
        : finding.content;
      parts.push(content);
    }

    return parts.join("\n");
  }

  private findTool(tools: readonly BaseTool[], name: string): BaseTool | null {
    return tools.find((t) => t.name === name) ?? null;
  }
}
