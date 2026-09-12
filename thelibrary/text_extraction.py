"""Extract text and per-page offsets from PDFs, classifying scan quality."""

import bisect

import psycopg
import pymupdf

# Environment errors halt the whole run.
ENVIRONMENT_ERRORS = (psycopg.OperationalError, OSError)

OCR_SIGNATURES = ("scribe", "abbyy", "finereader", "tesseract", "ocr", "scan")


def classify_document(doc) -> str:
    """Classify a document as OCR-needed or extracted by average text density.

    Args:
        doc: An open PyMuPDF Document.

    Returns:
        "needs_ocr" if pages average too few characters, else "extracted".
    """
    total_chars = sum(len(page.get_text()) for page in doc)
    chars_per_page = total_chars / max(len(doc), 1)
    if chars_per_page < 10:  # Essentially no text layer.
        return "needs_ocr"
    return "extracted"


def detect_text_source(doc) -> str:
    """Infer whether a document's text layer came from OCR or is digital.

    Args:
        doc: An open PyMuPDF Document.

    Returns:
        "ocr" if the creator/producer metadata matches a known OCR tool,
        otherwise "digital".
    """
    meta = doc.metadata or {}
    fingerprint = f"{meta.get('creator', '')} {meta.get('producer', '')}".lower()
    if any(sig in fingerprint for sig in OCR_SIGNATURES):
        return "ocr"
    return "digital"


def extract_one(conn, doc_id: int, full_path: str):
    """Extract text from one PDF and update its row in the database.

    On success, sets status to "extracted" or "needs_ocr" depending on
    text density. On a document-level failure, marks the row "failed"
    with the error message. Environment errors (DB/OS) are re-raised.

    Args:
        conn: Open database connection.
        doc_id: Primary key of the document row to update.
        full_path: Full filesystem path to the PDF.

    Returns:
        None.
    """
    try:
        with pymupdf.open(full_path) as doc:
            text, page_offsets = extract_text_with_pages(doc)
            chars_per_page = len(text) / max(len(doc), 1)
            status = "needs_ocr" if chars_per_page < 50 else "extracted"
            source = detect_text_source(doc)
            page_count = len(doc)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE documents
                SET status = %s, text_source = %s, page_count = %s,
                    full_text = %s, page_offsets = %s
                WHERE id = %s
                """,
                (status, source, page_count, text.replace("\x00", ""), page_offsets, doc_id),
            )
        conn.commit()
    except ENVIRONMENT_ERRORS:
        raise
    except (pymupdf.FileDataError, pymupdf.EmptyFileError, ValueError) as e:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE documents SET status = 'failed', error_msg = %s WHERE id = %s",
                (str(e), doc_id),
            )
        conn.commit()


def extract_text_with_pages(doc):
    """Concatenate a document's page text and record each page's offset.

    Args:
        doc: An open PyMuPDF Document.

    Returns:
        A tuple of (full_text, page_offsets), where page_offsets[i] is the
        character offset in full_text at which page i begins.
    """
    parts = []
    page_offsets = []  # Character offset where each page begins in full_text.
    cursor = 0
    for page in doc:
        page_offsets.append(cursor)
        t = page.get_text()
        parts.append(t)
        cursor += len(t)
    full_text = "".join(parts)
    return full_text, page_offsets


def page_for_offset(char_start, page_offsets):
    """Find the 1-indexed page containing a given character offset.

    Args:
        char_start: Character offset into the document's full text.
        page_offsets: Per-page starting offsets, as returned by
            extract_text_with_pages.

    Returns:
        The 1-indexed page number containing char_start.
    """
    # Rightmost page whose start is <= char_start; +1 for 1-indexed display.
    return bisect.bisect_right(page_offsets, char_start)
