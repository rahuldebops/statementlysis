
import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent))

from app.db.base import Base
from app.db.session import sync_engine
from sqlalchemy import text
from app.config import settings

def create_tables():
    print(f"Creating tables in schema: {settings.DB_SCHEMA}")
    with sync_engine.connect() as conn:
        # Create schema if it doesn't exist
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {settings.DB_SCHEMA}"))
        conn.commit()
        
    # Create all tables
    Base.metadata.create_all(bind=sync_engine)
    print("Tables created successfully.")

if __name__ == "__main__":
    create_tables()
