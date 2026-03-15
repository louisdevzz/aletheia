"""
Batch Embedding Client

Optimized embedding generation with batch processing and connection pooling.
Reduces API calls from N to N/batch_size.

Usage:
    client = BatchEmbeddingClient(provider='ollama')
    embeddings = client.embed_batch(texts, batch_size=32)
"""

import requests
import aiohttp
import asyncio
from typing import List, Dict, Optional, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
import time


class BatchEmbeddingClient:
    """
    High-performance embedding client with batching and async support.
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str = "text-embedding-3-small",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        max_workers: int = 4,
        batch_size: int = 32,
    ):
        """
        Initialize batch embedding client.

        Args:
            provider: 'openai' or 'ollama'
            model: Model name
            base_url: API base URL (for Ollama)
            api_key: API key (for OpenAI)
            max_workers: Max parallel workers
            batch_size: Texts per batch
        """
        self.provider = provider
        self.model = model
        self.base_url = base_url or "http://localhost:11434"
        self.api_key = api_key
        self.max_workers = max_workers
        self.batch_size = batch_size

        # Connection pooling
        self.session = requests.Session()
        if provider == "openai" and api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    def embed_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
        show_progress: bool = True,
    ) -> List[List[float]]:
        """
        Generate embeddings with batching.

        Args:
            texts: List of texts to embed
            batch_size: Override default batch size
            show_progress: Show progress bar

        Returns:
            List of embedding vectors
        """
        batch_size = batch_size or self.batch_size

        if len(texts) <= batch_size:
            # Single batch
            return self._embed_single_batch(texts)

        # Multiple batches
        all_embeddings = []
        total_batches = (len(texts) + batch_size - 1) // batch_size

        if show_progress:
            print(f"🔤 Embedding {len(texts)} texts in {total_batches} batches...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all batches
            futures = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                future = executor.submit(self._embed_single_batch, batch)
                futures.append((i, future))

            # Collect results
            results = [None] * len(texts)
            completed = 0

            for idx, future in futures:
                try:
                    batch_embeddings = future.result()
                    # Place in correct position
                    for j, emb in enumerate(batch_embeddings):
                        if idx + j < len(results):
                            results[idx + j] = emb

                    completed += 1
                    if show_progress and completed % 10 == 0:
                        print(f"   Progress: {completed}/{total_batches} batches")

                except Exception as e:
                    print(f"  ❌ Batch {idx // batch_size} failed: {e}")
                    # Fill with zeros for failed batch
                    for j in range(batch_size):
                        if idx + j < len(results):
                            results[idx + j] = [0.0] * 1536

        return results

    def _embed_single_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a single batch."""
        if self.provider == "ollama":
            return self._embed_ollama_batch(texts)
        else:
            return self._embed_openai_batch(texts)

    def _embed_ollama_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Batch embedding with Ollama.

        Note: Ollama supports batching via multiple prompts in one request
        or parallel requests.
        """
        import json

        embeddings = []

        # Ollama API v0.1.24+ supports batch embeddings
        try:
            # Try batch API first
            response = self.session.post(
                f"{self.base_url}/api/embed",
                json={
                    "model": self.model,
                    "input": texts,  # Batch input
                },
                timeout=120,
            )

            if response.status_code == 200:
                result = response.json()
                # New API returns embeddings array
                if "embeddings" in result:
                    return result["embeddings"]
        except:
            pass

        # Fallback: parallel individual requests
        with ThreadPoolExecutor(max_workers=min(len(texts), 8)) as executor:
            futures = [
                executor.submit(self._embed_ollama_single, text) for text in texts
            ]

            for future in as_completed(futures):
                try:
                    emb = future.result()
                    embeddings.append(emb)
                except Exception as e:
                    print(f"  ⚠️ Ollama embed failed: {e}")
                    embeddings.append([0.0] * 1536)

        return embeddings

    def _embed_ollama_single(self, text: str) -> List[float]:
        """Single Ollama embedding."""
        response = self.session.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["embedding"]

    def _embed_openai_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch embedding with OpenAI."""
        response = self.session.post(
            "https://api.openai.com/v1/embeddings",
            json={"model": self.model, "input": texts},
            timeout=60,
        )
        response.raise_for_status()

        result = response.json()
        # Sort by index to maintain order
        embeddings = sorted(result["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in embeddings]

    async def embed_batch_async(
        self, texts: List[str], batch_size: Optional[int] = None
    ) -> List[List[float]]:
        """
        Async batch embedding.

        Args:
            texts: List of texts
            batch_size: Batch size

        Returns:
            List of embeddings
        """
        batch_size = batch_size or self.batch_size

        async with aiohttp.ClientSession() as session:
            tasks = []

            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                task = self._embed_batch_async(session, batch)
                tasks.append(task)

            # Execute all batches concurrently
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Flatten results
            all_embeddings = []
            for result in batch_results:
                if isinstance(result, Exception):
                    print(f"  ❌ Batch failed: {result}")
                    # Add placeholder embeddings
                    all_embeddings.extend([[0.0] * 1536] * batch_size)
                else:
                    all_embeddings.extend(result)

            return all_embeddings[: len(texts)]

    async def _embed_batch_async(
        self, session: aiohttp.ClientSession, texts: List[str]
    ) -> List[List[float]]:
        """Async batch embedding helper."""
        if self.provider == "openai":
            url = "https://api.openai.com/v1/embeddings"
            headers = {"Authorization": f"Bearer {self.api_key}"}
        else:
            url = f"{self.base_url}/api/embed"
            headers = {}

        async with session.post(
            url,
            json={"model": self.model, "input": texts},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as response:
            response.raise_for_status()
            result = await response.json()

            if self.provider == "openai":
                embeddings = sorted(result["data"], key=lambda x: x["index"])
                return [item["embedding"] for item in embeddings]
            else:
                return result.get("embeddings", [])

    def close(self):
        """Close session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class EmbeddingCacheLayer:
    """
    L1/L2 caching layer for embeddings.

    L1: In-memory LRU cache (fast)
    L2: Disk/SQLite cache (persistent)
    """

    def __init__(self, l1_size: int = 10000, l2_storage=None):
        """
        Initialize cache layer.

        Args:
            l1_size: Max entries in L1 cache
            l2_storage: L2 storage backend
        """
        from functools import lru_cache

        self.l1_size = l1_size
        self.l2_storage = l2_storage

        # L1: Simple LRU using functools
        self._l1_get = lru_cache(maxsize=l1_size)(self._l1_compute)

    def _l1_compute(self, text_hash: str) -> Optional[List[float]]:
        """L1 miss - try L2."""
        if self.l2_storage:
            return self.l2_storage.get(text_hash)
        return None

    def get(self, text: str) -> Optional[List[float]]:
        """Get embedding from cache."""
        import hashlib

        text_hash = hashlib.md5(text.encode()).hexdigest()
        return self._l1_get(text_hash)

    def set(self, text: str, embedding: List[float]):
        """Store embedding in cache."""
        import hashlib

        text_hash = hashlib.md5(text.encode()).hexdigest()

        # L1 is handled by LRU cache
        # L2
        if self.l2_storage:
            self.l2_storage.set(text_hash, embedding)
