import { getRetrievalConfig } from "../../config/settings.js";
import { BATCH_SUMMARY_INITIAL, BATCH_SUMMARY_INCREMENTAL } from "../prompts.js";

export class CumulativeSummarizer {
  private readonly generator: { client: { chat: { completions: { create: (...args: unknown[]) => Promise<unknown> } } }; model: string };
  private readonly batchSize: number;
  private readonly maxRetries: number;
  private readonly timeout: number;

  constructor(generator: { client: { chat: { completions: { create: (...args: unknown[]) => Promise<unknown> } } }; model: string }) {
    this.generator = generator;
    const config = getRetrievalConfig();
    this.batchSize = config.batchSize;
    this.maxRetries = config.maxRetries;
    this.timeout = config.timeoutSeconds;
  }

  detectContentType(chunk: Record<string, unknown>): "text" | "table" | "formula" {
    const itemType = (chunk.item_type as string ?? "paragraph").toLowerCase();
    if (itemType === "table") return "table";
    if (["math", "formula", "equation"].includes(itemType)) return "formula";

    const text = (chunk.text as string) ?? "";
    if (this.isTable(text)) return "table";
    if (this.isFormula(text)) return "formula";
    return "text";
  }

  private isTable(text: string): boolean {
    if (text.includes("|") && (text.match(/\|/g)?.length ?? 0) > 2) return true;
    if (/^Table\b/i.test(text.trim())) return true;
    return false;
  }

  private isFormula(text: string): boolean {
    const latexMarkers = ["\\(", "\\[", "$$", "\\begin{equation}"];
    if (latexMarkers.some((m) => text.includes(m))) return true;
    const mathKeywords = ["equation", "=", "∫", "∑", "∂", "≈", "≤", "≥"];
    const count = mathKeywords.filter((k) => text.includes(k)).length;
    return count >= 2;
  }

  applyTableStrategy(tableChunk: Record<string, unknown>): Record<string, unknown> {
    const text = (tableChunk.text as string) ?? "";
    const caption = this.extractTableCaption(text);
    return {
      type: "table",
      caption,
      content: text,
      position: tableChunk.paragraph_id ?? "",
      page: tableChunk.page_num ?? 0,
    };
  }

  applyFormulaStrategy(
    formulaChunk: Record<string, unknown>,
    allChunks: readonly Record<string, unknown>[],
    position: number,
  ): Record<string, unknown> {
    const contextBefore = position > 0 ? ((allChunks[position - 1].text as string) ?? "") : "";
    const contextAfter = position < allChunks.length - 1 ? ((allChunks[position + 1].text as string) ?? "") : "";
    return {
      type: "formula",
      context_before: contextBefore,
      formula_latex: (formulaChunk.text as string) ?? "",
      context_after: contextAfter,
      position: formulaChunk.paragraph_id ?? "",
      page: formulaChunk.page_num ?? 0,
    };
  }

  private extractTableCaption(text: string): string {
    const match = /Table\s+\d+\.?\d*\s*:\s*([^\n|]+)/i.exec(text);
    if (match) return match[0].trim();
    const lines = text.split("\n");
    for (const line of lines) {
      if (line.trim() && !line.includes("|")) return line.trim();
    }
    return "";
  }

  private async callLlmWithRetry(prompt: string): Promise<[boolean, string]> {
    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      try {
        const resp = await this.generator.client.chat.completions.create({
          model: this.generator.model,
          messages: [{ role: "user", content: prompt }],
          temperature: 0.0,
        } as Record<string, unknown>) as { choices: { message: { content: string } }[] };
        return [true, resp.choices[0].message.content];
      } catch (e) {
        console.error(`[summarizer] LLM call failed (attempt ${attempt + 1}/${this.maxRetries}):`, e);
        if (attempt < this.maxRetries - 1) {
          await new Promise((r) => setTimeout(r, 2 ** attempt * 1000));
        }
      }
    }
    return [false, ""];
  }

  createFallbackSummary(chunks: readonly Record<string, unknown>[], chunkType = "text"): string {
    if (chunks.length === 0) return "[No content]";

    if (chunkType === "table") {
      return chunks.map((c) => {
        const text = (c.text as string) ?? "";
        const caption = this.extractTableCaption(text) || `Table at page ${c.page_num ?? "?"}`;
        return caption;
      }).join(" | ");
    }

    const firstText = ((chunks[0].text as string) ?? "").slice(0, 200);
    const lastText = chunks.length > 1 ? ((chunks[chunks.length - 1].text as string) ?? "").slice(0, 200) : "";
    return `${firstText}... ... ${lastText}`;
  }

  async summarizeBatch(textChunks: readonly Record<string, unknown>[]): Promise<string> {
    if (textChunks.length === 0) return "";
    if (textChunks.length === 1) return (textChunks[0].text as string) ?? "";

    let runningSummary = "";
    let processed = 0;

    while (processed < textChunks.length) {
      const batchEnd = Math.min(processed + this.batchSize, textChunks.length);
      const batch = textChunks.slice(processed, batchEnd);

      let prompt: string;
      if (processed === 0) {
        const batchText = batch
          .map((chunk, i) => `[Chunk ${i + 1}]:\n${(chunk.text as string) ?? ""}`)
          .join("\n\n");
        prompt = BATCH_SUMMARY_INITIAL
          .replace("{batch_text}", batchText)
          .replace("{num_chunks}", String(batch.length));
      } else {
        const newChunksText = batch
          .map((chunk, i) => `[Chunk ${processed + i + 1}]:\n${(chunk.text as string) ?? ""}`)
          .join("\n\n");
        prompt = BATCH_SUMMARY_INCREMENTAL
          .replace("{previous_summary}", runningSummary)
          .replace("{new_chunks}", newChunksText)
          .replace("{prev_end}", String(processed))
          .replace("{new_end}", String(batchEnd));
      }

      const [success, summary] = await this.callLlmWithRetry(prompt);

      if (success) {
        runningSummary = summary;
      } else {
        const fallback = this.createFallbackSummary(batch, "text");
        runningSummary = runningSummary
          ? `${runningSummary}\n\n[Chunks ${processed + 1}-${batchEnd}]: ${fallback}`
          : fallback;
      }

      processed = batchEnd;
    }

    return runningSummary;
  }

  assembleContext(
    summary: string,
    tables: readonly Record<string, unknown>[],
    formulas: readonly Record<string, unknown>[],
    currentChunk: Record<string, unknown>,
  ): string {
    const parts: string[] = [];

    if (summary) {
      parts.push(`=== CONTEXT SUMMARY ===\n${summary}\n`);
    }

    if (tables.length > 0) {
      parts.push("=== TABLES (Preserved) ===");
      for (const table of tables) {
        const caption = (table.caption as string) || `Table at page ${table.page}`;
        parts.push(`\n[${caption}]`);
        parts.push(table.content as string);
      }
      parts.push("");
    }

    if (formulas.length > 0) {
      parts.push("=== FORMULAS (with Context) ===");
      for (const formula of formulas) {
        if (formula.context_before) {
          parts.push(`Context: ${(formula.context_before as string).slice(0, 200)}...`);
        }
        parts.push(`\nFORMULA:\n${formula.formula_latex}\n`);
        if (formula.context_after) {
          parts.push(`Explanation: ${(formula.context_after as string).slice(0, 200)}...`);
        }
      }
      parts.push("");
    }

    parts.push(`=== CURRENT CHUNK (Page ${currentChunk.page_num ?? "?"}) ===`);
    parts.push((currentChunk.text as string) ?? "");

    return parts.join("\n");
  }
}
