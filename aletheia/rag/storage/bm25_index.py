"""
Elasticsearch BM25 Index - Lexical Search Layer
Provides keyword-based search using inverted index.
Supports both Elastic Cloud and local Elasticsearch.
"""
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from typing import List, Dict, Optional

from aletheia.config import elasticsearch_config


class BM25Index:
    """Elasticsearch-based BM25 search with inverted index."""
    
    def __init__(self, 
                 index_name: str = "sentences",
                 es_url: str = None,
                 api_key: str = None):
        """
        Initialize Elasticsearch connection.
        
        Args:
            index_name: Name of the Elasticsearch index
            es_url: Elasticsearch URL (uses config if None). For Elastic Cloud: https://xxx.es.io:443
            api_key: API key for authentication (uses config if None)
        """
        self.index_name = index_name
        
        # Get connection parameters
        if es_url or api_key:
            # Use provided parameters
            self.es_url = es_url or elasticsearch_config.url
            self.api_key = api_key or elasticsearch_config.api_key
        else:
            # Use config
            conn_params = elasticsearch_config.connection_params
            self.es_url = conn_params["hosts"][0]
            self.api_key = conn_params.get("api_key", "")
        
        # Connect to Elasticsearch
        self._connect()
    
    def _connect(self):
        """Establish connection to Elasticsearch."""
        try:
            if self.api_key:
                # Elastic Cloud connection
                self.es = Elasticsearch(
                    hosts=[self.es_url],
                    api_key=self.api_key
                )
                print(f"✓ Connected to Elastic Cloud at {self.es_url}")
            else:
                # Local Elasticsearch connection
                self.es = Elasticsearch([self.es_url])
                print(f"✓ Connected to Elasticsearch at {self.es_url}")
            
            # Verify connection
            if not self.es.ping():
                raise ConnectionError(f"Failed to ping Elasticsearch at {self.es_url}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Elasticsearch: {e}")
    
    def create_index(self, drop_existing: bool = False):
        """
        Create Elasticsearch index with BM25 similarity.
        
        Args:
            drop_existing: If True, drop existing index before creating
        """
        # Drop existing index if requested
        if drop_existing and self.es.indices.exists(index=self.index_name):
            self.es.indices.delete(index=self.index_name)
            print(f"✓ Dropped existing index: {self.index_name}")
        
        # Check if index already exists
        if self.es.indices.exists(index=self.index_name):
            print(f"✓ Index already exists: {self.index_name}")
            return
        
        # Define mapping
        mapping = {
            "mappings": {
                "properties": {
                    "sentence_id": {"type": "keyword"},
                    "doc_id": {"type": "keyword"},
                    "page_num": {"type": "integer"},
                    "paragraph_id": {"type": "keyword"},
                    "raw_text": {
                        "type": "text",
                        "analyzer": "standard",
                        "similarity": "BM25"
                    },
                    "item_type": {"type": "keyword"}
                }
            },
            "settings": {
                "index": {
                    "similarity": {
                        "default": {
                            "type": "BM25",
                            "k1": 1.2,
                            "b": 0.75
                        }
                    }
                }
            }
        }
        
        # Create index
        self.es.indices.create(index=self.index_name, body=mapping)
        print(f"✓ Created index: {self.index_name} with BM25 similarity")
    
    def index_sentences(self, sentences: List[Dict], doc_id: str):
        """
        Batch index sentences into Elasticsearch.
        
        Args:
            sentences: List of sentence dictionaries with keys:
                - id: Sentence ID
                - text: Sentence text
                - page_num: Page number
                - paragraph_id: Paragraph ID
                - item_type: Type (paragraph, math, table, figure)
            doc_id: Document UUID
        """
        if not sentences:
            return
        
        # Prepare bulk actions
        actions = []
        for sentence in sentences:
            action = {
                "_index": self.index_name,
                "_id": sentence['id'],
                "_source": {
                    "sentence_id": sentence['id'],
                    "doc_id": doc_id,
                    "page_num": sentence['page_num'],
                    "paragraph_id": sentence['paragraph_id'],
                    "raw_text": sentence['text'],
                    "item_type": sentence.get('item_type', 'paragraph')
                }
            }
            actions.append(action)
        
        # Bulk index
        success, failed = bulk(self.es, actions, raise_on_error=False)
        
        # Refresh index to make documents searchable
        self.es.indices.refresh(index=self.index_name)
        
        print(f"✓ Indexed {success} sentences into Elasticsearch")
        if failed:
            failed_ids = [f['create']['_id'] for f in failed if 'create' in f]
            raise Exception(f"Failed to index {len(failed)} sentences into Elasticsearch: {failed_ids[:5]}")
    
    def search(self, 
               query: str, 
               top_k: int = 5,
               filter_doc_id: str = None,
               filter_page_num: int = None) -> List[Dict]:
        """
        BM25 keyword search.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            filter_doc_id: Optional filter by document ID
            filter_page_num: Optional filter by page number
            
        Returns:
            List of search results with sentence IDs and scores
        """
        # Build query
        must_clauses = [
            {"match": {"raw_text": {"query": query, "operator": "or"}}}
        ]
        
        # Add filters
        if filter_doc_id:
            must_clauses.append({"term": {"doc_id": filter_doc_id}})
        if filter_page_num is not None:
            must_clauses.append({"term": {"page_num": filter_page_num}})
        
        search_body = {
            "query": {
                "bool": {
                    "must": must_clauses
                }
            },
            "size": top_k
        }
        
        # Execute search
        response = self.es.search(index=self.index_name, body=search_body)
        
        # Format results
        results = []
        for hit in response["hits"]["hits"]:
            results.append({
                "sentence_id": hit["_source"]["sentence_id"],
                "score": float(hit["_score"]),
                "metadata": {
                    "doc_id": hit["_source"]["doc_id"],
                    "page_num": hit["_source"]["page_num"],
                    "paragraph_id": hit["_source"]["paragraph_id"],
                    "item_type": hit["_source"]["item_type"]
                }
            })
        
        return results
    
    def page_exists(self, doc_id: str, page_num: int) -> bool:
        """
        Check if documents already exist for a specific page.
        
        Args:
            doc_id: Document UUID
            page_num: Page number
            
        Returns:
            True if documents exist for this page, False otherwise
        """
        query = {
            "bool": {
                "must": [
                    {"term": {"doc_id": doc_id}},
                    {"term": {"page_num": page_num}}
                ]
            }
        }
        
        try:
            response = self.es.count(index=self.index_name, query=query)
            return response['count'] > 0
        except Exception as e:
            raise Exception(f"Failed to check page existence: {e}")
    
    def delete_by_doc_id(self, doc_id: str):
        """
        Delete all documents for a doc_id.
        
        Args:
            doc_id: Document UUID
        """
        query = {
            "query": {
                "term": {"doc_id": doc_id}
            }
        }
        
        self.es.delete_by_query(index=self.index_name, body=query)
        self.es.indices.refresh(index=self.index_name)
        print(f"✓ Deleted documents for doc_id: {doc_id}")
    
    def close(self):
        """Close Elasticsearch connection."""
        self.es.close()
        print("✓ Elasticsearch connection closed")
