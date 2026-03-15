"""
Milvus Vector Index - Semantic Search Layer
Stores sentence embeddings for approximate nearest neighbor search.
Uses MilvusClient for Zilliz Cloud compatibility.
"""

import requests
from pymilvus import MilvusClient, DataType
from typing import List, Dict, Optional
from openai import OpenAI

from aletheia.config import milvus_config, embedding_config


class VectorIndex:
    """Milvus-based vector search with metadata filtering using MilvusClient."""

    def __init__(
        self,
        collection_name: str = "sentence_embeddings",
        uri: str = None,
        token: str = None,
    ):
        """
        Initialize Milvus connection and collection.

        Args:
            collection_name: Name of the Milvus collection
            uri: Milvus URI (uses config if None). For Zilliz Cloud: https://xxx.zillizcloud.com:19530
            token: Authentication token (uses config if None). Format: "user:password"
        """
        self.collection_name = collection_name
        self.dimension = embedding_config.dimension
        self.embedding_model = embedding_config.model

        # Initialize embedding client based on provider
        self.provider = embedding_config.provider
        if self.provider == "openai":
            self.openai_client = OpenAI(api_key=embedding_config.openai_api_key)
        elif self.provider == "ollama":
            self.openai_client = None  # Not used for Ollama
            self.ollama_base_url = embedding_config.ollama_base_url
        else:
            raise ValueError(f"Unknown embedding provider: {self.provider}")

        # Get connection parameters
        if uri or token:
            # Use provided parameters
            self.uri = uri or milvus_config.uri
            self.token = token or milvus_config.token
        else:
            # Use config
            conn_params = milvus_config.connection_params
            self.uri = conn_params["uri"]
            self.token = conn_params.get("token", "")

        # Connect to Milvus using MilvusClient
        self._connect()

    def _connect(self):
        """Establish connection to Milvus using MilvusClient."""
        try:
            if self.token:
                self.client = MilvusClient(uri=self.uri, token=self.token)
                print(f"✓ Connected to Zilliz Cloud at {self.uri}")
            else:
                self.client = MilvusClient(uri=self.uri)
                print(f"✓ Connected to Milvus at {self.uri}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Milvus: {e}")

    def create_collection(self, drop_existing: bool = False):
        """
        Create Milvus collection with schema using MilvusClient.

        Args:
            drop_existing: If True, drop existing collection before creating
        """
        # Drop existing collection if requested
        if drop_existing and self.client.has_collection(self.collection_name):
            self.client.drop_collection(self.collection_name)
            print(f"✓ Dropped existing collection: {self.collection_name}")

        # Check if collection already exists
        if self.client.has_collection(self.collection_name):
            print(f"✓ Collection already exists: {self.collection_name}")
            return

        # Define schema using MilvusClient API
        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=False)

        # Add fields
        schema.add_field(
            field_name="id", datatype=DataType.VARCHAR, max_length=200, is_primary=True
        )
        schema.add_field(
            field_name="embedding", datatype=DataType.FLOAT_VECTOR, dim=self.dimension
        )
        schema.add_field(field_name="doc_id", datatype=DataType.VARCHAR, max_length=100)
        schema.add_field(field_name="page_num", datatype=DataType.INT64)
        schema.add_field(
            field_name="paragraph_id", datatype=DataType.VARCHAR, max_length=100
        )
        schema.add_field(
            field_name="sentence_id", datatype=DataType.VARCHAR, max_length=100
        )

        # Create index params
        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 1024},
        )

        # Create collection
        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params,
        )

        print(f"✓ Created collection: {self.collection_name} with COSINE similarity")

    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings using configured provider (OpenAI or Ollama).

        Args:
            texts: List of text strings

        Returns:
            List of embedding vectors
        """
        try:
            if self.provider == "ollama":
                return self._generate_ollama_embeddings(texts)
            else:
                return self._generate_openai_embeddings(texts)
        except Exception as e:
            raise Exception(f"Failed to generate embeddings: {e}")

    def _generate_openai_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI API."""
        from tenacity import (
            retry,
            stop_after_attempt,
            wait_exponential,
            retry_if_exception_type,
        )

        @retry(
            retry=retry_if_exception_type(Exception),
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=2, max=20),
            reraise=True,
        )
        def _create_embeddings():
            return self.openai_client.embeddings.create(
                model=self.embedding_model, input=texts
            )

        response = _create_embeddings()
        return [item.embedding for item in response.data]

    def _generate_ollama_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Ollama HTTP API with batch processing."""
        from aletheia.rag.processing.batch_embeddings import BatchEmbeddingClient

        # Use batch embedding client for better performance
        client = BatchEmbeddingClient(
            provider="ollama",
            model=self.embedding_model,
            base_url=self.ollama_base_url,
            batch_size=32,
            max_workers=4,
        )

        try:
            embeddings = client.embed_batch(texts, batch_size=32)
            return embeddings
        except Exception as e:
            print(f"  ⚠️ Batch embedding failed: {e}, falling back to sequential")
            # Fallback to original sequential method
            return self._generate_ollama_embeddings_sequential(texts)
        finally:
            client.close()

    def _generate_ollama_embeddings_sequential(
        self, texts: List[str]
    ) -> List[List[float]]:
        """Fallback sequential embedding generation."""
        from tenacity import (
            retry,
            stop_after_attempt,
            wait_exponential,
            retry_if_exception_type,
        )

        embeddings = []

        @retry(
            retry=retry_if_exception_type((requests.RequestException, Exception)),
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=2, max=20),
            reraise=True,
        )
        def _call_ollama(text: str):
            response = requests.post(
                f"{self.ollama_base_url}/api/embeddings",
                json={"model": self.embedding_model, "prompt": text},
                timeout=60,
            )
            response.raise_for_status()
            return response.json()

        for text in texts:
            result = _call_ollama(text)
            embedding = result.get("embedding")
            if embedding is None:
                raise ValueError(f"No embedding found in response: {result}")
            embeddings.append(embedding)

        return embeddings

    def insert_vectors(self, sentences: List[Dict], doc_id: str):
        """
        Insert sentence embeddings into Milvus using MilvusClient.

        Args:
            sentences: List of sentence dictionaries with keys:
                - id: Sentence ID
                - text: Sentence text
                - page_num: Page number
                - paragraph_id: Paragraph ID
            doc_id: Document UUID
        """
        if not sentences:
            return

        # Generate embeddings
        texts = [s["text"] for s in sentences]
        embeddings = self._generate_embeddings(texts)

        # Prepare data as list of dictionaries
        data = []
        for i, sentence in enumerate(sentences):
            data.append(
                {
                    "id": sentence["id"],
                    "embedding": embeddings[i],
                    "doc_id": doc_id,
                    "page_num": sentence["page_num"],
                    "paragraph_id": sentence["paragraph_id"],
                    "sentence_id": sentence["id"],
                }
            )

        # Insert into collection
        self.client.insert(collection_name=self.collection_name, data=data)

        print(f"✓ Inserted {len(sentences)} vectors into Milvus")

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_doc_id: str = None,
        filter_page_num: int = None,
    ) -> List[Dict]:
        """
        Semantic search using vector similarity with MilvusClient.

        Args:
            query: Search query text
            top_k: Number of results to return
            filter_doc_id: Optional filter by document ID
            filter_page_num: Optional filter by page number

        Returns:
            List of search results with sentence IDs and scores
        """
        # Generate query embedding
        query_embedding = self._generate_embeddings([query])[0]

        # Build filter expression
        filter_expr = None
        if filter_doc_id and filter_page_num:
            filter_expr = (
                f'doc_id == "{filter_doc_id}" && page_num == {filter_page_num}'
            )
        elif filter_doc_id:
            filter_expr = f'doc_id == "{filter_doc_id}"'
        elif filter_page_num:
            filter_expr = f"page_num == {filter_page_num}"

        # Search using MilvusClient
        search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}

        results = self.client.search(
            collection_name=self.collection_name,
            data=[query_embedding],
            anns_field="embedding",
            search_params=search_params,
            limit=top_k,
            filter=filter_expr,
            output_fields=["doc_id", "page_num", "paragraph_id", "sentence_id"],
        )

        # Format results
        formatted_results = []
        for hit in results[0]:
            formatted_results.append(
                {
                    "sentence_id": hit.get("entity", {}).get("sentence_id")
                    or hit.get("sentence_id"),
                    "score": float(hit.get("distance", 0)),
                    "metadata": {
                        "doc_id": hit.get("entity", {}).get("doc_id")
                        or hit.get("doc_id"),
                        "page_num": hit.get("entity", {}).get("page_num")
                        or hit.get("page_num"),
                        "paragraph_id": hit.get("entity", {}).get("paragraph_id")
                        or hit.get("paragraph_id"),
                    },
                }
            )

        return formatted_results

    def page_exists(self, doc_id: str, page_num: int) -> bool:
        """
        Check if vectors already exist for a specific page.

        Args:
            doc_id: Document UUID
            page_num: Page number

        Returns:
            True if vectors exist for this page, False otherwise
        """
        filter_expr = f'doc_id == "{doc_id}" && page_num == {page_num}'

        try:
            results = self.client.query(
                collection_name=self.collection_name,
                filter=filter_expr,
                limit=1,
                output_fields=["sentence_id"],
            )
            return len(results) > 0
        except Exception as e:
            raise Exception(f"Failed to check page existence: {e}")

    def delete_by_doc_id(self, doc_id: str):
        """
        Delete all vectors for a document using MilvusClient.

        Args:
            doc_id: Document UUID
        """
        self.client.delete(
            collection_name=self.collection_name, filter=f'doc_id == "{doc_id}"'
        )
        print(f"✓ Deleted vectors for doc_id: {doc_id}")

    def close(self):
        """Close Milvus connection."""
        self.client.close()
        print("✓ Milvus connection closed")
