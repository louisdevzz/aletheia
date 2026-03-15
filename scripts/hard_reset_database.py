#!/usr/bin/env python3
"""
Hard Reset DB Script
====================
Drops ALL tables from the PostgreSQL database, including Alembic version history.
This is used to fix migration mismatch errors when local state doesn't match remote DB.

WARNING: DESTRUCTIVE!
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aletheia.config import postgres_config
import psycopg2


def hard_reset():
    print("\n" + "=" * 60)
    print("🔥 HARD RESET DATABASE 🔥")
    print("=" * 60)
    print(f"Target: {postgres_config.host}/{postgres_config.database}")
    
    try:
        conn = psycopg2.connect(
            host=postgres_config.host,
            port=postgres_config.port,
            database=postgres_config.database,
            user=postgres_config.user,
            password=postgres_config.password
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # 1. Drop alembic_version (The cause of the error)
        print("\n1. Dropping migration history...")
        cursor.execute("DROP TABLE IF EXISTS alembic_version;")
        print("  ✓ Dropped 'alembic_version'")
        
        # 2. Drop data tables
        print("\n2. Dropping data tables...")
        tables = ['sentences', 'documents']
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
            print(f"  ✓ Dropped '{table}'")
            
        cursor.close()
        conn.close()
        
        print("\n✅ Database reset complete!")
        print("You can now run: uv run scripts/migrate.py init")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = hard_reset()
    sys.exit(0 if success else 1)
