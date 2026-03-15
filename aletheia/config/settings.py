"""
Configuration module for document ingestion pipeline.
Loads environment variables and provides centralized configuration.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()


def get_workspace_dir() -> Path:
    """
    Get the workspace directory for runtime data.

    Returns ~/.aletheia/ for user data, SQLite DBs, configs.
    Creates the directory if it doesn't exist.
    """
    workspace = Path.home() / ".aletheia"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


@dataclass
class MilvusConfig:
    # For Zilliz Cloud, use URI and token
    uri: str = os.getenv("MILVUS_URI", "http://localhost:19530")
    token: str = os.getenv(
        "MILVUS_TOKEN", ""
    )  # Format: "user:password" for Zilliz Cloud

    # Legacy support for local Milvus (optional)
    host: str = os.getenv("MILVUS_HOST", "localhost")
    port: int = int(os.getenv("MILVUS_PORT", "19530"))

    @property
    def connection_params(self) -> dict:
        """Get connection parameters based on configuration."""
        if self.token:
            # Zilliz Cloud connection
            return {"uri": self.uri, "token": self.token}
        else:
            # Local Milvus connection
            return {"uri": f"http://{self.host}:{self.port}"}


@dataclass
class ElasticsearchConfig:
    # For Elastic Cloud, use URL and API key
    url: str = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    api_key: str = os.getenv("ELASTIC_API_KEY", "")  # Elastic Cloud API key

    # Legacy support for local Elasticsearch (optional)
    host: str = os.getenv("ELASTICSEARCH_HOST", "localhost")
    port: int = int(os.getenv("ELASTICSEARCH_PORT", "9200"))

    @property
    def connection_params(self) -> dict:
        """Get connection parameters based on configuration."""
        if self.api_key:
            # Elastic Cloud connection
            return {"hosts": [self.url], "api_key": self.api_key}
        else:
            # Local Elasticsearch connection
            return {"hosts": [f"http://{self.host}:{self.port}"]}


@dataclass
class EmbeddingConfig:
    provider: str = os.getenv(
        "EMBEDDING_PROVIDER", "ollama"
    )  # openai, huggingface, ollama
    model: str = os.getenv("EMBEDDING_MODEL", "mxbai-embed-large:335m")
    dimension: int = int(os.getenv("EMBEDDING_DIMENSION", "1024"))
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    # Ollama embedding server
    ollama_base_url: str = os.getenv(
        "OLLAMA_BASE_URL", "http://192.168.10.235:11434/v1"
    )


@dataclass
class HuggingFaceEmbeddingConfig:
    """HuggingFace Sentence Transformers config for local embeddings."""

    model: str = os.getenv(
        "HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    dimension: int = int(os.getenv("HF_EMBEDDING_DIMENSION", "384"))
    device: str = os.getenv("HF_EMBEDDING_DEVICE", "cpu")  # cpu, cuda, mps


@dataclass
class KimiConfig:
    """Kimi API configuration - supports both Kimi Coding API and legacy Moonshot."""

    api_key: str = os.getenv("KIMI_API_KEY", "")
    model: str = os.getenv("KIMI_MODEL", "kimi-coding")
    base_url: str = os.getenv("KIMI_BASE_URL", "https://api.kimi.com/coding/v1")
    user_agent: str = "KimiCLI/0.77"


@dataclass
class RetrievalConfig:
    """Configuration for cumulative retrieval system."""

    top_k: int = int(os.getenv("RETRIEVAL_TOP_K", "3"))
    batch_size: int = int(os.getenv("BATCH_SIZE", "5"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    timeout_seconds: int = int(os.getenv("TIMEOUT_SECONDS", "30"))


@dataclass
class StorageConfig:
    """Configuration for SQLite storage backend."""

    @property
    def db_path(self) -> str:
        """Get SQLite database path."""
        workspace = get_workspace_dir()
        return str(workspace / "database" / "aletheia.db")


# Global config instances
milvus_config = MilvusConfig()
elasticsearch_config = ElasticsearchConfig()
embedding_config = EmbeddingConfig()
kimi_config = KimiConfig()
retrieval_config = RetrievalConfig()
storage_config = StorageConfig()
