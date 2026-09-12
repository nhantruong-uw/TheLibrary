"""End-to-end ingestion pipeline: discovery, extraction, metadata, chunking."""

import time
from pathlib import Path

import pymupdf

from .chunking import chunk_with_offsets
from .file_discovery_inventory import find_pdfs, hash_file
from .metadata import resolve_authors, resolve_title
from .text_extraction import extract_one, page_for_offset


def run_metadata_backfill(conn, root):
    """Fill in missing titles and authors for already-extracted documents.

    Args:
        conn: Open database connection.
        root: Corpus root directory, as a Path.

    Returns:
        None.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, rel_path FROM documents "
            "WHERE status IN ('extracted','needs_ocr') AND title IS NULL"
        )
        rows = cur.fetchall()

    print(f"{len(rows)} documents to backfill")
    for doc_id, rel_path in rows:
        full_path = root / rel_path
        try:
            doc = pymupdf.open(full_path)
            meta = doc.metadata or {}
            doc.close()
        except Exception as e:
            print(f"skip {rel_path}: {e}")
            continue

        title = resolve_title(meta.get("title", ""), rel_path)
        if title:
            title = title.replace("\x00", "")
        authors = resolve_authors(meta.get("author", ""))
        for i in range(len(authors)):
            authors[i] = authors[i].replace("\x00", "")

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE documents SET title = %s, authors = %s WHERE id = %s",
                (title, authors, doc_id),
            )
    conn.commit()


def run_extraction(conn, root, status="pending"):
    """Extract text for every document with the given status.

    Prints the elapsed extraction time for each document.

    Args:
        conn: Open database connection.
        root: Corpus root directory, as a Path.
        status: Document status to select for extraction.

    Returns:
        None.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT id, rel_path FROM documents WHERE status = %s;", (status,))
        docs = cur.fetchall()

    print(f"{len(docs)} documents to extract")
    for doc_id, rel_path in docs:
        full_path = root / rel_path
        start = time.perf_counter()
        extract_one(conn, doc_id, str(full_path))
        elapsed = time.perf_counter() - start
        print(f"{elapsed:6.2f}s  {rel_path}")


def ingest_files(conn, root, folder, drive_id):
    """Insert every PDF found under root/folder into the documents table.

    This action is idempotent: PDFs already inserted (by file hash) are
    skipped.

    Args:
        conn: Open database connection.
        root: Corpus root directory, as a Path.
        folder: Subdirectory of root to scan for PDFs.
        drive_id: Identifier of the drive holding the corpus.

    Returns:
        None.
    """
    with conn.cursor() as cur:
        count = 0
        for path in find_pdfs(root / folder):
            if str(path).find("._") > -1:
                continue
            file_hash = hash_file(path)
            st = path.stat()

            rel_path = str(path.relative_to(root))

            cur.execute(
                """
                INSERT INTO documents (drive_id, rel_path, file_hash, file_size, file_mtime)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (file_hash) DO NOTHING
                """,
                (drive_id, rel_path, file_hash, st.st_size, st.st_mtime),
            )
            count += 1
        print(f"Processed {count} files. NOTE: This action is idempotent -- "
              f"PDF's already inserted will not be processed")
    conn.commit()


def run_chunking(conn):
    """Chunk the full text of every "extracted" document and store the chunks.

    Args:
        conn: Open database connection.

    Returns:
        None.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, full_text, page_offsets FROM documents WHERE status = 'extracted'"
        )
        docs = cur.fetchall()

    print(f"{len(docs)} documents to chunk")
    count = 0
    for doc_id, full_text, page_offsets in docs:
        print("Chunking document", doc_id)
        chunks = chunk_with_offsets(full_text)

        with conn.cursor() as cur:
            for idx, ch in enumerate(chunks):
                page_num = page_for_offset(ch["char_start"], page_offsets)
                cur.execute(
                    """
                    INSERT INTO chunks
                        (document_id, chunk_text, page_num, char_start, char_end, chunk_index)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (doc_id, ch["text"], page_num, ch["char_start"], ch["char_end"], idx),
                )
            cur.execute(
                "UPDATE documents SET status = 'chunked' WHERE id = %s",
                (doc_id,),
            )
        conn.commit()
        count += 1
    print(f"Finished chunking {count}/{len(docs)} documents")


def discover_incremental(conn, root: Path, drive_id: str):
    """Ingest only new or changed PDFs found under root.

    Files whose size and mtime match what's already recorded are skipped
    without re-hashing.

    Args:
        conn: Open database connection.
        root: Corpus root directory, as a Path.
        drive_id: Identifier of the drive holding the corpus.

    Returns:
        None.
    """
    # Load what we already know: path -> (size, mtime).
    with conn.cursor() as cur:
        cur.execute(
            "SELECT rel_path, file_size, file_mtime FROM documents WHERE drive_id = %s",
            [drive_id],
        )
        known = {rel: (size, mtime) for rel, size, mtime in cur.fetchall()}

    new_or_changed = 0
    for path in find_pdfs(root):
        rel_path = str(path.relative_to(root))
        st = path.stat()

        prior = known.get(rel_path)
        if prior is not None and prior[0] == st.st_size and abs(prior[1] - st.st_mtime) < 2:
            continue  # Unchanged -- skip without hashing.

        # New or changed: hash and upsert.
        file_hash = hash_file(path)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (drive_id, rel_path, file_hash, file_size, file_mtime)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (file_hash) DO UPDATE
                    SET rel_path = EXCLUDED.rel_path,
                        file_size = EXCLUDED.file_size,
                        file_mtime = EXCLUDED.file_mtime
                """,
                (drive_id, rel_path, file_hash, st.st_size, st.st_mtime),
            )
        new_or_changed += 1
    conn.commit()
    print(f"{new_or_changed} new or changed files")
