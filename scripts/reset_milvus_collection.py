"""
Reset Milvus collection to use new embedding dimension (1024).
Run this when switching from OpenAI (1536) to Ollama (1024) embeddings.
"""

import sys

sys.path.insert(0, "/home/louisdevzz/Documents/aletheia")

from aletheia.storage.vector_index import VectorIndex
from aletheia.config import embedding_config

print(f"Current embedding config:")
print(f"  Provider: {embedding_config.provider}")
print(f"  Model: {embedding_config.model}")
print(f"  Dimension: {embedding_config.dimension}")
print()

# Initialize vector index
vector_index = VectorIndex()

# Drop and recreate collection with new dimension
print("Dropping existing collection...")
vector_index.create_collection(drop_existing=True)

print(
    "\n✅ Collection recreated successfully with dimension:", embedding_config.dimension
)

vector_index.close()
