"""LedgerLense — FastAPI Application Entry Point."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.api.router import api_router
from app.parsers.registry import ParserRegistry
from app.parsers.base import ParserConfig

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="LedgerLense",
    description="AI/ML-ready bank statement extraction platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── Register Parsers ────────────────────────────────────────────────────────

def _register_parsers() -> None:
    """Register all bank-specific and generic parsers."""
    parsers_dir = Path(__file__).parent / "parsers"

    # Generic parser
    from app.parsers.generic.parser import GenericParser
    generic_config = ParserConfig.from_file(parsers_dir / "generic" / "config.json")
    ParserRegistry.register_generic(GenericParser, generic_config)

    # HDFC
    from app.parsers.hdfc.parser import HDFCParser
    hdfc_config = ParserConfig.from_file(parsers_dir / "hdfc" / "config.json")
    ParserRegistry.register("hdfc", HDFCParser, hdfc_config)

    # SBI
    from app.parsers.sbi.parser import SBIParser
    sbi_config = ParserConfig.from_file(parsers_dir / "sbi" / "config.json")
    ParserRegistry.register("sbi", SBIParser, sbi_config)

    # ICICI
    from app.parsers.icici.parser import ICICIParser
    icici_config = ParserConfig.from_file(parsers_dir / "icici" / "config.json")
    ParserRegistry.register("icici", ICICIParser, icici_config)

    registered = ParserRegistry.list_registered()
    logger.info(f"Parsers registered: {registered}")


_register_parsers()

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for any unhandled exceptions to return JSON instead of HTML."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {str(exc)}"}
    )

# ─── Routes ──────────────────────────────────────────────────────────────────

app.include_router(api_router)

# ─── Static Files & UI ───────────────────────────────────────────────────────

ui_dir = Path(__file__).parent / "ui"
static_dir = ui_dir / "static"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", include_in_schema=False)
async def serve_ui():
    """Serve the main UI page."""
    index_path = ui_dir / "templates" / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "LedgerLense API", "docs": "/docs"}


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "parsers": ParserRegistry.list_registered(),
    }
