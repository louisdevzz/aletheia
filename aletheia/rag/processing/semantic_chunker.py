"""
Semantic Chunking Module

Chunks text based on semantic coherence rather than just paragraph boundaries.
Uses sentence embeddings to detect topic shifts.

Usage:
    chunker = SemanticChunker(model_name='all-MiniLM-L6-v2')
    chunks = chunker.chunk(text, max_tokens=512)
"""

from typing import List, Dict, Tuple, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import nltk

# Download punkt if needed
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt", quiet=True)


class SemanticChunker:
    """
    Semantic chunker using sentence embeddings.

    For production: switch to 'BAAI/bge-base-en' or similar
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        similarity_threshold: float = 0.7,
        max_tokens: int = 512,
        overlap_sentences: int = 1,
    ):
        """
        Initialize semantic chunker.

        Args:
            model_name: Sentence transformer model
            similarity_threshold: Cosine similarity threshold (0.0-1.0)
            max_tokens: Maximum tokens per chunk
            overlap_sentences: Number of sentences to overlap between chunks
        """
        self.model = SentenceTransformer(model_name)
        self.similarity_threshold = similarity_threshold
        self.max_tokens = max_tokens
        self.overlap_sentences = overlap_sentences

    def chunk(self, text: str, max_tokens: Optional[int] = None) -> List[Dict]:
        """
        Chunk text semantically.

        Args:
            text: Input text
            max_tokens: Override default max_tokens

        Returns:
            List of chunk dicts with 'text', 'start_idx', 'end_idx', 'sentences'
        """
        max_tokens = max_tokens or self.max_tokens

        # Split into sentences
        sentences = nltk.sent_tokenize(text)
        if len(sentences) <= 1:
            return [
                {
                    "text": text,
                    "start_idx": 0,
                    "end_idx": len(text),
                    "sentences": sentences,
                    "token_count": self._estimate_tokens(text),
                }
            ]

        # Get embeddings
        embeddings = self.model.encode(sentences)

        # Group sentences into chunks
        chunks = []
        current_chunk_sentences = [sentences[0]]
        current_chunk_embeddings = [embeddings[0]]
        current_token_count = self._estimate_tokens(sentences[0])

        for i in range(1, len(sentences)):
            sentence = sentences[i]
            embedding = embeddings[i]
            sentence_tokens = self._estimate_tokens(sentence)

            # Check if we should start a new chunk
            should_split = False

            # Reason 1: Semantic shift
            if current_chunk_embeddings:
                avg_embedding = np.mean(current_chunk_embeddings, axis=0)
                similarity = cosine_similarity([avg_embedding], [embedding])[0][0]

                if similarity < self.similarity_threshold:
                    should_split = True

            # Reason 2: Token limit
            if current_token_count + sentence_tokens > max_tokens:
                should_split = True

            if should_split and current_chunk_sentences:
                # Save current chunk
                chunk_text = " ".join(current_chunk_sentences)
                chunks.append(
                    {
                        "text": chunk_text,
                        "start_idx": text.find(current_chunk_sentences[0]),
                        "end_idx": text.find(current_chunk_sentences[-1])
                        + len(current_chunk_sentences[-1]),
                        "sentences": current_chunk_sentences.copy(),
                        "token_count": current_token_count,
                    }
                )

                # Start new chunk with overlap
                overlap = (
                    current_chunk_sentences[-self.overlap_sentences :]
                    if self.overlap_sentences > 0
                    else []
                )
                current_chunk_sentences = overlap + [sentence]
                current_chunk_embeddings = [
                    embeddings[max(0, i - self.overlap_sentences + j)]
                    for j in range(len(overlap))
                ] + [embedding]
                current_token_count = sum(
                    self._estimate_tokens(s) for s in current_chunk_sentences
                )
            else:
                # Add to current chunk
                current_chunk_sentences.append(sentence)
                current_chunk_embeddings.append(embedding)
                current_token_count += sentence_tokens

        # Don't forget the last chunk
        if current_chunk_sentences:
            chunk_text = " ".join(current_chunk_sentences)
            chunks.append(
                {
                    "text": chunk_text,
                    "start_idx": text.find(current_chunk_sentences[0]),
                    "end_idx": text.find(current_chunk_sentences[-1])
                    + len(current_chunk_sentences[-1]),
                    "sentences": current_chunk_sentences,
                    "token_count": current_token_count,
                }
            )

        return chunks

    def chunk_with_hierarchy(
        self, text: str, section_markers: Optional[List[str]] = None
    ) -> Dict:
        """
        Create hierarchical chunks (section -> paragraph -> sentence).

        Args:
            text: Input text
            section_markers: List of section heading patterns

        Returns:
            Hierarchical structure
        """
        if section_markers is None:
            section_markers = [
                r"^\d+\.\s+\w+",  # "1. Introduction"
                r"^(Abstract|Introduction|Methods?|Results?|Discussion|Conclusion|References?)",
            ]

        # Split into sections
        sections = self._split_by_sections(text, section_markers)

        hierarchy = {"sections": []}

        for section_title, section_text in sections:
            # Chunk each section
            chunks = self.chunk(section_text)

            hierarchy["sections"].append(
                {"title": section_title, "text": section_text, "chunks": chunks}
            )

        return hierarchy

    def _split_by_sections(
        self, text: str, section_markers: List[str]
    ) -> List[Tuple[str, str]]:
        """Split text by section markers."""
        import re

        sections = []
        current_title = "Untitled"
        current_text = []

        lines = text.split("\n")

        for line in lines:
            is_section = False
            for marker in section_markers:
                if re.match(marker, line.strip(), re.IGNORECASE):
                    # Save previous section
                    if current_text:
                        sections.append((current_title, "\n".join(current_text)))
                    current_title = line.strip()
                    current_text = []
                    is_section = True
                    break

            if not is_section:
                current_text.append(line)

        # Save last section
        if current_text:
            sections.append((current_title, "\n".join(current_text)))

        return sections if sections else [("Full Text", text)]

    def _estimate_tokens(self, text: str) -> int:
        """
        Rough token estimation (words * 1.3 for safety).

        For precise counting, use tiktoken.
        """
        words = len(text.split())
        return int(words * 1.3)

    def get_chunk_embeddings(self, chunks: List[Dict]) -> np.ndarray:
        """Get embeddings for chunks (for retrieval)."""
        texts = [chunk["text"] for chunk in chunks]
        return self.model.encode(texts)


class ProductionSemanticChunker(SemanticChunker):
    """
    Production version with BGE-base model.

    Usage:
        chunker = ProductionSemanticChunker()
        chunks = chunker.chunk(text)
    """

    def __init__(self, **kwargs):
        # Force BGE-base model
        kwargs["model_name"] = "BAAI/bge-base-en"
        super().__init__(**kwargs)


class AdaptiveChunker:
    """
    Adaptive chunker that adjusts strategy based on content type.
    """

    def __init__(self):
        self.semantic_chunker = SemanticChunker()
        self.max_chunk_size = 512

    def chunk_item(self, item: Dict) -> List[Dict]:
        """
        Chunk a single item based on its type.

        Args:
            item: Item dict with 'text' and 'item_type'

        Returns:
            List of chunks
        """
        item_type = item.get("item_type", "text")
        text = item.get("text", "")

        if item_type == "table":
            # Tables usually shouldn't be split
            return [item]

        elif item_type == "equation":
            # Equations shouldn't be split
            return [item]

        elif item_type == "figure":
            # Figure captions - keep together
            return [item]

        else:
            # Text - use semantic chunking
            chunks = self.semantic_chunker.chunk(text, max_tokens=self.max_chunk_size)

            # Add metadata to chunks
            for chunk in chunks:
                chunk["parent_id"] = item.get("id")
                chunk["item_type"] = item_type
                chunk["page_num"] = item.get("page_num")

            return chunks
