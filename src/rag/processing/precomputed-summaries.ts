import OpenAI from "openai";
import { getKimiConfig } from "../../config/settings.js";

export interface SummaryResult {
  readonly docId: string;
  readonly pageNum: number;
  readonly summary: string;
  readonly itemCount: number;
}

export class PrecomputedSummarizer {
  private readonly client: OpenAI;
  private readonly model: string;

  constructor() {
    const config = getKimiConfig();
    this.client = new OpenAI({
      apiKey: config.apiKey,
      baseURL: config.baseUrl,
    });
    this.model = config.model;
  }

  async computeDocumentSummaries(
    sentences: readonly { text: string; page_num: number }[],
    docId: string,
  ): Promise<SummaryResult[]> {
    // Group by page
    const pageGroups = new Map<number, string[]>();
    for (const s of sentences) {
      const existing = pageGroups.get(s.page_num) ?? [];
      pageGroups.set(s.page_num, [...existing, s.text]);
    }

    const summaries: SummaryResult[] = [];

    for (const [pageNum, texts] of pageGroups) {
      const combined = texts.join("\n\n");
      if (combined.length < 50) continue;

      try {
        const response = await this.client.chat.completions.create({
          model: this.model,
          messages: [
            {
              role: "user",
              content: `Summarize the following page content in 2-3 sentences, preserving key facts and any mathematical formulas:\n\n${combined}`,
            },
          ],
          temperature: 0.0,
        });

        const summary = response.choices[0]?.message?.content ?? "";
        if (summary) {
          summaries.push({
            docId,
            pageNum,
            summary,
            itemCount: texts.length,
          });
        }
      } catch (e) {
        console.error(`[summarizer] Failed to summarize page ${pageNum}:`, e);
      }
    }

    return summaries;
  }
}
