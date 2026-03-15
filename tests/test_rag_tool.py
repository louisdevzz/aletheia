"""
Test RAG Tool standalone

Usage:
    python test_rag_tool.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from aletheia.tools.rag_tool import RAGTool


async def test_rag_tool():
    """Test RAG tool with sample queries."""
    print("=" * 60)
    print("Testing RAG Tool")
    print("=" * 60)

    # Create RAG tool instance
    tool = RAGTool()

    # Test queries
    test_queries = [
        {"query": "test query", "top_k": 3},
        {"query": "What is GDP?", "top_k": 5},
    ]

    for i, args in enumerate(test_queries, 1):
        print(f"\nTest {i}: Query = '{args['query']}'")
        print("-" * 40)

        try:
            result = await tool.execute(args)

            print(f"Success: {result.success}")
            print(
                f"Output: {result.output[:200]}..."
                if len(result.output) > 200
                else f"Output: {result.output}"
            )
            if result.error:
                print(f"Error: {result.error}")

        except Exception as e:
            print(f"Exception: {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    print("Test completed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_rag_tool())
