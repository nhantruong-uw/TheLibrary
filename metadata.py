from pathlib import Path
import re

def resolve_title(meta_title: str, rel_path: str) -> str | None:
    """
    make sure has title and title is good
    """
    t = (meta_title or "").strip()
    if t and not looks_like_junk(t):
        return t
    stem = Path(rel_path).stem
    if not looks_like_junk(stem):
        return stem.replace("-", " ").replace("_", " ")
    return None

def looks_like_junk(title: str) -> bool:
    """
    check if title is bad
    """
    t = (title or "").strip()
    if not t:
        return True
    stripped = t.replace(" ", "")
    # Drive export token: long run of mixed alnum with no real spacing
    if len(stripped) > 20 and " " not in t[:15]:
        return True
    return False

PLACEHOLDER_AUTHORS = {"firstname lastname", "author", "unknown", ""}

def resolve_authors(meta_author: str) -> list[str]:
    """
    make sure has author and author good
    """
    a = (meta_author or "").strip()
    if a.lower() in PLACEHOLDER_AUTHORS:
        return []
    # split on ; or , — handles "Alshammari; Bahsi" and "Dunnan, Nancy"
    parts = re.split(r"[;,]", a)
    return [p.strip() for p in parts if p.strip()]
