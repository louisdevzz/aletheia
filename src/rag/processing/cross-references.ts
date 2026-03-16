export interface CrossReference {
  readonly sourceId: string;
  readonly targetId: string;
  readonly refType: string;
  readonly refText: string;
}

const REFERENCE_PATTERNS = [
  { pattern: /(?:see|refer\s+to|as\s+shown\s+in|according\s+to)\s+(Table|Figure|Fig\.|Equation|Eq\.)\s*(\d+(?:\.\d+)?)/gi, type: "citation" },
  { pattern: /\[(\d+(?:,\s*\d+)*)\]/g, type: "numeric_citation" },
  { pattern: /(Table|Figure|Fig\.|Equation|Eq\.)\s*(\d+(?:\.\d+)?)/gi, type: "direct_reference" },
];

export class CrossReferenceResolver {
  buildGraph(items: readonly { id: string; text: string; item_type?: string }[]): Map<string, CrossReference[]> {
    const graph = new Map<string, CrossReference[]>();

    for (const item of items) {
      const refs = this.extractReferences(item);
      if (refs.length > 0) {
        graph.set(item.id, refs);
      }
    }

    return graph;
  }

  private extractReferences(item: { id: string; text: string }): CrossReference[] {
    const refs: CrossReference[] = [];
    const text = item.text;

    for (const { pattern, type } of REFERENCE_PATTERNS) {
      // Reset regex lastIndex for global patterns
      pattern.lastIndex = 0;
      let match: RegExpExecArray | null;

      while ((match = pattern.exec(text)) !== null) {
        refs.push({
          sourceId: item.id,
          targetId: match[0],
          refType: type,
          refText: match[0],
        });
      }
    }

    return refs;
  }
}
