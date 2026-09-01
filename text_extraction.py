import pymupdf

def classify_document(doc) -> str:
    """
    classify documents based on avg num of chars on a page; classify into needs_ocr or extracted

    Parameters:
        doc: PyMuPDF Document
    
    Returns:
        status := "needs_ocr" | "extracted"
    """
    total_chars = sum(len(page.get_text()) for page in doc)
    chars_per_page = total_chars / max(len(doc), 1)
    if chars_per_page < 10:       # essentially no text layer
        return "needs_ocr"
    return "extracted"

OCR_SIGNATURES = ("scribe", "abbyy", "finereader", "tesseract", "ocr", "scan")

def detect_text_source(doc) -> str:
    """
    read the doc's metadata to see whether or not the creator has ocr signatures

    Parameters:
        doc: PyMuPDF Document

    Returns:
        "ocr" | "digital"
    """
    meta = doc.metadata or {}
    fingerprint = f"{meta.get('creator','')} {meta.get('producer','')}".lower()
    if any(sig in fingerprint for sig in OCR_SIGNATURES):
        return "ocr"
    return "digital"

def extract_one(conn, doc_id: int, full_path: str):
    """
    try to extract from a pdf and update the documents as needed

    Parameters:
        conn
        doc_id
        full_path: full path to pdf
    Returns:
        None
    """
    try:
        doc = pymupdf.open(full_path)
        try:
            text = "".join(page.get_text() for page in doc)
            chars_per_page = len(text) / max(len(doc), 1)
            status = "needs_ocr" if chars_per_page < 50 else "extracted"
            source = detect_text_source(doc)
            page_count = len(doc)
        finally:
            doc.close()

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE documents
                SET status = %s, text_source = %s, page_count = %s, full_text = %s
                WHERE id = %s
                """,
                (status, source, page_count, text, doc_id),
            )
    except Exception as e:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE documents SET status = 'failed', error_msg = %s WHERE id = %s",
                (str(e), doc_id),
            )
    conn.commit()
