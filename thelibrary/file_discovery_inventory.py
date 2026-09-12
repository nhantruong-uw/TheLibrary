"""Discover PDFs on disk and track their ingestion status in the database."""

import hashlib
import logging
from pathlib import Path

from .config import CORPUS_DIR

log = logging.getLogger(__name__)


def find_pdfs(root: Path):
    """Yield every PDF found under a root directory.

    Args:
        root: Directory to search, as a Path.

    Yields:
        Path objects for each PDF file found.
    """
    for p in root.rglob("*"):
        try:
            if p.is_file() and p.suffix.lower() == ".pdf":
                yield p
        except OSError as e:
            log.warning("skipping %s: %s", p, e)


def hash_file(path: Path, chunk_size=65536) -> str:
    """Compute the SHA-256 hash of a file, reading it in chunks.

    Args:
        path: Path to the file to hash.
        chunk_size: Number of bytes to read per chunk.

    Returns:
        The hex-encoded SHA-256 digest.
    """
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def file_stats(path: Path) -> dict:
    """Get the size and modification time of a file.

    Args:
        path: Path to the file.

    Returns:
        A dict with "size" (bytes) and "mtime" (seconds since epoch).
    """
    st = path.stat()
    return {"size": st.st_size, "mtime": st.st_mtime}


def ingest_file(conn, file_path: Path):
    """Insert a single file into the documents table, if not already present.

    Args:
        conn: Open database connection.
        file_path: Path to the file to ingest.

    Returns:
        None.
    """
    with conn.cursor() as cur:
        file_hash = hash_file(file_path)
        st = file_path.stat()
        rel_path = str(file_path.relative_to(Path(CORPUS_DIR)))
        cur.execute(
            """
            INSERT INTO documents (drive_id, rel_path, file_hash, file_size, file_mtime)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (file_hash) DO NOTHING
            """,
            (CORPUS_DIR, rel_path, file_hash, st.st_size, st.st_mtime),
        )
    conn.commit()


def status_counts(conn):
    """Count documents grouped by ingestion status.

    Args:
        conn: Open database connection.

    Returns:
        A dict mapping status to the number of documents with that status.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT status, count(*) FROM documents GROUP BY status ORDER BY status")
        return dict(cur.fetchall())
