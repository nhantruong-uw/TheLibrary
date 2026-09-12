"""Split extracted document text into overlapping, offset-tracked chunks."""

from langchain_text_splitters import RecursiveCharacterTextSplitter


def naive_chunks(text, size=1500):
    """Split text into fixed-size, non-overlapping slices.

    Args:
        text: Full text to split.
        size: Number of characters per chunk.

    Returns:
        A list of text slices.
    """
    return [text[i:i + size] for i in range(0, len(text), size)]


splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name="cl100k_base",
    chunk_size=400,
    chunk_overlap=50,
    allowed_special={"<|endoftext|>"},
)


def chunk_with_offsets(full_text, splitter=splitter):
    """Split text into chunks and record each chunk's character offsets.

    Args:
        full_text: Full document text to split.
        splitter: Text splitter used to produce the chunk pieces.

    Returns:
        A list of dicts with keys "text", "char_start", and "char_end".
    """
    pieces = splitter.split_text(full_text)
    results = []
    search_start = 0
    for piece in pieces:
        idx = full_text.find(piece, search_start)
        if idx == -1:
            # Splitter altered the text (stripped whitespace, normalized);
            # fall back to searching from 0 so we don't lose the chunk.
            idx = full_text.find(piece)
        start = idx
        end = idx + len(piece)
        results.append({"text": piece, "char_start": start, "char_end": end})
        # Advance past this chunk, but back up by the overlap so the next
        # chunk (which overlaps) can still be found.
        search_start = max(end - 250, start + 1)
    return results
