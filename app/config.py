from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Database Selector
    DB_TYPE: str = "local"  # local or neon

    # Local Database
    LOCAL_DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ledgerlense"
    LOCAL_DATABASE_URL_SYNC: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/ledgerlense"

    # Neon Database
    NEON_DATABASE_URL: str = ""
    NEON_DATABASE_URL_SYNC: str = ""

    DB_SCHEMA: str = "public"

    @property
    def DATABASE_URL(self) -> str:
        return self.NEON_DATABASE_URL if self.DB_TYPE == "neon" else self.LOCAL_DATABASE_URL

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return self.NEON_DATABASE_URL_SYNC if self.DB_TYPE == "neon" else self.LOCAL_DATABASE_URL_SYNC

    # Storage
    PDF_STORAGE_PATH: str = "./storage/pdfs"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Security
    SECRET_KEY: str = "change-me-in-production"

    # Google Drive Archival
    GOOGLE_DRIVE_CREDENTIALS_PATH: str = "./secrets/ledgerlense.json"
    GOOGLE_DRIVE_ROOT_FOLDER_ID: str = ""


    # Extraction defaults
    TOKEN_Y_TOLERANCE: float = 3.0  # pixels tolerance for grouping tokens into lines
    LINE_GAP_THRESHOLD: float = 5.0  # gap between lines considered a new row
    MIN_TOKEN_LENGTH: int = 1

    @property
    def pdf_storage_dir(self) -> Path:
        path = Path(self.PDF_STORAGE_PATH)
        path.mkdir(parents=True, exist_ok=True)
        return path

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
