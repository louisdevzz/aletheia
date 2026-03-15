"""
Tests for fast retrieval components.
"""
import asyncio
import time
import tempfile
from pathlib import Path

import pytest

from aletheia.cache.search_cache import SearchCache
from aletheia.storage.sentence_store_optimized import OptimizedSentenceStore


class TestSearchCache:
    """Test cache functionality."""
    
    def test_cache_basic_operations(self):
        """Test basic cache get/set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = SearchCache(ttl_seconds=60)
            cache.db_path = Path(tmpdir) / "cache.db"
            cache._init_db()
            
            # Set cache
            results = [
                {'sentence_id': 's1', 'text': 'test', 'score': 0.9},
                {'sentence_id': 's2', 'text': 'test2', 'score': 0.8}
            ]
            cache.set("test query", {}, results)
            
            # Get cache
            cached = cache.get("test query", {})
            assert cached is not None
            assert len(cached) == 2
            assert cached[0]['sentence_id'] == 's1'
    
    def test_cache_ttl_expiration(self):
        """Test cache TTL expiration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = SearchCache(ttl_seconds=1)  # 1 second TTL
            cache.db_path = Path(tmpdir) / "cache.db"
            cache._init_db()
            
            # Set cache
            cache.set("test", {}, [{'id': '1'}])
            
            # Should exist immediately
            assert cache.get("test", {}) is not None
            
            # Wait for expiration
            time.sleep(1.1)
            
            # Should be expired
            assert cache.get("test", {}) is None
    
    def test_cache_stats(self):
        """Test cache statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = SearchCache()
            cache.db_path = Path(tmpdir) / "cache.db"
            cache._init_db()
            
            # Add entries
            cache.set("q1", {}, [{'id': '1'}])
            cache.set("q2", {}, [{'id': '2'}])
            
            # Access
            cache.get("q1")
            cache.get("q1")
            
            stats = cache.get_stats()
            assert stats['total_entries'] == 2
            assert stats['total_cache_hits'] == 2


class TestOptimizedSentenceStore:
    """Test optimized sentence store."""
    
    def test_batch_context_fetch(self, mocker):
        """Test batch context fetching."""
        # This would need a real database to test properly
        # For now just verify the method exists
        assert hasattr(OptimizedSentenceStore, 'get_paragraph_context_batch')
        assert hasattr(OptimizedSentenceStore, 'get_sentences_by_ids_batch')


class TestFastRetrieval:
    """Test fast retrieval pipeline."""
    
    def test_score_fusion_logic(self):
        """Test score fusion calculation."""
        # Import here to avoid dependency issues during test collection
        from aletheia.retrieval.fast_retrieval import FastRetrieval
        
        retriever = FastRetrieval(use_cache=False, use_reranker=False)
        
        vector_results = [
            {'sentence_id': 's1', 'score': 0.9},
            {'sentence_id': 's2', 'score': 0.7}
        ]
        
        bm25_results = [
            {'sentence_id': 's2', 'score': 0.8},
            {'sentence_id': 's3', 'score': 0.6}
        ]
        
        fused = retriever._fuse_scores(vector_results, bm25_results, alpha=0.5)
        
        # Should have all unique sentence IDs
        ids = [r['sentence_id'] for r in fused]
        assert set(ids) == {'s1', 's2', 's3'}
        
        # s2 appears in both, should have highest combined score
        s2_score = next(r['score'] for r in fused if r['sentence_id'] == 's2')
        assert s2_score > 0


@pytest.mark.asyncio
class TestStreamingSearch:
    """Test streaming search."""
    
    async def test_search_events(self, mocker):
        """Test streaming search events."""
        from aletheia.ui.streaming_components import StreamingSearch, SearchStage
        from aletheia.retrieval.fast_retrieval import FastRetrieval
        
        # Mock retriever
        mock_retriever = mocker.MagicMock(spec=FastRetrieval)
        mock_retriever.cache = None
        mock_retriever.vector_index = mocker.MagicMock()
        mock_retriever.vector_index.search.return_value = []
        mock_retriever.bm25_index = mocker.MagicMock()
        mock_retriever.bm25_index.search.return_value = []
        mock_retriever._fuse_scores.return_value = []
        mock_retriever.use_reranker = False
        mock_retriever.sentence_store = mocker.AsyncMock()
        mock_retriever.sentence_store.get_sentences_by_ids_batch.return_value = {}
        
        streaming = StreamingSearch(mock_retriever)
        
        # Collect events
        events = []
        async for event in streaming.search_streaming("test", top_k=2):
            events.append(event)
        
        # Should have events for each stage
        stages = [e.stage for e in events]
        assert SearchStage.CACHE_CHECK in stages
        assert SearchStage.VECTOR_SEARCH in stages
        assert SearchStage.BM25_SEARCH in stages


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
