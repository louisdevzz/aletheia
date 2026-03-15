"""
Tests for SQLite storage layer.
"""
import tempfile
import shutil
from pathlib import Path

import pytest

from aletheia.storage.sqlite_store import SQLiteStore, create_sqlite_store


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.db"
    store = SQLiteStore(str(db_path))
    yield store
    store.close()
    shutil.rmtree(temp_dir)


class TestSQLiteStore:
    """Test SQLite storage functionality."""
    
    def test_database_creation(self, temp_db):
        """Test database file is created."""
        assert Path(temp_db.db_path).exists()
    
    def test_document_insert_and_get(self, temp_db):
        """Test document insertion and retrieval."""
        doc_id = temp_db.insert_document("test.pdf", 10, {"author": "Test"})
        assert doc_id is not None
        
        doc = temp_db.get_document(doc_id)
        assert doc is not None
        assert doc['filename'] == "test.pdf"
        assert doc['total_pages'] == 10
        assert doc['doc_metadata']['author'] == "Test"
    
    def test_sentence_insert_and_get(self, temp_db):
        """Test sentence operations."""
        doc_id = temp_db.insert_document("test.pdf", 1)
        
        sentences = [
            {
                'id': 's1',
                'page_num': 1,
                'paragraph_id': 'p1',
                'sentence_id': 's1',
                'text': 'First sentence.',
                'char_offset_start': 0,
                'char_offset_end': 15,
                'item_type': 'paragraph'
            },
            {
                'id': 's2',
                'page_num': 1,
                'paragraph_id': 'p1',
                'sentence_id': 's2',
                'text': 'Second sentence.',
                'char_offset_start': 16,
                'char_offset_end': 32,
                'item_type': 'paragraph'
            }
        ]
        
        temp_db.insert_sentences(doc_id, sentences)
        
        # Get by doc
        retrieved = temp_db.get_sentences_by_doc(doc_id)
        assert len(retrieved) == 2
        
        # Get by ID
        s1 = temp_db.get_sentence_by_id('s1')
        assert s1 is not None
        assert s1['text'] == 'First sentence.'
    
    def test_batch_operations(self, temp_db):
        """Test batch fetch operations."""
        doc_id = temp_db.insert_document("test.pdf", 1)
        
        sentences = [
            {
                'id': f's{i}',
                'page_num': 1,
                'paragraph_id': 'p1',
                'sentence_id': f's{i}',
                'text': f'Sentence {i}.',
                'char_offset_start': i * 20,
                'char_offset_end': i * 20 + 12,
                'item_type': 'paragraph'
            }
            for i in range(10)
        ]
        
        temp_db.insert_sentences(doc_id, sentences)
        
        # Batch fetch
        results = temp_db.get_sentences_by_ids_batch(['s1', 's5', 's9'])
        assert len(results) == 3
        assert results['s1']['text'] == 'Sentence 1.'
        assert results['s5']['text'] == 'Sentence 5.'
        assert results['s9']['text'] == 'Sentence 9.'
    
    def test_context_window(self, temp_db):
        """Test context window retrieval."""
        doc_id = temp_db.insert_document("test.pdf", 1)
        
        sentences = [
            {
                'id': f's{i}',
                'page_num': 1,
                'paragraph_id': 'p1',
                'sentence_id': f's{i}',
                'text': f'Sentence {i}.',
                'char_offset_start': i * 20,
                'char_offset_end': i * 20 + 12,
                'item_type': 'paragraph'
            }
            for i in range(10)
        ]
        
        temp_db.insert_sentences(doc_id, sentences)
        
        # Get context window around s5
        window = temp_db.get_context_window(doc_id, 's5', window_size=2)
        assert len(window) == 5  # s3, s4, s5, s6, s7
        
        texts = [s['text'] for s in window]
        assert 'Sentence 3.' in texts
        assert 'Sentence 5.' in texts
        assert 'Sentence 7.' in texts
    
    def test_paragraph_context(self, temp_db):
        """Test paragraph context retrieval."""
        doc_id = temp_db.insert_document("test.pdf", 1)
        
        # Multiple paragraphs
        sentences = [
            {
                'id': 's1',
                'page_num': 1,
                'paragraph_id': 'p1',
                'sentence_id': 's1',
                'text': 'Para 1 sent 1.',
                'char_offset_start': 0,
                'char_offset_end': 15,
                'item_type': 'paragraph'
            },
            {
                'id': 's2',
                'page_num': 1,
                'paragraph_id': 'p1',
                'sentence_id': 's2',
                'text': 'Para 1 sent 2.',
                'char_offset_start': 16,
                'char_offset_end': 31,
                'item_type': 'paragraph'
            },
            {
                'id': 's3',
                'page_num': 1,
                'paragraph_id': 'p2',
                'sentence_id': 's3',
                'text': 'Para 2 sent 1.',
                'char_offset_start': 32,
                'char_offset_end': 47,
                'item_type': 'paragraph'
            }
        ]
        
        temp_db.insert_sentences(doc_id, sentences)
        
        # Get paragraph p1
        p1_sentences = temp_db.get_paragraph_context(doc_id, 'p1')
        assert len(p1_sentences) == 2
        
        # Batch paragraph context
        batch = temp_db.get_paragraph_context_batch(['s1', 's3'])
        assert 's1' in batch
        assert 's3' in batch
    
    def test_page_exists(self, temp_db):
        """Test page existence check."""
        doc_id = temp_db.insert_document("test.pdf", 2)
        
        sentences = [
            {
                'id': 's1',
                'page_num': 1,
                'paragraph_id': 'p1',
                'sentence_id': 's1',
                'text': 'Page 1.',
                'char_offset_start': 0,
                'char_offset_end': 7,
                'item_type': 'paragraph'
            }
        ]
        
        temp_db.insert_sentences(doc_id, sentences)
        
        assert temp_db.page_exists(doc_id, 1) is True
        assert temp_db.page_exists(doc_id, 2) is False
    
    def test_document_deletion(self, temp_db):
        """Test document deletion with cascade."""
        doc_id = temp_db.insert_document("test.pdf", 1)
        
        sentences = [
            {
                'id': 's1',
                'page_num': 1,
                'paragraph_id': 'p1',
                'sentence_id': 's1',
                'text': 'Sentence.',
                'char_offset_start': 0,
                'char_offset_end': 9,
                'item_type': 'paragraph'
            }
        ]
        
        temp_db.insert_sentences(doc_id, sentences)
        
        # Verify exists
        assert temp_db.get_document(doc_id) is not None
        assert temp_db.get_sentence_by_id('s1') is not None
        
        # Delete
        temp_db.delete_document(doc_id)
        
        # Verify deleted
        assert temp_db.get_document(doc_id) is None
        assert temp_db.get_sentence_by_id('s1') is None
    
    def test_chat_history(self, temp_db):
        """Test chat history operations."""
        session_id = "test-session-123"
        
        # Insert messages
        msg1 = temp_db.insert_chat_message(
            session_id, 
            'user', 
            'Hello', 
            sources=[{'doc': 'test.pdf', 'page': 1}]
        )
        msg2 = temp_db.insert_chat_message(
            session_id, 
            'assistant', 
            'Hi there!'
        )
        
        # Get history
        history = temp_db.get_chat_history(session_id)
        assert len(history) == 2
        assert history[0]['role'] == 'user'
        assert history[0]['content'] == 'Hello'
        assert history[0]['sources'] is not None
        assert history[1]['role'] == 'assistant'
    
    def test_stats(self, temp_db):
        """Test statistics."""
        stats = temp_db.get_stats()
        assert 'documents' in stats
        assert 'sentences' in stats
        assert 'chat_messages' in stats
        
        # Add data
        doc_id = temp_db.insert_document("test.pdf", 1)
        temp_db.insert_sentences(doc_id, [
            {
                'id': 's1',
                'page_num': 1,
                'paragraph_id': 'p1',
                'sentence_id': 's1',
                'text': 'Test.',
                'char_offset_start': 0,
                'char_offset_end': 5,
                'item_type': 'paragraph'
            }
        ])
        temp_db.insert_chat_message('session1', 'user', 'Hello')
        
        stats = temp_db.get_stats()
        assert stats['documents'] == 1
        assert stats['sentences'] == 1
        assert stats['chat_messages'] == 1
    
    def test_get_all_documents(self, temp_db):
        """Test getting all documents."""
        # Insert multiple
        doc1 = temp_db.insert_document("file1.pdf", 5)
        doc2 = temp_db.insert_document("file2.pdf", 10)
        
        docs = temp_db.get_all_documents()
        assert len(docs) == 2
        
        filenames = [d['filename'] for d in docs]
        assert "file1.pdf" in filenames
        assert "file2.pdf" in filenames


class TestFactory:
    """Test factory function."""
    
    def test_create_sqlite_store(self):
        """Test factory function."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "factory.db"
        
        store = create_sqlite_store(str(db_path))
        assert store is not None
        assert Path(store.db_path) == db_path
        
        store.close()
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
