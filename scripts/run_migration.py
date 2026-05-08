import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from app.db.base import Base
from app.db.models import *  # Ensure models are registered
from app.db.session import sync_engine
from sqlalchemy import text
from app.config import settings
from scripts.seed_db import seed

def run_migration():
    """
    Drops all existing tables and recreates them fresh.
    Use with caution!
    """
    print(f"Initializing fresh database...")
    print(f"DB_TYPE: {settings.DB_TYPE}")
    print(f"DB_SCHEMA: {settings.DB_SCHEMA}")
    
    # In some environments, we might want to ensure the schema exists first
    # especially if it's not 'public'
    if settings.DB_SCHEMA != "public":
        with sync_engine.connect() as conn:
            print(f"Ensuring schema '{settings.DB_SCHEMA}' exists...")
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {settings.DB_SCHEMA}"))
            conn.commit()

    print("Dropping all existing tables...")
    try:
        Base.metadata.drop_all(bind=sync_engine)
        print("Tables dropped successfully.")
    except Exception as e:
        print(f"Error dropping tables (they might not exist): {e}")

    print("Creating all tables...")
    try:
        Base.metadata.create_all(bind=sync_engine)
        print("Tables created successfully.")
    except Exception as e:
        print(f"Error creating tables: {e}")
        sys.exit(1)

    print("Seeding initial data...")
    try:
        seed()
        print("Initial data seeded successfully.")
    except Exception as e:
        print(f"Error seeding database: {e}")

    print("\nDatabase is now fresh and ready.")

if __name__ == "__main__":
    run_migration()
