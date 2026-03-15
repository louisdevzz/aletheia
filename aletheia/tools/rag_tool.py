"""
RAG Tool

Tool wrapper for RAG system.
Gọi aletheia.rag.HybridRetrieval để search documents.
"""

import logging
from typing import Any, Dict
from .base import Tool, ToolResult

logger = logging.getLogger(__name__)


class RAGTool(Tool):
    """
    Tool for document retrieval using RAG.

    Wraps aletheia.rag.HybridRetrieval to provide document search
    as a tool for the Agent.
    """

    def __init__(self):
        self._retrieval = None

    def _get_retrieval(self):
        """Lazy initialization of HybridRetrieval."""
        if self._retrieval is None:
            from aletheia.rag.retrieval.retrieval import HybridRetrieval

            self._retrieval = HybridRetrieval()
        return self._retrieval

    @property
    def name(self) -> str:
        return "document_search"

    @property
    def description(self) -> str:
        return (
            "Search through uploaded documents to find relevant information. "
            "Use this when the user asks questions about their documents, PDFs, or files. "
            "Returns relevant text passages with source citations."
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query about the documents",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5)",
                    "default": 5,
                },
                "doc_id": {
                    "type": "string",
                    "description": "Optional: specific document ID to search within",
                    "default": None,
                },
            },
            "required": ["query"],
        }

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """
        Execute document search.

        Args:
            arguments: Must contain 'query', optionally 'top_k' and 'doc_id'

        Returns:
            ToolResult with search results
        """
        try:
            query = arguments.get("query")
            logger.info(f"🔍 RAG Tool executing with query: '{query}'")
            if not query:
                return ToolResult(success=False, output="", error="Query is required")

            top_k = arguments.get("top_k", 5)
            doc_id = arguments.get("doc_id")

            # Call RAG
            retrieval = self._get_retrieval()

            # Use hybrid search - filter_doc_id là tên tham số đúng
            results = retrieval.hybrid_search(
                query=query, top_k=top_k, filter_doc_id=doc_id
            )
            # Log all results with truncation
            result_summary = []
            for i, result in enumerate(results, 1):
                text = result.get("text", "")
                metadata = result.get("metadata", {})
                filename = metadata.get("filename", "Unknown")
                page = metadata.get("page_num", "N/A")
                text_preview = text[:100] + "..." if len(text) > 100 else text
                result_summary.append(
                    f"  [{i}] {filename} (Page {page}): {text_preview}"
                )

            logger.info(
                f"📚 RAG search found {len(results)} results:\n"
                + "\n".join(result_summary)
            )

            # Format results
            if not results:
                return ToolResult(
                    success=True, output="No relevant documents found for this query."
                )

            # Build output with citations
            output_parts = []
            for i, result in enumerate(results, 1):
                text = result.get("text", "")
                metadata = result.get("metadata", {})
                filename = metadata.get("filename", "Unknown")
                page = metadata.get("page_num", "N/A")

                output_parts.append(f"[{i}] {filename} (Page {page}):\n{text}\n")

            return ToolResult(success=True, output="\n".join(output_parts))

        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Error searching documents: {str(e)}"
            )
