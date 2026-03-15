"""
Research Phase - Proactive information gathering

Conducts research before main response to gather relevant information.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import asyncio


@dataclass
class ResearchFinding:
    """A finding from research."""

    source: str
    content: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchResult:
    """Result of research phase."""

    findings: List[ResearchFinding]
    duration_ms: float
    success: bool
    error: Optional[str] = None


class ResearchPhase:
    """
    Conducts proactive research before generating response.

    Gathers information using available tools before the main agent loop begins.
    """

    def __init__(self, max_research_iterations: int = 3):
        self.max_iterations = max_research_iterations

    async def conduct_research(
        self, query: str, tools: List[Any], provider: Any
    ) -> ResearchResult:
        """
        Conduct research to gather information.

        Args:
            query: User query to research
            tools: Available research tools (e.g., RAG, web search)
            provider: LLM provider for planning

        Returns:
            ResearchResult with findings
        """
        import time

        start_time = time.time()

        try:
            findings = []

            # Use RAG tool if available for document research
            rag_tool = self._find_tool(tools, "document_search")
            if rag_tool:
                result = await rag_tool.execute({"query": query, "top_k": 5})
                if result.success:
                    findings.append(
                        ResearchFinding(
                            source="document_search",
                            content=result.output,
                            confidence=0.9,
                        )
                    )

            # Could add web search, calculator, etc.

            duration_ms = (time.time() - start_time) * 1000

            return ResearchResult(
                findings=findings, duration_ms=duration_ms, success=True
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return ResearchResult(
                findings=[], duration_ms=duration_ms, success=False, error=str(e)
            )

    def _find_tool(self, tools: List[Any], name: str) -> Optional[Any]:
        """Find a tool by name."""
        for tool in tools:
            if hasattr(tool, "name") and tool.name == name:
                return tool
        return None

    def format_findings(self, findings: List[ResearchFinding]) -> str:
        """Format findings for inclusion in system prompt."""
        if not findings:
            return ""

        parts = ["\n\n## Research Findings\n"]

        for i, finding in enumerate(findings, 1):
            parts.append(f"\n### Source {i}: {finding.source}\n")
            parts.append(finding.content[:500])  # Limit length
            if len(finding.content) > 500:
                parts.append("...")

        return "\n".join(parts)
