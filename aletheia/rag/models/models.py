"""
Database models using SQLAlchemy for Alembic migrations.
Similar to Drizzle schema in TypeScript.
"""
from sqlalchemy import Column, String, Integer, Text, ForeignKey, TIMESTAMP, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


class Document(Base):
    """Document table - stores PDF metadata."""
    __tablename__ = 'documents'
    
    doc_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(Text, nullable=False)
    total_pages = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    doc_metadata = Column(JSON)  # Renamed from 'metadata' to avoid SQLAlchemy conflict



class Sentence(Base):
    """Sentence table - stores text with offsets."""
    __tablename__ = 'sentences'
    
    id = Column(Text, primary_key=True)
    doc_id = Column(UUID(as_uuid=True), ForeignKey('documents.doc_id', ondelete='CASCADE'), nullable=False)
    page_num = Column(Integer, nullable=False)
    paragraph_id = Column(Text, nullable=False)
    sentence_id = Column(Text, nullable=False)
    text = Column(Text, nullable=False)
    char_offset_start = Column(Integer, nullable=False)
    char_offset_end = Column(Integer, nullable=False)
    item_type = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Indexes are defined in Alembic migration

class ChatHistory(Base):
    """Chat history table."""
    __tablename__ = 'chat_messages'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    role = Column(String, nullable=False) # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    sources = Column(JSON, nullable=True) # Store source metadata for citations
    created_at = Column(TIMESTAMP, server_default=func.now())
