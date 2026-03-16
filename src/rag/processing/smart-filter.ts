const METADATA_PATTERNS = [
  /^page\s+\d+\s*(of\s+\d+)?$/i,
  /^downloaded\s+from/i,
  /^accessed\s+on/i,
  /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/,
  /^view\s+table\s+of\s+contents/i,
  /^terms\s+(and|&)\s+conditions/i,
  /^copyright\s+/i,
  /^some\s+figures\s+may\s+appear/i,
  /^https?:\/\/\S+$/,
  /^doi:\s/i,
  /^published\s+online/i,
  /^available\s+at\s/i,
  /^journal\s+homepage/i,
];

const BOILERPLATE_PHRASES = [
  "all rights reserved",
  "this article is licensed under",
  "creative commons",
  "open access",
  "peer review",
  "received:",
  "accepted:",
  "published:",
  "revised:",
  "corresponding author",
];

export class SmartMetadataFilter {
  private readonly patterns: RegExp[];
  private readonly boilerplatePhrases: string[];

  constructor(
    extraPatterns?: RegExp[],
    extraPhrases?: string[],
  ) {
    this.patterns = [...METADATA_PATTERNS, ...(extraPatterns ?? [])];
    this.boilerplatePhrases = [...BOILERPLATE_PHRASES, ...(extraPhrases ?? [])];
  }

  filterContent(text: string): string {
    const lines = text.split("\n");
    const filtered = lines.filter((line) => !this.isMetadata(line));
    return filtered.join("\n").trim();
  }

  isMetadata(text: string): boolean {
    const trimmed = text.trim();
    if (trimmed.length === 0) return false;

    // Check regex patterns
    for (const pattern of this.patterns) {
      if (pattern.test(trimmed)) return true;
    }

    // Check boilerplate phrases
    const lower = trimmed.toLowerCase();
    for (const phrase of this.boilerplatePhrases) {
      if (lower.includes(phrase)) return true;
    }

    return false;
  }
}
