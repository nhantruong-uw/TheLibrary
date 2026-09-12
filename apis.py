"""FastAPI search endpoint over the indexed document chunks."""

import psycopg
from fastapi import FastAPI
from pydantic import BaseModel

from thelibrary.config import DATABASE_URL

app = FastAPI()


class SearchResult(BaseModel):
    """A single full-text search hit."""

    snippet: str
    page_num: int | None
    document_id: int
    title: str
    rel_path: str
    rank: float


SEARCH_SQL = """
    SELECT
        ts_headline('english', c.chunk_text, plainto_tsquery('english', %(q)s),
                    'StartSel=<mark>, StopSel=</mark>, MaxWords=35, MinWords=15') AS snippet,
        c.page_num,
        d.id AS document_id,
        COALESCE(d.title, d.rel_path) AS title,
        d.rel_path,
        ts_rank(c.text_search, plainto_tsquery('english', %(q)s)) AS rank
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE c.text_search @@ plainto_tsquery('english', %(q)s)
    ORDER BY rank DESC
    LIMIT 10;
"""


@app.get("/search")
def search(q: str) -> list[SearchResult]:
    """Full-text search over indexed chunks, ranked by relevance.

    Args:
        q: The search query string.

    Returns:
        Up to 10 matching chunks, each with a highlighted snippet.
    """
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(SEARCH_SQL, {"q": q})
            rows = cur.fetchall()
    return [
        SearchResult(
            snippet=r[0], page_num=r[1], document_id=r[2],
            title=r[3], rel_path=r[4], rank=r[5],
        )
        for r in rows
    ]
