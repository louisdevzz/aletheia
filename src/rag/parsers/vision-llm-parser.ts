import { readFileSync } from "fs";
import OpenAI from "openai";
import { getKimiConfig } from "../../config/settings.js";
import type { Sentence, Paragraph, DisplayMath, Table, Figure, Page, PageItem, Document } from "./types.js";
import { isParagraph, isDisplayMath, isTable, isFigure } from "./types.js";

export const VISION_PROMPT = `You are a document parsing engine for citation-critical systems.

Your task is to faithfully reconstruct ONLY the actual academic/scientific content from the provided page image.

CONTENT TO EXTRACT (Include these):
- Title, authors, abstract
- Section headings (Introduction, Methods, Results, Discussion, Conclusion, References)
- Main text paragraphs with full sentences
- Mathematical equations (convert to LaTeX)
- Tables with data (convert to HTML)
- Figure captions (text describing figures)
- Bibliographic references

CONTENT TO EXCLUDE (Do NOT include these):
- Page headers and footers
- Page numbers
- "Downloaded from..." or "Accessed on..." text
- IP addresses
- "View table of contents" or navigation links
- Journal website branding (IOPscience, Nature.com, etc.)
- Terms and conditions
- Legal disclaimers
- Pricing information
- Standalone URLs (unless part of citations)
- Copyright notices

STRICT RULES (must follow):
- Do NOT summarize.
- Do NOT paraphrase.
- Do NOT improve wording.
- Do NOT merge sentences.
- Do NOT split sentences unless the original sentence is clearly broken by layout.
- Preserve original sentence boundaries as much as possible.
- Preserve original paragraph boundaries.
- Preserve original reading order.

OUTPUT FORMAT (MANDATORY)
---
primary_language: <ISO-639-1 code>
is_rotation_valid: <true|false>
rotation_correction: <degrees>
contains_table: <true|false>
contains_figure: <true|false>
---

[SECTION]
<Section title if present>

[PARAGRAPH]
Sentence 1.
Sentence 2.

[DISPLAY_MATH]
$$
LaTeX equation
$$

[TABLE]
<table>...</table>

[FIGURE]
Figure 1. Description of the figure.
`;

const DEFAULT_FIGURE_INDICATORS = [
  /^Figure\s+\d+/i,
  /^Fig\.\s*\d+/i,
  /^Scheme\s+\d+/i,
  /^Diagram\s+\d+/i,
  /^Chart\s+\d+/i,
  /^Plot\s+\d+/i,
  /^Graph\s+\d+/i,
  /^Image\s+\d+/i,
];

export class IngestionParser {
  private figurePatterns: RegExp[];

  constructor(figurePatterns?: string[]) {
    this.figurePatterns = figurePatterns
      ? figurePatterns.map((p) => new RegExp(p, "i"))
      : DEFAULT_FIGURE_INDICATORS;
  }

  private isFigureCaption(content: string): boolean {
    const stripped = content.trim();
    for (const pattern of this.figurePatterns) {
      if (pattern.test(stripped)) return true;
    }

    const mathSymbols = (content.match(/[\\=+\-_^{}[\]$]/g) ?? []).length;
    const total = content.length;
    if (total > 0) {
      const ratio = mathSymbols / total;
      if (ratio < 0.05 && stripped[0]?.match(/[A-Z]/)) {
        const captionWords = ["shows", "displays", "illustrates", "depicts", "presents"];
        if (captionWords.some((w) => stripped.toLowerCase().includes(w))) return true;
      }
    }

    return false;
  }

  parseCanonicalMarkdown(markdownText: string, pageIndex = 1): Page {
    const items: PageItem[] = [];
    const lines = markdownText.split("\n");
    let currentMode: string | null = null;
    let buffer: string[] = [];

    let paraCount = 0;
    let mathCount = 0;
    let tableCount = 0;
    let figCount = 0;
    let charOffset = 0;

    const flushBuffer = (): void => {
      if (!currentMode) return;
      const content = buffer.join("\n").trim();
      if (!content) {
        buffer = [];
        currentMode = null;
        return;
      }

      const itemStartOffset = charOffset;

      if (currentMode === "PARAGRAPH") {
        paraCount++;
        const sentences: Sentence[] = [];
        const sentLines = content.split("\n");
        let sentOffset = itemStartOffset;

        for (let sIdx = 0; sIdx < sentLines.length; sIdx++) {
          const sText = sentLines[sIdx].trim();
          if (sText) {
            const sId = `p${pageIndex}_para${paraCount}_s${sIdx + 1}`;
            sentences.push({ id: sId, text: sText, offsetStart: sentOffset, offsetEnd: sentOffset + sText.length });
            sentOffset += sText.length + 1;
          }
        }

        if (sentences.length > 0) {
          items.push({ id: `p${pageIndex}_para${paraCount}`, sentences } as Paragraph);
        }
      } else if (currentMode === "DISPLAY_MATH") {
        if (this.isFigureCaption(content)) {
          figCount++;
          items.push({ id: `p${pageIndex}_fig${figCount}`, description: content, placeholder: "" } as Figure);
        } else {
          mathCount++;
          items.push({ id: `p${pageIndex}_math${mathCount}`, latex: content } as DisplayMath);
        }
      } else if (currentMode === "TABLE") {
        tableCount++;
        items.push({ id: `p${pageIndex}_table${tableCount}`, html: content } as Table);
      } else if (currentMode === "FIGURE") {
        figCount++;
        let desc = "Figure";
        let placeholder = "";
        if (content.startsWith("![") && content.includes("](")) {
          const parts = content.split("](", 2);
          desc = parts[0].slice(2);
          placeholder = parts[1]?.slice(0, -1) ?? "";
        } else {
          desc = content;
        }
        items.push({ id: `p${pageIndex}_fig${figCount}`, description: desc, placeholder } as Figure);
      }

      charOffset = itemStartOffset + content.length + 1;
      buffer = [];
      currentMode = null;
    };

    for (const line of lines) {
      const stripped = line.trim();
      if (["[PARAGRAPH]", "[DISPLAY_MATH]", "[TABLE]", "[FIGURE]"].includes(stripped)) {
        flushBuffer();
        currentMode = stripped.slice(1, -1);
      } else if (stripped === "[SECTION]") {
        flushBuffer();
        currentMode = null;
      } else if (stripped.startsWith("---") && !currentMode) {
        continue;
      } else if (currentMode) {
        buffer.push(line);
      }
    }

    flushBuffer();
    return { id: `p${pageIndex}`, items };
  }
}

export class DocumentRenderer {
  static renderForReading(document: Document): string {
    const outputLines: string[] = [];

    for (const page of document.pages) {
      for (const item of page.items) {
        if (isParagraph(item)) {
          const text = item.sentences.map((s) => s.text).join(" ");
          outputLines.push(text, "");
        } else if (isDisplayMath(item)) {
          outputLines.push("$$", item.latex, "$$", "");
        } else if (isTable(item)) {
          outputLines.push(item.html, "");
        } else if (isFigure(item)) {
          outputLines.push(`![${item.description}](${item.placeholder})`, "");
        }
      }
    }

    return outputLines.join("\n");
  }
}

export class VisionLLMParser {
  readonly provider = "kimi";
  readonly modelName: string;
  private readonly client: OpenAI;

  constructor(modelName?: string) {
    this.modelName = modelName ?? "kimi-k2.5";
    const config = getKimiConfig();

    if (!config.apiKey) {
      throw new Error("KIMI_API_KEY not set in environment variables!");
    }

    this.client = new OpenAI({
      apiKey: config.apiKey,
      baseURL: config.baseUrl,
      defaultHeaders: { "User-Agent": config.userAgent },
    });

    console.log("[vision] API Key validated for KIMI provider");
  }

  async getPdfPageCount(pdfPath: string): Promise<number> {
    // Use pdfjs-dist to get page count
    const { getDocument } = await import("pdfjs-dist");
    const data = new Uint8Array(readFileSync(pdfPath));
    const doc = await getDocument({ data }).promise;
    const count = doc.numPages;
    doc.destroy();
    return count;
  }

  async getPageImageBase64(pdfPath: string, pageNum: number): Promise<string> {
    // Use pdfjs-dist + canvas to render page to image
    const { getDocument } = await import("pdfjs-dist");
    const { createCanvas } = await import("@napi-rs/canvas");

    const data = new Uint8Array(readFileSync(pdfPath));
    const doc = await getDocument({ data }).promise;
    const page = await doc.getPage(pageNum);

    const viewport = page.getViewport({ scale: 2.0 });
    const canvas = createCanvas(viewport.width, viewport.height);
    const ctx = canvas.getContext("2d");

    await page.render({ canvasContext: ctx as never, viewport }).promise;
    doc.destroy();

    return canvas.toBuffer("image/jpeg").toString("base64");
  }

  async parseImage(base64Image: string, pageNum?: number): Promise<string> {
    const pageInfo = pageNum ? `[Page ${pageNum}] ` : "";
    console.log(`  ${pageInfo}Sending request to KIMI API...`);
    const startTime = performance.now();

    const response = await this.client.chat.completions.create({
      model: this.modelName,
      messages: [
        {
          role: "user",
          content: [
            { type: "text", text: VISION_PROMPT },
            { type: "image_url", image_url: { url: `data:image/jpeg;base64,${base64Image}` } },
          ],
        },
      ],
      temperature: 0.0,
    });

    const elapsed = ((performance.now() - startTime) / 1000).toFixed(1);
    const content = response.choices[0]?.message?.content ?? "";
    console.log(`  ${pageInfo}API response received in ${elapsed}s (${content.length} chars)`);

    return content;
  }
}
