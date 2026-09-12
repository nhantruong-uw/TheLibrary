"""Hybrid (lexical + vector) search over indexed document chunks."""

from pgvector.psycopg import register_vector

from .embedding import embed_query

RESULT_COLUMNS = ("chunk_id", "snippet", "page_num", "document_id", "title", "rel_path")

LEXICAL_SQL = """
    SELECT
        c.id AS chunk_id,
        ts_headline('english', c.chunk_text, plainto_tsquery('english', %(q)s),
                    'StartSel=<mark>, StopSel=</mark>, MaxWords=35, MinWords=15') AS snippet,
        c.page_num,
        d.id AS document_id,
        COALESCE(d.title, d.rel_path) AS title,
        d.rel_path
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE c.text_search @@ plainto_tsquery('english', %(q)s)
    ORDER BY ts_rank(c.text_search, plainto_tsquery('english', %(q)s)) DESC
    LIMIT %(limit)s;
"""

VECTOR_SQL = """
    SELECT
        c.id AS chunk_id,
        ts_headline('english', c.chunk_text, plainto_tsquery('english', %(q)s),
                    'StartSel=<mark>, StopSel=</mark>, MaxWords=35, MinWords=15') AS snippet,
        c.page_num,
        d.id AS document_id,
        COALESCE(d.title, d.rel_path) AS title,
        d.rel_path
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE c.embedding IS NOT NULL
    ORDER BY c.embedding <=> %(qvec)s::vector
    LIMIT %(limit)s;
"""


def reciprocal_rank_fusion(ranked_id_lists, k=60):
    """Merge multiple ranked ID lists into one fused ranking.

    Args:
        ranked_id_lists: One list of IDs per ranking signal, best-first.
        k: RRF smoothing constant; higher values flatten the influence of
            top ranks.

    Returns:
        A dict mapping each ID to its fused score (higher is better).
    """
    scores = {}
    for ranked_ids in ranked_id_lists:
        for rank, item_id in enumerate(ranked_ids, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return scores


def hybrid_search(conn, query: str, limit: int = 10, candidate_k: int = 30) -> list[dict]:
    """Search chunks by combining lexical and vector similarity rankings.

    Runs Postgres full-text search and pgvector cosine similarity as two
    independent candidate lists, then merges them with Reciprocal Rank
    Fusion so a chunk ranked well by either signal surfaces near the top.
    Chunks without an embedding yet (not-yet-embedded documents) are simply
    absent from the vector candidates and can still surface lexically.

    Args:
        conn: Open database connection.
        query: The user's search query.
        limit: Number of fused results to return.
        candidate_k: Number of candidates to pull from each signal before
            fusion.

    Returns:
        Up to `limit` result dicts (chunk_id, snippet, page_num,
        document_id, title, rel_path, rank), ordered by fused score.
    """
    register_vector(conn)
    query_vector = embed_query(query)

    with conn.cursor() as cur:
        cur.execute(LEXICAL_SQL, {"q": query, "limit": candidate_k})
        lexical_rows = cur.fetchall()
        cur.execute(VECTOR_SQL, {"q": query, "qvec": query_vector, "limit": candidate_k})
        vector_rows = cur.fetchall()

    chunks_by_id = {}
    lexical_order = []
    for row in lexical_rows:
        result = dict(zip(RESULT_COLUMNS, row))
        chunks_by_id.setdefault(result["chunk_id"], result)
        lexical_order.append(result["chunk_id"])

    vector_order = []
    for row in vector_rows:
        result = dict(zip(RESULT_COLUMNS, row))
        chunks_by_id.setdefault(result["chunk_id"], result)
        vector_order.append(result["chunk_id"])

    fused_scores = reciprocal_rank_fusion([lexical_order, vector_order])
    ranked_ids = sorted(fused_scores, key=fused_scores.get, reverse=True)[:limit]

    return [{**chunks_by_id[cid], "rank": fused_scores[cid]} for cid in ranked_ids]
