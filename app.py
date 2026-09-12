"""Streamlit search UI over the indexed document chunks."""

import html
import os

import pymupdf
import requests
import streamlit as st

from thelibrary.mounting import DRIVE_MOUNT


def render_highlighted_page(pdf_path: str, page_num: int, query: str, dpi: int = 100) -> bytes:
    """Render one PDF page as a PNG with the query terms highlighted.

    Args:
        pdf_path: Full path to the PDF on disk.
        page_num: 1-indexed page number to render.
        query: Search query whose matches should be highlighted.
        dpi: Resolution to render the page at.

    Returns:
        PNG image bytes.
    """
    with pymupdf.open(pdf_path) as doc:
        page = doc[page_num - 1]  # page_num is 1-indexed.
        for rect in page.search_for(query):
            annot = page.add_highlight_annot(rect)
            annot.update()
        pix = page.get_pixmap(dpi=dpi)
        return pix.tobytes("png")


def try_render(pdf_path: str, page_num: int, query: str) -> bytes | None:
    """Render a highlighted page, returning None if the source is unavailable.

    Args:
        pdf_path: Full path to the PDF on disk.
        page_num: 1-indexed page number to render.
        query: Search query whose matches should be highlighted.

    Returns:
        PNG image bytes, or None if the drive isn't mounted, the file is
        missing, or rendering fails.
    """
    if not os.path.ismount(DRIVE_MOUNT):
        return None  # Drive not connected.
    if not os.path.exists(pdf_path):
        return None  # Mounted but file missing.
    try:
        return render_highlighted_page(pdf_path, page_num, query)
    except Exception:
        return None  # Corrupt page, render failure.


@st.cache_data
def cached_render(pdf_path: str, page_num: int, query: str) -> bytes | None:
    """Cache wrapper around try_render, keyed on its arguments."""
    return try_render(pdf_path, page_num, query)


st.set_page_config(page_title="The Library", layout="wide")
st.title("The Library")

query = st.text_input("Search", placeholder="Dai Viet, Sherlock Holmes, Red-teaming, ...")

if query:
    resp = requests.get("http://127.0.0.1:8000/search", params={"q": query})
    results = resp.json()

    st.caption(f"{len(results)} results")

    cleaned_results = {}

    for r in results:
        if r["title"] not in cleaned_results:
            cleaned_results[r["title"]] = {
                "rel_path": r["rel_path"],
                "pages": [],
                "snippets": []
            }
        cleaned_results[r["title"]]["pages"].append(r["page_num"])
        cleaned_results[r["title"]]["snippets"].append(r["snippet"])

    for r in cleaned_results:
        with st.container(border=True):
            st.markdown(f"**{r}**")
            st.caption(f"{cleaned_results[r]['rel_path']}")
            for p, s in zip(cleaned_results[r]["pages"], cleaned_results[r]["snippets"]):
                safe = html.escape(s)
                safe = safe.replace("#", "&#35;")  # Kill # so it can't start a header.
                # Now restore only the <mark> tags:
                safe = safe.replace("&lt;mark&gt;", "<mark>").replace("&lt;/mark&gt;", "</mark>")
                st.markdown(f"- *(pg {p}):* " + safe, unsafe_allow_html=True)

                with st.expander("Show Page"):
                    full_path = DRIVE_MOUNT + "/Files/" + cleaned_results[r]["rel_path"]
                    img = cached_render(full_path, int(p), query)
                    if img:
                        st.image(img)
                    else:
                        st.info(f"Drive not connected — see page {p} in {r}")
