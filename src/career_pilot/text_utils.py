def normalize_text(text: str) -> str:
    """Remove unnecessary whitespace while preserving the words."""
    return " ".join(text.strip().split())
