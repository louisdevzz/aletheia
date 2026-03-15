"""
Cumulative Summarizer Module
Implements batch incremental summarization with table/formula handling.
"""

import re
import time
from typing import List, Dict, Optional, Tuple
from aletheia.config.settings import retrieval_config
from aletheia.rag.prompts import (
    BATCH_SUMMARY_INITIAL,
    BATCH_SUMMARY_INCREMENTAL,
    TABLE_FALLBACK_PROMPT,
)


class CumulativeSummarizer:
    """
    Handles incremental batch summarization for cumulative context.

    Features:
    - Batch summarization (configurable batch size)
    - Content type detection (text/table/formula)
    - Retry mechanism with fallback
    - Table caption extraction
    - Formula LaTeX preservation
    """

    def __init__(self, generator):
        """
        Initialize summarizer.

        Args:
            generator: LLMGenerator instance for summarization
        """
        self.generator = generator
        self.batch_size = retrieval_config.batch_size
        self.max_retries = retrieval_config.max_retries
        self.timeout = retrieval_config.timeout_seconds

    def detect_content_type(self, chunk: Dict) -> str:
        """
        Detect chunk content type.

        Args:
            chunk: Paragraph dictionary with 'item_type' and 'text'

        Returns:
            "text", "table", or "formula"
        """
        # Primary: Check database field
        if "item_type" in chunk:
            item_type = chunk.get("item_type", "paragraph").lower()
            if item_type == "table":
                return "table"
            elif item_type in ["math", "formula", "equation"]:
                return "formula"

        # Fallback: Heuristic detection
        text = chunk.get("text", "")

        # Table detection
        if self._is_table(text):
            return "table"

        # Formula detection
        if self._is_formula(text):
            return "formula"

        return "text"

    def _is_table(self, text: str) -> bool:
        """Check if text looks like a table."""
        # Check for markdown table syntax
        if "|" in text and text.count("|") > 2:
            return True

        # Check for "Table" prefix
        if text.strip().startswith("Table") or text.strip().startswith("TABLE"):
            return True

        return False

    def _is_formula(self, text: str) -> bool:
        """Check if text contains mathematical formulas."""
        # LaTeX markers
        latex_markers = [r"\(", r"\[", r"$$", r"\begin{equation}"]
        if any(marker in text for marker in latex_markers):
            return True

        # Math keywords
        math_keywords = ["equation", "=", "∫", "∑", "∂", "≈", "≤", "≥"]
        # Must have multiple indicators
        indicator_count = sum(1 for keyword in math_keywords if keyword in text)
        if indicator_count >= 2:
            return True

        return False

    def extract_table_caption(self, table_chunk: Dict) -> str:
        """
        Extract table caption/title.

        Args:
            table_chunk: Table paragraph dictionary

        Returns:
            Caption string or empty string
        """
        text = table_chunk.get("text", "")

        # Pattern 1: "Table X.Y: Caption"
        pattern1 = r"Table\s+\d+\.?\d*\s*:\s*([^\n|]+)"
        match = re.search(pattern1, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()

        # Pattern 2: First line before table
        lines = text.split("\n")
        for line in lines:
            if line.strip() and "|" not in line:
                return line.strip()

        return ""

    def extract_table_structure(self, table_chunk: Dict) -> Dict:
        """
        Parse table into structured format.

        Args:
            table_chunk: Table paragraph dictionary

        Returns:
            {
                'caption': str,
                'header': List[str],
                'rows': List[List[str]],
                'raw_text': str
            }
        """
        text = table_chunk.get("text", "")
        lines = text.split("\n")

        caption = self.extract_table_caption(table_chunk)
        header = []
        rows = []

        # Parse markdown table
        for line in lines:
            if "|" in line:
                cells = [cell.strip() for cell in line.split("|") if cell.strip()]

                # Skip separator lines (---)
                if all(set(cell.strip()) <= {"-", " ", ":"} for cell in cells):
                    continue

                if not header:
                    header = cells
                else:
                    rows.append(cells)

        return {"caption": caption, "header": header, "rows": rows, "raw_text": text}

    def apply_table_strategy(self, table_chunk: Dict) -> Dict:
        """
        Decoupled Indexing: Preserve table without summarization.

        Args:
            table_chunk: Table paragraph dictionary

        Returns:
            Enriched table structure
        """
        structure = self.extract_table_structure(table_chunk)

        return {
            "type": "table",
            "caption": structure["caption"],
            "header": structure["header"],
            "rows": structure["rows"],
            "content": structure["raw_text"],
            "position": table_chunk.get("paragraph_id", ""),
            "page": table_chunk.get("page_num", 0),
        }

    def apply_formula_strategy(
        self, formula_chunk: Dict, all_chunks: List[Dict], position: int
    ) -> Dict:
        """
        Context Enrichment: Preserve formula with surrounding context.

        Args:
            formula_chunk: Formula paragraph dictionary
            all_chunks: All paragraphs in sequence
            position: Index of formula_chunk in all_chunks

        Returns:
            Enriched formula structure
        """
        # Get surrounding context
        context_before = ""
        context_after = ""

        if position > 0:
            prev_chunk = all_chunks[position - 1]
            context_before = prev_chunk.get("text", "")

        if position < len(all_chunks) - 1:
            next_chunk = all_chunks[position + 1]
            context_after = next_chunk.get("text", "")

        return {
            "type": "formula",
            "context_before": context_before,
            "formula_latex": formula_chunk.get("text", ""),
            "context_after": context_after,
            "position": formula_chunk.get("paragraph_id", ""),
            "page": formula_chunk.get("page_num", 0),
        }

    def _call_llm_with_retry(self, prompt: str) -> Tuple[bool, str]:
        """
        Call LLM with retry mechanism.

        Args:
            prompt: Prompt to send to LLM

        Returns:
            (success: bool, result: str)
        """
        for attempt in range(self.max_retries):
            try:
                # Only Kimi provider is supported
                resp = self.generator.client.chat.completions.create(
                    model=self.generator.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    timeout=self.timeout,
                )
                summary = resp.choices[0].message.content
                return True, summary

            except Exception as e:
                print(
                    f"⚠️ LLM call failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff
                continue

        return False, ""

    def _create_fallback_summary(
        self, chunks: List[Dict], chunk_type: str = "text"
    ) -> str:
        """
        Create fallback summary when LLM fails.

        Args:
            chunks: List of chunk dictionaries
            chunk_type: "text" or "table"

        Returns:
            Fallback summary string
        """
        if chunk_type == "table":
            # Use table structure: Caption + Header + First Row
            summaries = []
            for chunk in chunks:
                structure = self.extract_table_structure(chunk)
                caption = (
                    structure["caption"]
                    or f"Table at page {chunk.get('page_num', '?')}"
                )
                header = ", ".join(structure["header"][:5])  # First 5 columns
                first_row = (
                    ", ".join(structure["rows"][0][:5]) if structure["rows"] else ""
                )

                summaries.append(
                    f"{caption} - Columns: {header} - Example: {first_row}"
                )

            return " | ".join(summaries)
        else:
            # Text fallback: First 200 chars + Last 200 chars
            if len(chunks) == 0:
                return "[No content]"

            first_text = chunks[0].get("text", "")[:200]
            last_text = chunks[-1].get("text", "")[:200] if len(chunks) > 1 else ""

            return f"{first_text}... ... {last_text}"

    def summarize_batch(self, text_chunks: List[Dict]) -> str:
        """
        Perform batch incremental summarization.

        Workflow:
        1. Batch 1 (chunks 1-N): Initial summarization
        2. Batch 2 (summary_1 + chunks N+1-M): Incremental
        3. Continue until all chunks processed

        Args:
            text_chunks: List of text paragraph dictionaries (no tables/formulas)

        Returns:
            Final cumulative summary
        """
        if not text_chunks:
            return ""

        if len(text_chunks) == 1:
            # Single chunk, no need to summarize
            return text_chunks[0].get("text", "")

        running_summary = ""
        processed = 0

        while processed < len(text_chunks):
            # Get next batch
            batch_end = min(processed + self.batch_size, len(text_chunks))
            batch = text_chunks[processed:batch_end]

            if processed == 0:
                # Initial batch
                batch_text = "\n\n".join(
                    [
                        f"[Chunk {i + 1}]:\n{chunk.get('text', '')}"
                        for i, chunk in enumerate(batch)
                    ]
                )
                prompt = BATCH_SUMMARY_INITIAL.format(
                    batch_text=batch_text, num_chunks=len(batch)
                )
            else:
                # Incremental batch
                new_chunks_text = "\n\n".join(
                    [
                        f"[Chunk {processed + i + 1}]:\n{chunk.get('text', '')}"
                        for i, chunk in enumerate(batch)
                    ]
                )
                prompt = BATCH_SUMMARY_INCREMENTAL.format(
                    previous_summary=running_summary,
                    new_chunks=new_chunks_text,
                    prev_end=processed,
                    new_end=batch_end,
                )

            # Call LLM with retry
            success, summary = self._call_llm_with_retry(prompt)

            if success:
                running_summary = summary
            else:
                # Fallback
                print(f"⚠️ Fallback summary used for chunks {processed + 1}-{batch_end}")
                fallback = self._create_fallback_summary(batch, chunk_type="text")
                if running_summary:
                    running_summary = f"{running_summary}\n\n[Chunks {processed + 1}-{batch_end}]: {fallback}"
                else:
                    running_summary = fallback

            processed = batch_end

        return running_summary

    def assemble_context(
        self,
        summary: str,
        tables: List[Dict],
        formulas: List[Dict],
        current_chunk: Dict,
    ) -> str:
        """
        Assemble final enriched context.

        Args:
            summary: Text summary from batch summarization
            tables: List of table structures
            formulas: List of formula structures
            current_chunk: The target chunk (N)

        Returns:
            Formatted context string
        """
        parts = []

        # Text summary
        if summary:
            parts.append(f"=== CONTEXT SUMMARY ===\n{summary}\n")

        # Tables (preserved)
        if tables:
            parts.append("=== TABLES (Preserved) ===")
            for table in tables:
                caption = table["caption"] or f"Table at page {table['page']}"
                parts.append(f"\n[{caption}]")
                parts.append(table["content"])
            parts.append("")

        # Formulas (enriched)
        if formulas:
            parts.append("=== FORMULAS (with Context) ===")
            for formula in formulas:
                if formula["context_before"]:
                    parts.append(f"Context: {formula['context_before'][:200]}...")
                parts.append(f"\nFORMULA:\n{formula['formula_latex']}\n")
                if formula["context_after"]:
                    parts.append(f"Explanation: {formula['context_after'][:200]}...")
            parts.append("")

        # Current chunk
        parts.append(
            f"=== CURRENT CHUNK (Page {current_chunk.get('page_num', '?')}) ==="
        )
        parts.append(current_chunk.get("text", ""))

        return "\n".join(parts)
