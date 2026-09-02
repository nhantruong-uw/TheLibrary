import pymupdf
import psycopg
from config import DATABASE_URL, CORPUS_DIR
from text_extraction import extract_one, page_for_offset
from file_discovery_inventory import find_pdfs, hash_file
from metadata import resolve_title, resolve_authors
import time
from chunking import chunk_with_offsets

# func here
def run_metadata_backfill(conn, root):
    """
    Fill in titles and authors as needed
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, rel_path FROM documents WHERE status IN ('extracted','needs_ocr') AND title IS NULL"
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
            title = title.replace('\x00', '')
        authors = resolve_authors(meta.get("author", ""))
        for i in range(len(authors)):
            authors[i] = authors[i].replace('\x00', '')

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE documents SET title = %s, authors = %s WHERE id = %s",
                (title, authors, doc_id),
            )
    conn.commit()

def run_extraction(conn, root, status="pending"):
    """
    find all pdfs with relevant status and extract information about those pdfs into db documents
    prints out allotted time for measurements
    Parameters:
        status: status wanted from pdfs; default pending

    Returns:
        none
    """
    with conn.cursor() as cur:
        cur.execute("SELECT id, rel_path FROM documents WHERE status = %s;", (status,),)
        docs = cur.fetchall()

    print(f"{len(docs)} documents to extract")
    for doc_id, rel_path in docs:
        full_path = root / rel_path
        start = time.perf_counter()
        extract_one(conn, doc_id, str(full_path))
        elapsed = time.perf_counter() - start
        print(f"{elapsed:6.2f}s  {rel_path}")

def ingest_files(conn, root, drive_id):
    with conn.cursor() as cur:
        count = 0
        for path in find_pdfs(root):
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
        print("Processed " + str(count) + " files. NOTE: This action is idempotent -- PDF's already inserted will not be processed")
    conn.commit()

def run_chunking(conn):
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
    print("Finished chunking " + str(count) + "/" + str(len(docs)) + " documents")

from pathlib import Path

def discover_incremental(conn, root: Path, drive_id: str):
    # load what we already know: path -> (size, mtime)
    with conn.cursor() as cur:
        cur.execute("SELECT rel_path, file_size, file_mtime FROM documents WHERE drive_id = %s", [drive_id])
        known = {rel: (size, mtime) for rel, size, mtime in cur.fetchall()}

    new_or_changed = 0
    for path in find_pdfs(root):
        rel_path = str(path.relative_to(root))
        st = path.stat()

        prior = known.get(rel_path)
        if prior is not None and prior[0] == st.st_size and abs(prior[1] - st.st_mtime) < 2:
            continue   # unchanged — skip without hashing

        # new or changed: hash and upsert
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

from mounting import resolve_corpus_root, DRIVE_ID, find_mountpoint

if __name__ == "__main__":
    main_root = resolve_corpus_root(DRIVE_ID) / "Files"
    print("Welcome to TheLibrary. What would you like to do?")
    print("-------------------------------------------------")
    print("Current root: " + str(main_root))
    print("(1) Load an entire new folder")
    print("(2) Check for changed/new files")
    choice = input("Input: ")

    if choice == "1":
        print("What is your desired directory?")
        folder = input("Desired Directory: ")
        with psycopg.connect(DATABASE_URL) as conn:
                root = main_root / folder
                print("Begin ingesting files...")
                print("-" * 20)
                ingest_files(conn, root, DRIVE_ID)
                print("-" * 20)
                print("...End ingesting files")
                print()
                print("Begin extraction...")
                print("-" * 20)
                run_extraction(conn, root=root)
                print("-" * 20)
                print("...End extraction")
                print()
                print("Begin backfill...")
                print("-" * 20)
                run_metadata_backfill(conn, root=root)
                print("-" * 20)
                print("...End backfill")
                print()
                print("Begin chunking...")
                print("-" * 20)
                run_chunking(conn)
                print("-" * 20)
                print("...End chunking")
    elif choice == "2":
        print("What is your desired directory?")
        folder = input("Desired Directory: ")
        with psycopg.connect(DATABASE_URL) as conn:
            root = main_root / folder
            discover_incremental(conn, root, DRIVE_ID)
    else:
        print("Choice not understood. Exiting...")
