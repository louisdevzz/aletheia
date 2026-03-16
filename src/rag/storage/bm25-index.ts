import { Client } from "@elastic/elasticsearch";
import { getElasticsearchConfig, getElasticsearchConnectionParams } from "../../config/settings.js";

export interface BM25SearchResult {
  readonly sentence_id: string;
  readonly score: number;
  readonly metadata: {
    readonly doc_id: string;
    readonly page_num: number;
    readonly paragraph_id: string;
    readonly item_type: string;
  };
}

export class BM25Index {
  private readonly es: Client;
  private readonly indexName: string;

  constructor(indexName = "sentences", esUrl?: string, apiKey?: string) {
    this.indexName = indexName;

    const config = getElasticsearchConfig();
    const resolvedUrl = esUrl ?? config.url;
    const resolvedApiKey = apiKey ?? config.apiKey;

    if (resolvedApiKey) {
      this.es = new Client({ node: resolvedUrl, auth: { apiKey: resolvedApiKey } });
      console.log(`[elasticsearch] Connected to Elastic Cloud at ${resolvedUrl}`);
    } else {
      this.es = new Client({ node: resolvedUrl });
      console.log(`[elasticsearch] Connected to ${resolvedUrl}`);
    }
  }

  async createIndex(dropExisting = false): Promise<void> {
    if (dropExisting) {
      const exists = await this.es.indices.exists({ index: this.indexName });
      if (exists) {
        await this.es.indices.delete({ index: this.indexName });
        console.log(`[elasticsearch] Dropped existing index: ${this.indexName}`);
      }
    }

    const exists = await this.es.indices.exists({ index: this.indexName });
    if (exists) {
      console.log(`[elasticsearch] Index already exists: ${this.indexName}`);
      return;
    }

    await this.es.indices.create({
      index: this.indexName,
      body: {
        mappings: {
          properties: {
            sentence_id: { type: "keyword" },
            doc_id: { type: "keyword" },
            page_num: { type: "integer" },
            paragraph_id: { type: "keyword" },
            raw_text: { type: "text", analyzer: "standard", similarity: "BM25" },
            item_type: { type: "keyword" },
          },
        },
        settings: {
          index: {
            similarity: {
              default: { type: "BM25", k1: 1.2, b: 0.75 },
            },
          },
        },
      },
    });

    console.log(`[elasticsearch] Created index: ${this.indexName} with BM25 similarity`);
  }

  async indexSentences(sentences: readonly { id: string; text: string; page_num: number; paragraph_id: string; item_type?: string }[], docId: string): Promise<void> {
    if (sentences.length === 0) return;

    const operations = sentences.flatMap((sentence) => [
      { index: { _index: this.indexName, _id: sentence.id } },
      {
        sentence_id: sentence.id,
        doc_id: docId,
        page_num: sentence.page_num,
        paragraph_id: sentence.paragraph_id,
        raw_text: sentence.text,
        item_type: sentence.item_type ?? "paragraph",
      },
    ]);

    const response = await this.es.bulk({ operations, refresh: true });

    if (response.errors) {
      const failedItems = response.items.filter((item) => item.index?.error);
      const failedIds = failedItems.map((item) => item.index?._id).slice(0, 5);
      throw new Error(`Failed to index ${failedItems.length} sentences: ${failedIds.join(", ")}`);
    }

    console.log(`[elasticsearch] Indexed ${sentences.length} sentences`);
  }

  async search(query: string, topK = 5, filterDocId?: string, filterPageNum?: number): Promise<BM25SearchResult[]> {
    const mustClauses: Record<string, unknown>[] = [
      { match: { raw_text: { query, operator: "or" } } },
    ];

    if (filterDocId) {
      mustClauses.push({ term: { doc_id: filterDocId } });
    }
    if (filterPageNum !== undefined) {
      mustClauses.push({ term: { page_num: filterPageNum } });
    }

    const response = await this.es.search({
      index: this.indexName,
      body: {
        query: { bool: { must: mustClauses } },
        size: topK,
      },
    });

    return response.hits.hits.map((hit) => {
      const source = hit._source as { sentence_id: string; doc_id: string; page_num: number; paragraph_id: string; item_type: string };
      return {
        sentence_id: source.sentence_id,
        score: hit._score ?? 0,
        metadata: {
          doc_id: source.doc_id,
          page_num: source.page_num,
          paragraph_id: source.paragraph_id,
          item_type: source.item_type,
        },
      };
    });
  }

  async pageExists(docId: string, pageNum: number): Promise<boolean> {
    const response = await this.es.count({
      index: this.indexName,
      query: {
        bool: {
          must: [
            { term: { doc_id: docId } },
            { term: { page_num: pageNum } },
          ],
        },
      },
    });
    return response.count > 0;
  }

  async deleteByDocId(docId: string): Promise<void> {
    await this.es.deleteByQuery({
      index: this.indexName,
      body: { query: { term: { doc_id: docId } } },
      refresh: true,
    });
    console.log(`[elasticsearch] Deleted documents for doc_id: ${docId}`);
  }

  async close(): Promise<void> {
    await this.es.close();
    console.log("[elasticsearch] Connection closed");
  }
}
