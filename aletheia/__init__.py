"""
Aletheia - Agentic AI System

Refactored architecture:
- aletheia.rag: RAG system (retrieval, storage, pipeline, parsers, models)
- aletheia.agent: Agent system (function calling)
- aletheia.tools: Tool definitions and registry
- aletheia.providers: LLM providers (Kimi only)

Version: 0.1.0
"""

__version__ = "0.1.0"
__name__ = "aletheia"

# Export main components
from .rag import HybridRetrieval, IngestionPipeline
from .agent import Agent, AgentBuilder
from .tools import Tool, ToolRegistry, RAGTool, CalculatorTool

# Providers
from .providers import (
    Provider,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    KimiProvider,
)

__all__ = [
    # RAG
    "HybridRetrieval",
    "IngestionPipeline",
    # Agent
    "Agent",
    "AgentBuilder",
    # Tools
    "Tool",
    "ToolRegistry",
    "RAGTool",
    "CalculatorTool",
    # Providers
    "Provider",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "KimiProvider",
]
