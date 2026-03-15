"""
Cross-Reference Resolution Module

Resolves inline citations (IEEE style) to their targets in the document.
Creates bidirectional links between text and referenced items.

Usage:
    resolver = CrossReferenceResolver()
    graph = resolver.build_graph(items)
    refs = resolver.get_references_to("table_1")
"""

import re
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class ReferenceType(Enum):
    """Types of cross-references."""

    TABLE = "table"
    FIGURE = "figure"
    EQUATION = "equation"
    SECTION = "section"
    CITATION = "citation"  # Bibliographic


@dataclass
class Reference:
    """Represents a cross-reference."""

    source_id: str
    target_id: str
    ref_type: ReferenceType
    ref_number: str
    context: str  # Surrounding text
    position: int  # Character position in source


@dataclass
class ReferenceTarget:
    """Represents a reference target (table, figure, etc.)."""

    id: str
    target_type: ReferenceType
    number: str
    caption: str
    content: str
    page_num: int
    item_type: str  # "table", "figure", "equation"
    referenced_by: List[str] = None  # List of source IDs that reference this target

    def __post_init__(self):
        if self.referenced_by is None:
            self.referenced_by = []


class CrossReferenceResolver:
    """
    Resolves IEEE-style cross-references in academic documents.
    """

    # IEEE citation patterns
    CITATION_PATTERNS = {
        ReferenceType.TABLE: [
            r"Table\s+(\d+)",
            r"Tab\.\s*(\d+)",
            r"table\s+(\d+)",
        ],
        ReferenceType.FIGURE: [
            r"Fig\.\s*(\d+)",
            r"Figure\s+(\d+)",
            r"fig\.\s*(\d+)",
            r"figure\s+(\d+)",
        ],
        ReferenceType.EQUATION: [
            r"equation\s*\(\s*(\d+)\s*\)",
            r"eq\.\s*\(\s*(\d+)\s*\)",
            r"Eq\.\s*\(\s*(\d+)\s*\)",
            r"\[(\d+)\]",  # Sometimes equations cited as [1]
        ],
        ReferenceType.SECTION: [
            r"section\s+(\d+\.?\d*)",
            r"Section\s+(\d+\.?\d*)",
            r"§\s*(\d+\.?\d*)",
        ],
        ReferenceType.CITATION: [
            r"\[(\d+)\]",  # [1], [2], etc.
            r"\[(\d+),\s*(\d+)\]",  # [1, 2]
            r"\[(\d+)[–-](\d+)\]",  # [1-3]
        ],
    }

    def __init__(self):
        """Initialize resolver with compiled patterns."""
        self.patterns = {}
        for ref_type, patterns in self.CITATION_PATTERNS.items():
            self.patterns[ref_type] = [re.compile(p) for p in patterns]

    def build_graph(self, items: List[Dict]) -> Dict[str, ReferenceTarget]:
        """
        Build reference graph from document items.

        Args:
            items: List of parsed items (paragraphs, tables, figures, etc.)

        Returns:
            Dictionary mapping target IDs to ReferenceTarget objects
        """
        # Step 1: Index all reference targets
        targets = self._index_targets(items)

        # Step 2: Find references in text
        references = []
        for item in items:
            if item.get("type") == "paragraph":
                refs = self._extract_references(item, targets)
                references.extend(refs)

        # Step 3: Link references to targets
        for ref in references:
            if ref.target_id in targets:
                target = targets[ref.target_id]
                if target.referenced_by is None:
                    target.referenced_by = []
                target.referenced_by.append(ref.source_id)

        return targets

    def _index_targets(self, items: List[Dict]) -> Dict[str, ReferenceTarget]:
        """Index all potential reference targets."""
        targets = {}

        for item in items:
            item_type = item.get("type")
            item_id = item.get("id", "")

            if item_type == "table":
                target = self._parse_table_target(item)
                if target:
                    targets[target.id] = target

            elif item_type == "figure":
                target = self._parse_figure_target(item)
                if target:
                    targets[target.id] = target

            elif item_type == "display_math":
                target = self._parse_equation_target(item)
                if target:
                    targets[target.id] = target

        return targets

    def _parse_table_target(self, item: Dict) -> Optional[ReferenceTarget]:
        """Parse a table item into ReferenceTarget."""
        text = item.get("text", "")

        # Try to extract "Table X" from caption
        match = re.search(r"Table\s+(\d+)", text, re.IGNORECASE)
        if not match:
            # Try to find table number in other formats
            match = re.search(r"Tab\.\s*(\d+)", text, re.IGNORECASE)

        if match:
            table_num = match.group(1)
            return ReferenceTarget(
                id=f"table_{table_num}",
                target_type=ReferenceType.TABLE,
                number=table_num,
                caption=text[:200],  # First 200 chars
                content=text,
                page_num=item.get("page_num", 0),
                item_type="table",
            )

        return None

    def _parse_figure_target(self, item: Dict) -> Optional[ReferenceTarget]:
        """Parse a figure item into ReferenceTarget."""
        text = item.get("text", "")

        # Try to extract "Figure X"
        match = re.search(r"Figure\s+(\d+)", text, re.IGNORECASE)
        if not match:
            match = re.search(r"Fig\.\s*(\d+)", text, re.IGNORECASE)

        if match:
            fig_num = match.group(1)
            return ReferenceTarget(
                id=f"figure_{fig_num}",
                target_type=ReferenceType.FIGURE,
                number=fig_num,
                caption=text[:200],
                content=text,
                page_num=item.get("page_num", 0),
                item_type="figure",
            )

        return None

    def _parse_equation_target(self, item: Dict) -> Optional[ReferenceTarget]:
        """Parse an equation item into ReferenceTarget."""
        eq_num = item.get("equation_number")

        if eq_num:
            return ReferenceTarget(
                id=f"equation_{eq_num}",
                target_type=ReferenceType.EQUATION,
                number=eq_num,
                caption=item.get("description", "")[:200],
                content=item.get("latex", ""),
                page_num=item.get("page_num", 0),
                item_type="equation",
            )

        return None

    def _extract_references(
        self, item: Dict, targets: Dict[str, ReferenceTarget]
    ) -> List[Reference]:
        """Extract all references from a text item."""
        text = item.get("text", "")
        item_id = item.get("id", "")
        references = []

        for ref_type, patterns in self.patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    ref_num = match.group(1)

                    # Build target ID
                    if ref_type == ReferenceType.TABLE:
                        target_id = f"table_{ref_num}"
                    elif ref_type == ReferenceType.FIGURE:
                        target_id = f"figure_{ref_num}"
                    elif ref_type == ReferenceType.EQUATION:
                        target_id = f"equation_{ref_num}"
                    else:
                        target_id = f"{ref_type.value}_{ref_num}"

                    # Get context (50 chars before and after)
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end]

                    ref = Reference(
                        source_id=item_id,
                        target_id=target_id,
                        ref_type=ref_type,
                        ref_number=ref_num,
                        context=context,
                        position=match.start(),
                    )
                    references.append(ref)

        return references

    def get_references_to(
        self, target_id: str, graph: Dict[str, ReferenceTarget]
    ) -> List[Reference]:
        """
        Get all references pointing to a specific target.

        Args:
            target_id: ID of the target (e.g., "table_1")
            graph: Reference graph

        Returns:
            List of Reference objects
        """
        refs = []

        for target in graph.values():
            if target.referenced_by:
                # Find the actual reference object
                # (Would need to store references separately in real implementation)
                pass

        return refs

    def get_context_for_target(
        self, target_id: str, items: List[Dict], window: int = 2
    ) -> List[Dict]:
        """
        Get context items surrounding a reference target.

        Args:
            target_id: Target ID
            items: All document items
            window: Number of items before/after to include

        Returns:
            List of context items
        """
        # Find target position
        target_idx = None
        for idx, item in enumerate(items):
            if item.get("id") == target_id:
                target_idx = idx
                break

        if target_idx is None:
            return []

        # Get window
        start = max(0, target_idx - window)
        end = min(len(items), target_idx + window + 1)

        return items[start:end]


class ReferenceGraphStorage:
    """
    Stores reference graph in SQLite for persistence.
    """

    def __init__(self, db_path: str):
        import sqlite3

        self.db_path = db_path
        self._init_table()

    def _get_connection(self):
        """Get database connection."""
        import sqlite3

        return sqlite3.connect(self.db_path)

    def _init_table(self):
        """Initialize cross_references table."""
        query = """
            CREATE TABLE IF NOT EXISTS cross_references (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT,
                source_item_id TEXT,
                target_item_id TEXT,
                ref_type TEXT,
                ref_number TEXT,
                context TEXT,
                position INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        with self._get_connection() as conn:
            conn.execute(query)
            conn.commit()

        # Create indexes
        with self._get_connection() as conn:
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cross_ref_source
                ON cross_references(source_item_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cross_ref_target
                ON cross_references(target_item_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cross_ref_doc
                ON cross_references(doc_id)
            """)
            conn.commit()

    def save_references(self, doc_id: str, references: List[Reference]):
        """Save references to database."""
        query = """
            INSERT INTO cross_references
            (doc_id, source_item_id, target_item_id, ref_type, ref_number, context, position)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        with self._get_connection() as conn:
            for ref in references:
                conn.execute(
                    query,
                    (
                        doc_id,
                        ref.source_id,
                        ref.target_id,
                        ref.ref_type.value,
                        ref.ref_number,
                        ref.context,
                        ref.position,
                    ),
                )
            conn.commit()

    def get_references_to_target(self, doc_id: str, target_id: str) -> List[Reference]:
        """Get all references to a specific target."""
        query = """
            SELECT source_item_id, target_item_id, ref_type, ref_number, context, position
            FROM cross_references
            WHERE doc_id = ? AND target_item_id = ?
        """

        with self._get_connection() as conn:
            rows = conn.execute(query, (doc_id, target_id)).fetchall()

        return [
            Reference(
                source_id=row[0],
                target_id=row[1],
                ref_type=ReferenceType(row[2]),
                ref_number=row[3],
                context=row[4],
                position=row[5],
            )
            for row in rows
        ]

    def get_references_from_source(
        self, doc_id: str, source_id: str
    ) -> List[Reference]:
        """Get all references from a specific source."""
        query = """
            SELECT source_item_id, target_item_id, ref_type, ref_number, context, position
            FROM cross_references
            WHERE doc_id = ? AND source_item_id = ?
        """

        with self._get_connection() as conn:
            rows = conn.execute(query, (doc_id, source_id)).fetchall()

        return [
            Reference(
                source_id=row[0],
                target_id=row[1],
                ref_type=ReferenceType(row[2]),
                ref_number=row[3],
                context=row[4],
                position=row[5],
            )
            for row in rows
        ]
