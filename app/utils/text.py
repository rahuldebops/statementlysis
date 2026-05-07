"""Text processing utilities."""

def sanitize_for_db(text: str) -> str:
    """Remove null bytes and other characters that Postgres might reject in UTF-8."""
    if not text:
        return ""
    # Remove null bytes (CharacterNotInRepertoireError)
    return text.replace("\u0000", "")
