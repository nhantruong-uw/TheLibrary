"""FastAPI search endpoint over the indexed document chunks."""

import psycopg
from fastapi import FastAPI
from pydantic import BaseModel

from thelibrary.config import DATABASE_URL
from thelibrary.search import hybrid_search

app = FastAPI()


class SearchResult(BaseModel):
    """A single hybrid (lexical + vector) search hit."""

    snippet: str
    page_num: int | None
    document_id: int
    title: str
    rel_path: str
    rank: float


@app.get("/search")
def search(q: str) -> list[SearchResult]:
    """Hybrid search over indexed chunks, ranked by Reciprocal Rank Fusion.

    Args:
        q: The search query string.

    Returns:
        Up to 10 matching chunks, each with a highlighted snippet.
    """
    with psycopg.connect(DATABASE_URL) as conn:
        results = hybrid_search(conn, q)
    return [SearchResult(**r) for r in results]
