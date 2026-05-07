"""Parser Registry.

Central registry for bank-specific parsers.
Supports dynamic registration and lookup by bank_id.
"""

from __future__ import annotations

import logging
from typing import Optional, Type

from app.parsers.base import BaseParser, ParserConfig

logger = logging.getLogger(__name__)


class ParserRegistry:
    """Registry of bank-specific parsers."""

    _parsers: dict[str, tuple[Type[BaseParser], ParserConfig]] = {}
    _generic_parser: Optional[tuple[Type[BaseParser], ParserConfig]] = None

    @classmethod
    def register(
        cls,
        bank_id: str,
        parser_class: Type[BaseParser],
        config: ParserConfig,
    ) -> None:
        """Register a parser for a specific bank."""
        cls._parsers[bank_id] = (parser_class, config)
        logger.info(f"Registered parser: {bank_id} → {parser_class.__name__} v{config.version}")

    @classmethod
    def register_generic(
        cls,
        parser_class: Type[BaseParser],
        config: ParserConfig,
    ) -> None:
        """Register the generic fallback parser."""
        cls._generic_parser = (parser_class, config)
        logger.info(f"Registered generic parser: {parser_class.__name__} v{config.version}")

    @classmethod
    def get_parser(cls, bank_id: Optional[str]) -> Optional[BaseParser]:
        """Get a parser instance for a given bank_id."""
        if bank_id and bank_id in cls._parsers:
            parser_class, config = cls._parsers[bank_id]
            return parser_class(config)
        return None

    @classmethod
    def get_generic_parser(cls) -> Optional[BaseParser]:
        """Get the generic fallback parser."""
        if cls._generic_parser:
            parser_class, config = cls._generic_parser
            return parser_class(config)
        return None

    @classmethod
    def get_or_fallback(cls, bank_id: Optional[str]) -> BaseParser:
        """Get bank-specific parser or fallback to generic."""
        parser = cls.get_parser(bank_id)
        if parser:
            return parser

        generic = cls.get_generic_parser()
        if generic:
            logger.warning(f"No parser for bank '{bank_id}', using generic parser")
            return generic

        raise ValueError(
            f"No parser available for bank '{bank_id}' and no generic parser registered"
        )

    @classmethod
    def list_registered(cls) -> dict[str, str]:
        """List all registered parsers: {bank_id: parser_class_name}."""
        result = {}
        for bank_id, (parser_class, config) in cls._parsers.items():
            result[bank_id] = f"{parser_class.__name__} v{config.version}"
        if cls._generic_parser:
            pc, cfg = cls._generic_parser
            result["generic"] = f"{pc.__name__} v{cfg.version}"
        return result

    @classmethod
    def clear(cls) -> None:
        """Clear all registrations (used in testing)."""
        cls._parsers.clear()
        cls._generic_parser = None
