"""Resolve usable document titles and authors from PDF metadata."""

import re
from pathlib import Path

PLACEHOLDER_AUTHORS = {"firstname lastname", "author", "unknown", ""}


def resolve_title(meta_title: str, rel_path: str) -> str | None:
    """Pick a usable title from PDF metadata, falling back to the filename.

    Args:
        meta_title: The "title" field from the PDF's metadata.
        rel_path: Path to the PDF, relative to the corpus root.

    Returns:
        A cleaned-up title, or None if no usable title could be found.
    """
    t = (meta_title or "").strip()
    if t and not looks_like_junk(t):
        return t
    stem = Path(rel_path).stem
    if not looks_like_junk(stem):
        return stem.replace("-", " ").replace("_", " ")
    return None


def looks_like_junk(title: str) -> bool:
    """Check whether a title looks like a generated ID rather than real text.

    Args:
        title: Candidate title string.

    Returns:
        True if the title looks like junk (empty or an unspaced token dump).
    """
    t = (title or "").strip()
    if not t:
        return True
    stripped = t.replace(" ", "")
    # Drive export token: long run of mixed alnum with no real spacing.
    if len(stripped) > 20 and " " not in t[:15]:
        return True
    return False


def resolve_authors(meta_author: str) -> list[str]:
    """Parse an author metadata string into a list of individual names.

    Args:
        meta_author: The "author" field from the PDF's metadata.

    Returns:
        A list of author names, or an empty list if none could be resolved.
    """
    a = (meta_author or "").strip()
    if a.lower() in PLACEHOLDER_AUTHORS:
        return []
    # Split on ; or , -- handles "Alshammari; Bahsi" and "Dunnan, Nancy".
    parts = re.split(r"[;,]", a)
    return [p.strip() for p in parts if p.strip()]
