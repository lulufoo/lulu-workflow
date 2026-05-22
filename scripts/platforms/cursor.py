"""Cursor platform adapter: pass-through (native Cursor format)."""


def normalize(payload: dict) -> dict:
    """Cursor payloads are already in the expected format; return as-is."""
    return payload
