import { encodingForModel } from "js-tiktoken";
import type { TiktokenModel } from "js-tiktoken";

export class TokenManager {
  private readonly encoding: ReturnType<typeof encodingForModel>;

  constructor(model: TiktokenModel = "gpt-4") {
    this.encoding = encodingForModel(model);
  }

  countTokens(text: string): number {
    return this.encoding.encode(text).length;
  }

  truncateToTokenLimit(text: string, maxTokens: number): string {
    const tokens = this.encoding.encode(text);
    if (tokens.length <= maxTokens) return text;
    const truncated = tokens.slice(0, maxTokens);
    return this.encoding.decode(truncated);
  }

  isWithinLimit(text: string, maxTokens: number): boolean {
    return this.countTokens(text) <= maxTokens;
  }
}
