import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from app.db.base import Base
from app.db.models import *  # Ensure models are registered
from app.db.session import sync_engine
from sqlalchemy import text, create_engine
from sqlalchemy.engine.url import make_url
from app.config import settings
from scripts.seed_db import seed

def ensure_database_exists():
    """
    Connects to the 'postgres' database to drop and recreate the target database.
    Only performed if DB_TYPE is 'local'.
    """
    if settings.DB_TYPE != "local":
        print(f"Skipping database-level recreation for non-local DB_TYPE: {settings.DB_TYPE}")
        return

    url = make_url(settings.DATABASE_URL_SYNC)
    db_name = url.database
    
    # Create a temporary engine connected to the default 'postgres' database
    postgres_url = url.set(database="postgres")
    temp_engine = create_engine(postgres_url, isolation_level="AUTOCOMMIT")
    
    print(f"Recreating database '{db_name}' on {url.host}...")
    with temp_engine.connect() as conn:
        try:
            # DROP DATABASE cannot run in a transaction, hence AUTOCOMMIT above.
            # WITH (FORCE) kills other active connections to the DB.
            conn.execute(text(f"DROP DATABASE IF EXISTS {db_name} WITH (FORCE)"))
            print(f"  Dropped existing database '{db_name}' (if it existed).")
        except Exception as e:
            print(f"  Warning: Could not drop database (it might not exist or lacks permissions): {e}")
            
        try:
            conn.execute(text(f"CREATE DATABASE {db_name}"))
            print(f"  Created fresh database '{db_name}'.")
        except Exception as e:
            print(f"  Error creating database: {e}")
            sys.exit(1)
    
    temp_engine.dispose()

def run_migration():
    """
    Drops all existing tables and recreates them fresh.
    Use with caution!
    """
    # Step 0: Ensure the physical database exists (Local only)
    ensure_database_exists()
    
    print(f"Initializing fresh database schema...")
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
