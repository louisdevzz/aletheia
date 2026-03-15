"""
Token Manager Module

Precise token counting using tiktoken for OpenAI models.
Prevents truncation by ensuring chunks fit within model limits.

Usage:
    manager = TokenManager(model='text-embedding-3-small')
    token_count = manager.count_tokens(text)
    chunks = manager.chunk_by_tokens(text, max_tokens=512)
"""

from typing import List, Dict, Optional
import tiktoken


class TokenManager:
    """
    Manages token counting and chunking for OpenAI models.
    """

    # Model to encoding mapping
    MODEL_ENCODINGS = {
        "text-embedding-3-small": "cl100k_base",
        "text-embedding-3-large": "cl100k_base",
        "text-embedding-ada-002": "cl100k_base",
        "gpt-4": "cl100k_base",
        "gpt-4-turbo": "cl100k_base",
        "gpt-3.5-turbo": "cl100k_base",
    }

    # Default model limits
    MODEL_LIMITS = {
        "text-embedding-3-small": 8191,
        "text-embedding-3-large": 8191,
        "text-embedding-ada-002": 8191,
    }

    def __init__(self, model: str = "text-embedding-3-small"):
        """
        Initialize token manager.

        Args:
            model: OpenAI model name
        """
        self.model = model
        self.encoding_name = self.MODEL_ENCODINGS.get(model, "cl100k_base")
        self.encoding = tiktoken.get_encoding(self.encoding_name)
        self.max_tokens = self.MODEL_LIMITS.get(model, 8191)

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.

        Args:
            text: Input text

        Returns:
            Number of tokens
        """
        return len(self.encoding.encode(text))

    def count_tokens_batch(self, texts: List[str]) -> List[int]:
        """
        Count tokens for multiple texts.

        Args:
            texts: List of texts

        Returns:
            List of token counts
        """
        return [self.count_tokens(text) for text in texts]

    def chunk_by_tokens(
        self, text: str, max_tokens: int = 512, overlap_tokens: int = 50
    ) -> List[Dict]:
        """
        Chunk text by token count with overlap.

        Args:
            text: Input text
            max_tokens: Maximum tokens per chunk
            overlap_tokens: Tokens to overlap between chunks

        Returns:
            List of chunk dicts
        """
        tokens = self.encoding.encode(text)

        if len(tokens) <= max_tokens:
            return [
                {
                    "text": text,
                    "tokens": len(tokens),
                    "start_idx": 0,
                    "end_idx": len(text),
                }
            ]

        chunks = []
        start = 0

        while start < len(tokens):
            end = min(start + max_tokens, len(tokens))

            # Decode chunk
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoding.decode(chunk_tokens)

            chunks.append(
                {
                    "text": chunk_text,
                    "tokens": len(chunk_tokens),
                    "start_idx": start,
                    "end_idx": end,
                }
            )

            # Move with overlap
            start = end - overlap_tokens if end < len(tokens) else end

        return chunks

    def truncate_to_tokens(
        self, text: str, max_tokens: int, add_ellipsis: bool = True
    ) -> str:
        """
        Truncate text to fit within token limit.

        Args:
            text: Input text
            max_tokens: Maximum tokens
            add_ellipsis: Add "..." if truncated

        Returns:
            Truncated text
        """
        tokens = self.encoding.encode(text)

        if len(tokens) <= max_tokens:
            return text

        # Reserve tokens for ellipsis
        if add_ellipsis:
            ellipsis_tokens = self.encoding.encode("... ")
            max_tokens -= len(ellipsis_tokens)

        # Truncate
        truncated_tokens = tokens[:max_tokens]
        truncated_text = self.encoding.decode(truncated_tokens)

        if add_ellipsis:
            truncated_text += "..."

        return truncated_text

    def validate_chunks(
        self, chunks: List[Dict], max_tokens: Optional[int] = None
    ) -> Dict:
        """
        Validate chunks are within token limits.

        Args:
            chunks: List of chunk dicts
            max_tokens: Maximum allowed tokens

        Returns:
            Validation result with stats
        """
        max_tokens = max_tokens or self.max_tokens

        results = {
            "valid": True,
            "total_chunks": len(chunks),
            "total_tokens": 0,
            "oversized_chunks": [],
            "warnings": [],
        }

        for i, chunk in enumerate(chunks):
            text = chunk.get("text", "")
            token_count = self.count_tokens(text)

            results["total_tokens"] += token_count

            if token_count > max_tokens:
                results["valid"] = False
                results["oversized_chunks"].append(
                    {"index": i, "tokens": token_count, "max_allowed": max_tokens}
                )

        if results["oversized_chunks"]:
            results["warnings"].append(
                f"{len(results['oversized_chunks'])} chunks exceed token limit"
            )

        return results

    def get_model_info(self) -> Dict:
        """Get information about current model."""
        return {
            "model": self.model,
            "encoding": self.encoding_name,
            "max_tokens": self.max_tokens,
        }


class AdaptiveChunkManager:
    """
    Manages chunking strategy based on content type and model.
    """

    def __init__(self, model: str = "text-embedding-3-small"):
        self.token_manager = TokenManager(model)
        self.max_tokens = self.token_manager.max_tokens

    def create_chunks(
        self, items: List[Dict], max_tokens: Optional[int] = None
    ) -> List[Dict]:
        """
        Create optimized chunks from items.

        Args:
            items: List of content items
            max_tokens: Max tokens per chunk

        Returns:
            List of chunks with metadata
        """
        max_tokens = max_tokens or self.max_tokens
        all_chunks = []

        for item in items:
            text = item.get("text", "")
            item_type = item.get("item_type", "text")

            # Check if item needs chunking
            token_count = self.token_manager.count_tokens(text)

            if token_count <= max_tokens:
                # Fits in one chunk
                all_chunks.append(
                    {
                        **item,
                        "chunk_id": f"{item.get('id')}_0",
                        "chunk_index": 0,
                        "total_chunks": 1,
                        "tokens": token_count,
                    }
                )
            else:
                # Needs chunking
                chunks = self.token_manager.chunk_by_tokens(
                    text, max_tokens=max_tokens, overlap_tokens=50
                )

                # Add metadata
                for i, chunk in enumerate(chunks):
                    all_chunks.append(
                        {
                            "id": f"{item.get('id')}_{i}",
                            "parent_id": item.get("id"),
                            "text": chunk["text"],
                            "tokens": chunk["tokens"],
                            "item_type": item_type,
                            "page_num": item.get("page_num"),
                            "chunk_id": f"{item.get('id')}_{i}",
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                        }
                    )

        return all_chunks

    def merge_small_chunks(
        self,
        chunks: List[Dict],
        min_tokens: int = 100,
        max_tokens: Optional[int] = None,
    ) -> List[Dict]:
        """
        Merge small chunks to improve efficiency.

        Args:
            chunks: List of chunks
            min_tokens: Minimum tokens per chunk
            max_tokens: Maximum tokens per merged chunk

        Returns:
            List of merged chunks
        """
        max_tokens = max_tokens or self.max_tokens

        merged = []
        current_chunk = None

        for chunk in chunks:
            if current_chunk is None:
                current_chunk = chunk.copy()
            elif current_chunk["tokens"] + chunk["tokens"] <= max_tokens:
                # Merge
                current_chunk["text"] += " " + chunk["text"]
                current_chunk["tokens"] += chunk["tokens"]
                current_chunk["merged_from"] = current_chunk.get("merged_from", []) + [
                    chunk["id"]
                ]
            else:
                # Save current and start new
                merged.append(current_chunk)
                current_chunk = chunk.copy()

        # Don't forget last chunk
        if current_chunk:
            merged.append(current_chunk)

        return merged
