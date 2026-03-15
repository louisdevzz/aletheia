"""
Content Deduplication Module

Removes duplicate content from parsed documents to prevent:
- Storage waste (duplicate embeddings)
- Search pollution (same results appearing multiple times)
- Citation confusion (same content cited from different "pages")

Usage:
    deduplicator = ContentDeduplicator(similarity_threshold=0.95)
    unique_items = deduplicator.deduplicate(items)
"""

import hashlib
import re
from typing import List, Dict, Set
from collections import defaultdict


class ContentDeduplicator:
    """
    Multi-strategy deduplicator supporting exact and fuzzy matching.
    """

    def __init__(
        self,
        exact_match: bool = True,
        fuzzy_match: bool = True,
        similarity_threshold: float = 0.95,
        min_text_length: int = 20,
    ):
        """
        Initialize deduplicator.

        Args:
            exact_match: Enable exact hash-based deduplication
            fuzzy_match: Enable fuzzy similarity-based deduplication
            similarity_threshold: Jaccard similarity threshold (0.0-1.0)
            min_text_length: Minimum text length to consider for dedup
        """
        self.exact_match = exact_match
        self.fuzzy_match = fuzzy_match
        self.similarity_threshold = similarity_threshold
        self.min_text_length = min_text_length

        # State tracking
        self.exact_hashes: Set[str] = set()
        self.text_fingerprints: List[Dict] = []

    def reset(self):
        """Reset internal state for new document processing."""
        self.exact_hashes.clear()
        self.text_fingerprints.clear()

    def deduplicate(self, items: List[Dict]) -> List[Dict]:
        """
        Remove duplicates from list of content items.

        Args:
            items: List of dicts with 'text' key

        Returns:
            Filtered list with duplicates removed
        """
        unique_items = []
        duplicates_found = 0

        for item in items:
            text = item.get("text", "")

            # Skip items with too short text
            if len(text.strip()) < self.min_text_length:
                unique_items.append(item)
                continue

            # Check if duplicate
            if self._is_duplicate(text):
                duplicates_found += 1
                continue

            # Add to fingerprints
            self._add_fingerprint(text)
            unique_items.append(item)

        if duplicates_found > 0:
            print(
                f"  🧹 Deduplication: Removed {duplicates_found} duplicates, kept {len(unique_items)} unique items"
            )

        return unique_items

    def _is_duplicate(self, text: str) -> bool:
        """Check if text is duplicate using exact and fuzzy matching."""
        normalized_text = self._normalize_text(text)

        # Exact match check
        if self.exact_match:
            text_hash = hashlib.md5(normalized_text.encode()).hexdigest()
            if text_hash in self.exact_hashes:
                return True

        # Fuzzy match check
        if self.fuzzy_match and self.text_fingerprints:
            similarity = self._compute_max_similarity(normalized_text)
            if similarity >= self.similarity_threshold:
                return True

        return False

    def _add_fingerprint(self, text: str):
        """Add text to fingerprint database."""
        normalized_text = self._normalize_text(text)

        if self.exact_match:
            text_hash = hashlib.md5(normalized_text.encode()).hexdigest()
            self.exact_hashes.add(text_hash)

        if self.fuzzy_match:
            # Store normalized text and word set for fuzzy matching
            word_set = set(normalized_text.split())
            self.text_fingerprints.append(
                {
                    "text": normalized_text,
                    "word_set": word_set,
                    "length": len(normalized_text),
                }
            )

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        # Lowercase
        text = text.lower().strip()

        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)

        # Remove common citation markers that might differ
        text = re.sub(r"\[\d+\]", "", text)

        return text

    def _compute_max_similarity(self, text: str) -> float:
        """Compute maximum Jaccard similarity with existing fingerprints."""
        word_set = set(text.split())
        text_length = len(text)

        max_similarity = 0.0

        for fingerprint in self.text_fingerprints:
            # Quick length check - if lengths differ too much, skip
            length_ratio = min(text_length, fingerprint["length"]) / max(
                text_length, fingerprint["length"]
            )
            if length_ratio < 0.8:  # Lengths differ by more than 20%
                continue

            # Compute Jaccard similarity
            intersection = len(word_set & fingerprint["word_set"])
            union = len(word_set | fingerprint["word_set"])

            if union > 0:
                similarity = intersection / union
                max_similarity = max(max_similarity, similarity)

                # Early exit if high similarity found
                if max_similarity >= self.similarity_threshold:
                    break

        return max_similarity

    def find_similar_groups(self, items: List[Dict]) -> List[List[int]]:
        """
        Find groups of similar items without removing them.

        Args:
            items: List of content items

        Returns:
            List of index groups where items are similar
        """
        groups = []
        processed = set()

        for i, item1 in enumerate(items):
            if i in processed:
                continue

            text1 = self._normalize_text(item1.get("text", ""))
            word_set1 = set(text1.split())

            group = [i]

            for j, item2 in enumerate(items[i + 1 :], start=i + 1):
                if j in processed:
                    continue

                text2 = self._normalize_text(item2.get("text", ""))
                word_set2 = set(text2.split())

                # Compute similarity
                intersection = len(word_set1 & word_set2)
                union = len(word_set1 | word_set2)

                if union > 0:
                    similarity = intersection / union
                    if similarity >= self.similarity_threshold:
                        group.append(j)
                        processed.add(j)

            if len(group) > 1:
                groups.append(group)
            processed.add(i)

        return groups

    def get_stats(self) -> Dict:
        """Get deduplication statistics."""
        return {
            "exact_hashes_count": len(self.exact_hashes),
            "fuzzy_fingerprints_count": len(self.text_fingerprints),
            "exact_match_enabled": self.exact_match,
            "fuzzy_match_enabled": self.fuzzy_match,
            "similarity_threshold": self.similarity_threshold,
        }


class DocumentLevelDeduplicator:
    """
    Deduplicator that works across multiple pages in a document.
    Maintains state across page processing.
    """

    def __init__(self, **kwargs):
        self.page_deduplicator = ContentDeduplicator(**kwargs)
        self.document_fingerprints = defaultdict(set)

    def process_page(self, page_num: int, items: List[Dict]) -> List[Dict]:
        """
        Process a single page, checking against both page-level and document-level duplicates.

        Args:
            page_num: Page number
            items: Content items from this page

        Returns:
            Deduplicated items
        """
        # Reset page-level state but keep document-level
        self.page_deduplicator.reset()

        unique_items = []

        for item in items:
            text = item.get("text", "")

            # Check document-level duplicates (across all pages)
            doc_hash = hashlib.md5(text.lower().strip().encode()).hexdigest()
            if doc_hash in self.document_fingerprints[page_num]:
                continue

            # Check page-level duplicates
            if self.page_deduplicator._is_duplicate(text):
                continue

            # Add to both levels
            self.page_deduplicator._add_fingerprint(text)
            self.document_fingerprints[page_num].add(doc_hash)
            unique_items.append(item)

        return unique_items

    def reset_document(self):
        """Reset document-level state for new document."""
        self.document_fingerprints.clear()
        self.page_deduplicator.reset()
