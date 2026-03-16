import type { ToolResult } from "./base.js";
import { BaseTool, createToolResult } from "./base.js";
import type { HybridRetrieval, SearchResult } from "../rag/retrieval/retrieval.js";

export class RAGTool extends BaseTool {
  private _retrieval: HybridRetrieval | null = null;

  get name(): string {
    return "document_search";
  }

  get description(): string {
    return (
      "Search through uploaded documents to find relevant information. " +
      "Use this when the user asks questions about their documents, PDFs, or files. " +
      "Returns relevant text passages with source citations."
    );
  }

  get parametersSchema(): Record<string, unknown> {
    return {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "The search query about the documents",
        },
        top_k: {
          type: "integer",
          description: "Number of results to return (default: 5)",
          default: 5,
        },
        doc_id: {
          type: "string",
          description: "Optional: specific document ID to search within",
        },
      },
      required: ["query"],
    };
  }

  private async getRetrieval(): Promise<HybridRetrieval> {
    if (!this._retrieval) {
      const { HybridRetrieval } = await import("../rag/retrieval/retrieval.js");
      this._retrieval = new HybridRetrieval();
    }
    return this._retrieval;
  }

  async execute(args: Record<string, unknown>): Promise<ToolResult> {
    try {
      const query = args.query as string;
      if (!query) {
        return createToolResult(false, "", "Query is required");
      }

      const topK = (args.top_k as number) ?? 5;
      const docId = args.doc_id as string | undefined;

      console.log(`[rag-tool] Searching with query: '${query}'`);

      const retrieval = await this.getRetrieval();
      const results = await retrieval.hybridSearch(query, topK, 0.5, docId);

      if (results.length === 0) {
        return createToolResult(true, "No relevant documents found for this query.");
      }

      const outputParts: string[] = [];
      for (let i = 0; i < results.length; i++) {
        const result = results[i] as SearchResult;
        const text = (result.text as string) ?? "";
        const metadata = (result.metadata as Record<string, unknown>) ?? {};
        const filename = (metadata.filename as string) ?? "Unknown";
        const page = metadata.page_num ?? "N/A";
        outputParts.push(`[${i + 1}] ${filename} (Page ${page}):\n${text}\n`);
      }

      console.log(`[rag-tool] Found ${results.length} results`);
      return createToolResult(true, outputParts.join("\n"));
    } catch (e) {
      return createToolResult(
        false,
        "",
        `Error searching documents: ${e instanceof Error ? e.message : String(e)}`,
      );
    }
  }
}
