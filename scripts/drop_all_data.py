#!/usr/bin/env python3
"""
Drop All Data Script
====================
This script drops all data from all databases used in the Aletheia system:
- PostgreSQL: Drops all tables and recreates schema
- Milvus: Drops the sentence_embeddings collection
- Elasticsearch: Deletes the sentences index

WARNING: This is a destructive operation and cannot be undone!
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aletheia.storage.sqlite_store import SQLiteStore as SentenceStore
from aletheia.storage.vector_index import VectorIndex
from aletheia.storage.bm25_index import BM25Index
from aletheia.config import postgres_config
import psycopg2


def confirm_action():
    """Ask user for confirmation before proceeding."""
    print("\n" + "=" * 70)
    print("⚠️  WARNING: DESTRUCTIVE OPERATION ⚠️")
    print("=" * 70)
    print("\nThis script will DELETE ALL DATA from:")
    print("  1. PostgreSQL (all tables)")
    print("  2. Milvus (sentence_embeddings collection)")
    print("  3. Elasticsearch (sentences index)")
    print("\nThis action CANNOT be undone!")
    print("=" * 70)
    
    response = input("\nType 'DELETE ALL DATA' to confirm: ")
    return response == "DELETE ALL DATA"


def drop_postgresql_data():
    """Drop all tables from PostgreSQL and recreate schema."""
    print("\n[1/3] Dropping PostgreSQL data...")
    
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=postgres_config.host,
            port=postgres_config.port,
            database=postgres_config.database,
            user=postgres_config.user,
            password=postgres_config.password
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Drop tables in correct order (respecting foreign keys)
        print("  - Dropping 'sentences' table...")
        cursor.execute("DROP TABLE IF EXISTS sentences CASCADE;")
        
        print("  - Dropping 'chat_messages' table...")
        cursor.execute("DROP TABLE IF EXISTS chat_messages CASCADE;")

        cursor.close()
        conn.close()
        
        print("  ✓ PostgreSQL data dropped successfully!")
        
        # Recreate schema using migration script
        print("\n  ↻ Recreating schema via Alembic...")
        try:
            import migrate
            migrate.init_db()
            print("  ✓ Schema recreated successfully!")
            return True
        except Exception as e:
            print(f"  ✗ Failed to recreate schema: {e}")
            return False
        
    except Exception as e:
        print(f"  ✗ Error dropping PostgreSQL data: {e}")
        return False


def drop_milvus_data():
    """Drop Milvus collection."""
    print("\n[2/3] Dropping Milvus data...")
    
    try:
        vector_index = VectorIndex()
        
        # Check if collection exists
        if vector_index.client.has_collection(vector_index.collection_name):
            print(f"  - Dropping collection '{vector_index.collection_name}'...")
            vector_index.client.drop_collection(vector_index.collection_name)
            print("  ✓ Milvus collection dropped successfully!")
        else:
            print(f"  - Collection '{vector_index.collection_name}' does not exist. Skipping.")
        
        vector_index.close()
        return True
        
    except Exception as e:
        print(f"  ✗ Error dropping Milvus data: {e}")
        return False


def drop_elasticsearch_data():
    """Drop Elasticsearch index."""
    print("\n[3/3] Dropping Elasticsearch data...")
    
    try:
        bm25_index = BM25Index()
        
        # Check if index exists
        if bm25_index.es.indices.exists(index=bm25_index.index_name):
            print(f"  - Deleting index '{bm25_index.index_name}'...")
            bm25_index.es.indices.delete(index=bm25_index.index_name)
            print("  ✓ Elasticsearch index deleted successfully!")
        else:
            print(f"  - Index '{bm25_index.index_name}' does not exist. Skipping.")
        
        bm25_index.close()
        return True
        
    except Exception as e:
        print(f"  ✗ Error dropping Elasticsearch data: {e}")
        return False


def main():
    """Main execution function."""
    print("\n" + "=" * 70)
    print("Aletheia - Drop All Data Script")
    print("=" * 70)
    
    # Confirm action
    if not confirm_action():
        print("\n❌ Operation cancelled by user.")
        return 1
    
    print("\n🚀 Starting data deletion process...\n")
    
    # Track success
    results = []
    
    # Drop data from all databases
    results.append(drop_postgresql_data())
    results.append(drop_milvus_data())
    results.append(drop_elasticsearch_data())
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    if all(results):
        print("✅ All data dropped successfully!")
        print("\nYou can now:")
        print("  - Run ingestion pipeline to add new data")
        print("  - Or recreate collections/indexes as needed")
        return 0
    else:
        print("⚠️  Some operations failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
