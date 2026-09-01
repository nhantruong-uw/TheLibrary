import logging
from pathlib import Path
import hashlib
import psycopg
from config import DATABASE_URL, CORPUS_DIR

log = logging.getLogger(__name__)

def find_pdfs(root: Path):
    """
    a generator to find all PDF's of a given root directory

    Parameters:
        root: URL to the root in Path datatype
    
    Returns:
        no returns; simply yield as requested from caller
    """
    for p in root.rglob("*"):
        try:
            if p.is_file() and p.suffix.lower() == ".pdf":
                yield p
        except OSError as e:
            log.warning("skipping %s: %s", p, e)

def hash_file(path: Path, chunk_size=65536) -> str:
    """
    Hash a file with SHA-256 given by path by chunks of chunk_size; process chunk by chunk

    Parameters:
        path: path to file in Path datatype
        chunk_size: size of chunk to process; default is 65536
    
    Returns:
        the hash
    """
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()

def file_stats(path: Path) -> dict:
    """
    Give the stats of the file indicated by the path.

    Parameters:
        path: Path
    
    Returns:
        return a dictionary with size and mtime, where size is size of file and mtime is last modified time
    """
    st = path.stat()
    return {"size": st.st_size, "mtime": st.st_mtime}

def ingest_files(root: Path):
    """
    Given a file, insert the file and relevant information into the database as indicated by DATABASE_URL;
    commits final query at the end to ensure changes

    Parameters:
        root: Path

    Returns:
        Nothing; sql errors if any
    """
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            for path in find_pdfs(root):
                file_hash = hash_file(path)
                st = path.stat()
                rel_path = str(path.relative_to(root))
                cur.execute(
                    """
                    INSERT INTO documents (drive_id, rel_path, file_hash, file_size, file_mtime)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (file_hash) DO NOTHING
                    """,
                    ("test_corpus", rel_path, file_hash, st.st_size, st.st_mtime),
                )
        conn.commit()

def status_counts(conn):
    """
    count the number of files per status type

    Parameters:
        conn: connection to db
    """
    with conn.cursor() as cur:
        cur.execute("SELECT status, count(*) FROM documents GROUP BY status ORDER BY status")
        return dict(cur.fetchall())