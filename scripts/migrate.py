"""
Database migration utilities.
Provides commands similar to Drizzle ORM: generate, push, migrate.
"""
import subprocess
import sys
from pathlib import Path


def generate(message: str = "auto migration"):
    """
    Generate a new migration based on model changes.
    Similar to: drizzle-kit generate
    
    Args:
        message: Migration message
    """
    print(f"🔄 Generating migration: {message}")
    result = subprocess.run(
        ["alembic", "revision", "--autogenerate", "-m", message],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✓ Migration generated successfully!")
        print(result.stdout)
    else:
        print("✗ Failed to generate migration")
        print(result.stderr)
        sys.exit(1)


def push():
    """
    Apply all pending migrations to database.
    Similar to: drizzle-kit push
    """
    print("🚀 Pushing migrations to database...")
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✓ Migrations applied successfully!")
        print(result.stdout)
    else:
        print("✗ Failed to apply migrations")
        print(result.stderr)
        sys.exit(1)


def rollback(steps: int = 1):
    """
    Rollback migrations.
    
    Args:
        steps: Number of migrations to rollback
    """
    print(f"⏪ Rolling back {steps} migration(s)...")
    revision = f"-{steps}"
    result = subprocess.run(
        ["alembic", "downgrade", revision],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✓ Rollback successful!")
        print(result.stdout)
    else:
        print("✗ Failed to rollback")
        print(result.stderr)
        sys.exit(1)


def status():
    """Show current migration status."""
    print("📊 Migration status:")
    result = subprocess.run(
        ["alembic", "current"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    
    print("\n📜 Migration history:")
    result = subprocess.run(
        ["alembic", "history"],
        capture_output=True,
        text=True
    )
    print(result.stdout)


def init_db():
    """
    Initialize database with initial migration.
    Creates tables if they don't exist.
    """
    print("🔧 Initializing database...")
    
    # Check if migrations exist
    versions_dir = Path("alembic/versions")
    if not versions_dir.exists() or not list(versions_dir.glob("*.py")):
        print("📝 No migrations found. Generating initial migration...")
        generate("initial schema")
    
    # Apply migrations
    push()
    print("✓ Database initialized!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Database migration utilities")
    parser.add_argument("command", choices=["generate", "push", "rollback", "status", "init"],
                       help="Migration command")
    parser.add_argument("-m", "--message", default="auto migration",
                       help="Migration message (for generate)")
    parser.add_argument("-s", "--steps", type=int, default=1,
                       help="Number of steps to rollback")
    
    args = parser.parse_args()
    
    if args.command == "generate":
        generate(args.message)
    elif args.command == "push":
        push()
    elif args.command == "rollback":
        rollback(args.steps)
    elif args.command == "status":
        status()
    elif args.command == "init":
        init_db()
