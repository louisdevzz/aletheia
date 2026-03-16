import { createHash } from "crypto";

export interface DeduplicatorOptions {
  readonly exactMatch: boolean;
  readonly fuzzyMatch: boolean;
  readonly similarityThreshold: number;
  readonly minTextLength: number;
}

function jaccard(a: Set<string>, b: Set<string>): number {
  const intersection = new Set([...a].filter((x) => b.has(x)));
  const union = new Set([...a, ...b]);
  return union.size === 0 ? 0 : intersection.size / union.size;
}

function tokenize(text: string): Set<string> {
  return new Set(text.toLowerCase().split(/\s+/).filter((w) => w.length > 0));
}

export class ContentDeduplicator {
  private readonly exactMatch: boolean;
  private readonly fuzzyMatch: boolean;
  private readonly similarityThreshold: number;
  private readonly minTextLength: number;
  private readonly seenHashes = new Set<string>();

  constructor(options?: Partial<DeduplicatorOptions>) {
    this.exactMatch = options?.exactMatch ?? true;
    this.fuzzyMatch = options?.fuzzyMatch ?? true;
    this.similarityThreshold = options?.similarityThreshold ?? 0.95;
    this.minTextLength = options?.minTextLength ?? 20;
  }

  deduplicate<T extends { text: string }>(items: readonly T[]): T[] {
    const result: T[] = [];
    const seenTokenSets: Set<string>[] = [];

    for (const item of items) {
      const text = item.text;

      // Skip very short items
      if (text.length < this.minTextLength) {
        result.push(item);
        continue;
      }

      // Exact match via MD5 hash
      if (this.exactMatch) {
        const hash = createHash("md5").update(text).digest("hex");
        if (this.seenHashes.has(hash)) continue;
        this.seenHashes.add(hash);
      }

      // Fuzzy match via Jaccard similarity
      if (this.fuzzyMatch) {
        const tokens = tokenize(text);
        let isDuplicate = false;

        for (const seenTokens of seenTokenSets) {
          if (jaccard(tokens, seenTokens) >= this.similarityThreshold) {
            isDuplicate = true;
            break;
          }
        }

        if (isDuplicate) continue;
        seenTokenSets.push(tokens);
      }

      result.push(item);
    }

    return result;
  }

  reset(): void {
    this.seenHashes.clear();
  }
}
