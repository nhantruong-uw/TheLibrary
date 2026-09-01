import logging
from pathlib import Path
import hashlib

log = logging.getLogger(__name__)

def find_pdfs(root: Path):
    for p in root.rglob("*"):
        try:
            if p.is_file() and p.suffix.lower() == ".pdf":
                yield p
        except OSError as e:
            log.warning("skipping %s: %s", p, e)

def hash_file(path: Path, chunk_size=65536) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()

def file_stats(path: Path) -> dict:
    st = path.stat()
    return {"size": st.st_size, "mtime": st.st_mtime}