"""
Smart Metadata Filter - Heuristic-based approach

Instead of hardcoded regex patterns, uses document structure analysis
to identify and filter metadata.

Strategies:
1. Positional analysis (top/bottom of page)
2. Repetition detection (appears on every page)
3. Statistical analysis (short lines, special formatting)
4. Content density scoring

Usage:
    filter = SmartMetadataFilter()
    clean_text = filter.filter_document(pages)
"""

import re
from typing import List, Dict, Set, Tuple
from collections import defaultdict
import statistics


class SmartMetadataFilter:
    """
    Filters metadata using document structure analysis rather than hardcoded patterns.
    """

    def __init__(
        self,
        short_line_threshold: int = 50,
        repetition_threshold: float = 0.8,
        header_lines: int = 5,
        footer_lines: int = 5,
    ):
        """
        Initialize filter with configurable thresholds.

        Args:
            short_line_threshold: Max length for "short" lines (likely metadata)
            repetition_threshold: Ratio of pages a line must appear to be considered repeating
            header_lines: Number of lines at top to analyze for headers
            footer_lines: Number of lines at bottom to analyze for footers
        """
        self.short_line_threshold = short_line_threshold
        self.repetition_threshold = repetition_threshold
        self.header_lines = header_lines
        self.footer_lines = footer_lines

    def filter_document(self, pages: List[str]) -> List[str]:
        """
        Filter metadata from a multi-page document.

        Args:
            pages: List of page contents

        Returns:
            List of filtered page contents
        """
        if not pages:
            return []

        # Step 1: Detect repeating headers/footers
        repeating_lines = self._detect_repeating_lines(pages)

        # Step 2: Detect positional patterns (always at top/bottom)
        positional_patterns = self._detect_positional_patterns(pages)

        # Step 3: Filter each page
        filtered_pages = []
        for page in pages:
            filtered = self._filter_page(page, repeating_lines, positional_patterns)
            filtered_pages.append(filtered)

        return filtered_pages

    def filter_content(self, text: str) -> str:
        """
        Filter metadata from a single text content.

        Args:
            text: Text content to filter

        Returns:
            Filtered text with metadata removed
        """
        if not text or not text.strip():
            return text

        lines = text.split("\n")
        filtered_lines = []

        for line in lines:
            normalized = self._normalize_line(line)

            # Skip very short lines (likely page numbers, etc.)
            if self._is_likely_metadata(line):
                continue

            # Skip if it's just whitespace or common metadata patterns
            if len(normalized) < 3:
                continue

            filtered_lines.append(line)

        return "\n".join(filtered_lines)

    def _detect_repeating_lines(self, pages: List[str]) -> Set[str]:
        """
        Detect lines that appear on most pages (likely headers/footers).

        Uses normalized similarity to catch slight variations.
        """
        if len(pages) < 2:
            return set()

        # Normalize and count occurrences
        line_counts = defaultdict(int)
        total_pages = len(pages)

        for page in pages:
            seen_in_page = set()
            lines = page.split("\n")

            for line in lines:
                normalized = self._normalize_line(line)
                if normalized and normalized not in seen_in_page:
                    line_counts[normalized] += 1
                    seen_in_page.add(normalized)

        # Find lines appearing on > threshold of pages
        threshold = int(total_pages * self.repetition_threshold)
        repeating = set()

        for normalized_line, count in line_counts.items():
            if count >= threshold:
                repeating.add(normalized_line)

        return repeating

    def _detect_positional_patterns(self, pages: List[str]) -> Dict[str, Set[str]]:
        """
        Detect patterns that consistently appear at specific positions.

        Returns dict with 'header' and 'footer' pattern sets.
        """
        if len(pages) < 2:
            return {"header": set(), "footer": set()}

        header_candidates = []
        footer_candidates = []

        for page in pages:
            lines = page.split("\n")

            # Header candidates (first N non-empty lines)
            header_lines = [
                self._normalize_line(line)
                for line in lines[: self.header_lines]
                if line.strip()
            ]
            header_candidates.append(header_lines)

            # Footer candidates (last N non-empty lines)
            footer_lines = [
                self._normalize_line(line)
                for line in lines[-self.footer_lines :]
                if line.strip()
            ]
            footer_candidates.append(footer_lines)

        # Find consistent header/footer patterns
        header_patterns = self._find_consistent_patterns(header_candidates)
        footer_patterns = self._find_consistent_patterns(footer_candidates)

        return {"header": header_patterns, "footer": footer_patterns}

    def _find_consistent_patterns(self, page_sections: List[List[str]]) -> Set[str]:
        """Find lines that consistently appear in the same position."""
        if not page_sections or len(page_sections) < 2:
            return set()

        consistent = set()
        max_lines = max(len(section) for section in page_sections)

        for pos in range(max_lines):
            lines_at_pos = []
            for section in page_sections:
                if pos < len(section):
                    lines_at_pos.append(section[pos])

            if len(lines_at_pos) >= len(page_sections) * 0.8:
                # Check if mostly the same (allowing for page numbers)
                if self._are_similar(lines_at_pos):
                    consistent.update(lines_at_pos)

        return consistent

    def _filter_page(
        self,
        page: str,
        repeating_lines: Set[str],
        positional_patterns: Dict[str, Set[str]],
    ) -> str:
        """Filter a single page based on detected patterns."""
        lines = page.split("\n")
        filtered_lines = []

        for i, line in enumerate(lines):
            normalized = self._normalize_line(line)

            # Skip if matches repeating pattern
            if normalized in repeating_lines:
                continue

            # Skip if matches header/footer pattern and in header/footer zone
            if i < self.header_lines and normalized in positional_patterns["header"]:
                continue
            if (
                i >= len(lines) - self.footer_lines
                and normalized in positional_patterns["footer"]
            ):
                continue

            # Skip very short lines (likely page numbers, etc.)
            if self._is_likely_metadata(line):
                continue

            filtered_lines.append(line)

        return "\n".join(filtered_lines)

    def _normalize_line(self, line: str) -> str:
        """Normalize line for comparison."""
        # Lowercase, strip whitespace, remove page numbers
        normalized = line.strip().lower()
        # Remove digits (page numbers, years, etc.)
        normalized = re.sub(r"\d+", "", normalized)
        # Normalize whitespace
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _are_similar(self, lines: List[str], threshold: float = 0.8) -> bool:
        """Check if most lines are similar (for detecting patterns with varying numbers)."""
        if len(lines) < 2:
            return True

        # Group by similarity
        groups = []
        for line in lines:
            found_group = False
            for group in groups:
                if self._similarity(line, group[0]) >= threshold:
                    group.append(line)
                    found_group = True
                    break
            if not found_group:
                groups.append([line])

        # Check if one dominant group
        largest_group = max(len(g) for g in groups)
        return largest_group / len(lines) >= threshold

    def _similarity(self, s1: str, s2: str) -> float:
        """Calculate simple similarity between two strings."""
        if not s1 or not s2:
            return 0.0

        # Use Jaccard similarity on words
        words1 = set(s1.split())
        words2 = set(s2.split())

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _is_likely_metadata(self, line: str) -> bool:
        """
        Heuristic check if a line is likely metadata.

        Uses statistical properties rather than hardcoded patterns.
        """
        stripped = line.strip()

        # Too short
        if len(stripped) < 5:
            return True

        # Very short compared to average (if we had context)
        if len(stripped) < self.short_line_threshold:
            # Additional checks for short lines
            # High ratio of special characters
            special_chars = len(re.findall(r"[^\w\s]", stripped))
            if len(stripped) > 0 and special_chars / len(stripped) > 0.3:
                return True

            # Looks like an email or URL (but not a citation)
            if re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", stripped):
                return True
            if re.match(r"^https?://", stripped):
                return True

        # All uppercase (often headers)
        if stripped.isupper() and len(stripped) < 100:
            # But might be section headings, so check length
            if len(stripped.split()) < 5:
                return True

        return False


class ContentScorer:
    """
    Scores content quality to identify metadata vs. actual content.
    """

    def __init__(self):
        self.min_content_score = 0.3

    def score_line(self, line: str, context: Dict = None) -> float:
        """
        Score a line's likelihood of being actual content.

        Returns score 0.0-1.0, higher = more likely content.
        """
        stripped = line.strip()
        if not stripped:
            return 0.0

        scores = []

        # Length score (longer = more likely content)
        length_score = min(len(stripped) / 200, 1.0)
        scores.append(length_score)

        # Sentence structure score
        has_sentence_end = any(c in stripped for c in ".!?")
        scores.append(1.0 if has_sentence_end else 0.3)

        # Word diversity score
        words = stripped.split()
        if words:
            unique_ratio = len(set(words)) / len(words)
            scores.append(unique_ratio)

        # Content indicator words
        content_indicators = [
            "the",
            "and",
            "of",
            "to",
            "in",
            "is",
            "that",
            "for",
        ]
        indicator_count = sum(1 for w in content_indicators if w in stripped.lower())
        scores.append(min(indicator_count / 4, 1.0))

        # Average score
        return statistics.mean(scores)

    def is_content(self, line: str, threshold: float = None) -> bool:
        """Check if line is likely actual content."""
        threshold = threshold or self.min_content_score
        return self.score_line(line) >= threshold
