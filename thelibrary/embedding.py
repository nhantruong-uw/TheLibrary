"""Generate dense embeddings for chunk text and search queries."""

from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-small-en-v1.5"
# BGE models are asymmetric: queries need this instruction prefix so the
# encoder treats them as search queries; stored passages don't get one.
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Load and cache the embedding model.

    Returns:
        The shared SentenceTransformer instance.
    """
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_passages(texts: list[str]) -> list[list[float]]:
    """Embed a batch of chunk texts for storage.

    Args:
        texts: Chunk texts to embed.

    Returns:
        One embedding vector per input text, in order.
    """
    return get_model().encode(texts, normalize_embeddings=True).tolist()


def embed_query(text: str) -> list[float]:
    """Embed a search query for similarity search against stored passages.

    Args:
        text: The user's search query.

    Returns:
        The query embedding vector.
    """
    return get_model().encode(QUERY_INSTRUCTION + text, normalize_embeddings=True).tolist()
