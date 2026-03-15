"""
Document Data Types

Defines the core data structures for document parsing:
- Sentence, Paragraph, DisplayMath, Table, Figure
- Page, Document
"""
from typing import List
from dataclasses import dataclass


@dataclass
class Sentence:
    """A single sentence with offset tracking."""
    id: str
    text: str
    offset_start: int = 0
    offset_end: int = 0


@dataclass
class Paragraph:
    """A paragraph containing multiple sentences."""
    id: str
    sentences: List[Sentence]


@dataclass
class DisplayMath:
    """A display math block with LaTeX."""
    id: str
    latex: str


@dataclass
class Table:
    """A table with HTML representation."""
    id: str
    html: str


@dataclass
class Figure:
    """A figure with description and placeholder."""
    id: str
    description: str
    placeholder: str


@dataclass
class Page:
    """A page containing multiple items."""
    id: str
    items: List


@dataclass
class Document:
    """A document containing multiple pages."""
    pages: List[Page]
