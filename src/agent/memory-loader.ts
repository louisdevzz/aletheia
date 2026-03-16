export interface MemoryEntry {
  readonly id: string;
  readonly key: string;
  readonly content: string;
  readonly category: string;
  readonly timestamp: string;
  readonly score?: number;
  readonly sessionId?: string;
}

export interface Memory {
  recall(query: string, limit: number, sessionId?: string): Promise<readonly MemoryEntry[]>;
  store(key: string, content: string, category: string, sessionId?: string): Promise<void>;
}

const LOADER_DECAY_HALF_LIFE_DAYS = 7.0;
const CORE_CATEGORY_SCORE_BOOST = 0.3;
const RECALL_OVER_FETCH_FACTOR = 2;

export interface MemoryLoader {
  loadContext(memory: Memory, userMessage: string): Promise<string>;
}

export class DefaultMemoryLoader implements MemoryLoader {
  private readonly limit: number;
  private readonly minRelevanceScore: number;

  constructor(limit = 5, minRelevanceScore = 0.4) {
    this.limit = Math.max(1, limit);
    this.minRelevanceScore = minRelevanceScore;
  }

  async loadContext(memory: Memory, userMessage: string): Promise<string> {
    const fetchLimit = this.limit * RECALL_OVER_FETCH_FACTOR;
    const entries = await memory.recall(userMessage, fetchLimit);

    if (entries.length === 0) return "";

    const decayed = applyTimeDecay(entries, LOADER_DECAY_HALF_LIFE_DAYS);

    const scored: { entry: MemoryEntry; score: number }[] = [];
    for (const entry of decayed) {
      if (isAssistantAutosaveKey(entry.key)) continue;

      const baseScore = entry.score ?? this.minRelevanceScore;
      const boostedScore = applyCategoryBoost(entry, baseScore);

      if (boostedScore >= this.minRelevanceScore) {
        scored.push({ entry, score: boostedScore });
      }
    }

    scored.sort((a, b) => b.score - a.score);
    const top = scored.slice(0, this.limit);

    if (top.length === 0) return "";

    const lines = ["[Memory context]"];
    for (const { entry } of top) {
      lines.push(`- ${entry.key}: ${entry.content}`);
    }

    return lines.join("\n") + "\n";
  }
}

export class SimpleMemoryLoader implements MemoryLoader {
  private readonly limit: number;

  constructor(limit = 5) {
    this.limit = limit;
  }

  async loadContext(memory: Memory, userMessage: string): Promise<string> {
    const entries = await memory.recall(userMessage, this.limit);
    if (entries.length === 0) return "";

    const lines = ["[Memory context]"];
    for (const entry of entries) {
      lines.push(`- ${entry.key}: ${entry.content}`);
    }

    return lines.join("\n") + "\n";
  }
}

export class NoOpMemoryLoader implements MemoryLoader {
  async loadContext(): Promise<string> {
    return "";
  }
}

export function createMemoryLoader(
  enableDecay = true,
  enableBoost = true,
  limit = 5,
  minScore = 0.4,
): MemoryLoader {
  if (!enableDecay && !enableBoost) {
    return new SimpleMemoryLoader(limit);
  }
  return new DefaultMemoryLoader(limit, minScore);
}

function applyTimeDecay(
  entries: readonly MemoryEntry[],
  halfLifeDays: number,
): readonly MemoryEntry[] {
  const now = Date.now();

  return entries.map((entry) => {
    if (entry.score == null) return entry;

    try {
      const entryTime = new Date(entry.timestamp).getTime();
      const ageDays = (now - entryTime) / (24 * 3600 * 1000);
      const decayFactor = Math.pow(0.5, ageDays / halfLifeDays);
      return { ...entry, score: entry.score * decayFactor };
    } catch {
      return entry;
    }
  });
}

function applyCategoryBoost(entry: MemoryEntry, baseScore: number): number {
  if (entry.category.toLowerCase() === "core") {
    return Math.min(1.0, baseScore + CORE_CATEGORY_SCORE_BOOST);
  }
  return baseScore;
}

function isAssistantAutosaveKey(key: string): boolean {
  return key.startsWith("assistant_resp") || key.startsWith("assistant_");
}
