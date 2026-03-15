from typing import List, Dict
from aletheia.retrieval.retrieval import HybridRetrieval

def print_results(results: List[Dict]):
    """Helper function to print results (CLI only)."""
    print(f"\n{'='*80}")
    print(f"SEARCH RESULTS ({len(results)} found)")
    print(f"{'='*80}\n")
    
    for i, result in enumerate(results, start=1):
        print(f"[{i}] Score: {result['score']:.4f}")
        print(f"    Text: {result['text']}")
        print(f"    Metadata:")
        print(f"      - Document ID: {result['metadata']['doc_id']}")
        print(f"      - Page: {result['metadata']['page_num']}")
        print(f"      - Paragraph: {result['metadata']['paragraph_id']}")
        print(f"      - Offsets: {result['metadata']['char_offset_start']}-{result['metadata']['char_offset_end']}")
        print()


try:
    retriever = HybridRetrieval()
    
    # Hybrid search
    results = retriever.hybrid_search(
        query="",
        top_k=5,
        alpha=0.5,
        filter_doc_id="",
        rerank_method="weighted"
    )
    
    print_results(results)
    
    retriever.close()
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()