# TheLibrary

A searchable database over a hard drive of PDFs — hybrid keyword + semantic
search, with results that link back to a highlighted page in the original
document. Reranking is planned next.

## Architecture

Derived data (extracted text, chunks, metadata) lives in Postgres and is always
available. The original PDF blobs live on an external drive (or S3, later).
Search only touches derived data, so it keeps working when the drive is
unplugged — only opening the actual file to render a highlighted page breaks on
disconnect, and that's where the UI shows a "drive not connected" message
instead of failing.

```
main.py ──ingest/extract/chunk/embed──▶ Postgres ◀──hybrid search── apis.py (FastAPI)
                                                                          ▲
                                                                          │ HTTP
                                                                     app.py (Streamlit)
```

## Project layout

```
thelibrary/                    Core library package
    config.py                  Environment-backed settings (DATABASE_URL, CORPUS_DIR)
    mounting.py                Locate the removable drive holding the corpus by UUID
    file_discovery_inventory.py  Walk a directory for PDFs, hash files, track status
    text_extraction.py         Extract text + per-page offsets with PyMuPDF
    metadata.py                Resolve a usable title/author from PDF metadata
    chunking.py                Split document text into overlapping, offset-tracked chunks
    embedding.py                Embed chunk text and search queries with bge-small-en-v1.5
    search.py                  Hybrid lexical + vector search, fused with RRF
    pipeline.py                Ingestion pipeline: discover -> extract -> backfill -> chunk -> embed

main.py                        Interactive CLI entry point that drives the pipeline
apis.py                        FastAPI app exposing GET /search
app.py                         Streamlit UI: search box + highlighted page preview
schema.sql                     Postgres schema (documents, chunks)
docker-compose.yml             Postgres 16 + pgvector, for local development
test_corpus/                   Small sample PDF set used for local iteration
TASKS.md                       Working log and roadmap (not tracked for style here)
```

## Stack

| Layer | Choice | Status |
|---|---|---|
| Database | Postgres 16 + pgvector | In use for metadata and full-text search |
| Infra | Docker Compose | In use, runs Postgres locally |
| Extraction | PyMuPDF (`fitz`) | In use |
| Metadata | Embedded PDF metadata + filename fallback | In use (GROBID evaluated, skipped — corpus metadata is clean enough) |
| Chunking | LangChain `RecursiveCharacterTextSplitter` (tiktoken-based) | In use |
| Search | Postgres full-text search (`tsvector`/`tsquery`, GIN index) | In use |
| Embeddings | `bge-small-en-v1.5` (384-dim), via `sentence-transformers` | In use |
| Vector search | pgvector, `vector_cosine_ops` HNSW index | In use |
| Fusion | Reciprocal Rank Fusion over lexical + vector rankings | In use |
| API | FastAPI | In use (`GET /search`) |
| Frontend | Streamlit | In use |
| OCR | Tesseract (`pytesseract`) | Planned — scanned PDFs are flagged `needs_ocr` but not yet OCR'd |
| Reranking | `bge-reranker-base` cross-encoder over the fused top-k | Planned |

See [TASKS.md](TASKS.md) for the detailed goal-by-goal working log.

## How it works

1. **Discovery** (`thelibrary/file_discovery_inventory.py`) walks a directory
   for PDFs and records each one's path, SHA-256 hash, size, and modified time
   in the `documents` table with status `pending`. Hashing (not the path)
   deduplicates files that live in more than one folder.
2. **Extraction** (`thelibrary/text_extraction.py`) opens each pending PDF with
   PyMuPDF, concatenates per-page text, and records the character offset where
   each page begins. Documents with too little extractable text are flagged
   `needs_ocr` instead of `extracted`; extraction failures are recorded as
   `failed` with the error message rather than aborting the run.
3. **Metadata backfill** (`thelibrary/metadata.py`) resolves a usable title and
   author list, falling back to the filename when the embedded PDF metadata is
   missing or looks like an auto-generated token.
4. **Chunking** (`thelibrary/chunking.py`) splits each document's full text into
   ~400-token chunks with 50-token overlap, mapping each chunk back to the page
   it starts on via the offsets recorded during extraction.
5. **Embedding** (`thelibrary/embedding.py`, `thelibrary/pipeline.py`) encodes
   each chunk's text with `bge-small-en-v1.5` and stores the 384-dim vector on
   the chunk row, then marks the document `embedded`.
6. **Search** (`thelibrary/search.py`) runs two independent retrieval signals
   per query — Postgres full-text search (`ts_rank`) and pgvector cosine
   similarity over chunk embeddings — and merges their ranked lists with
   Reciprocal Rank Fusion so a chunk that scores well on either signal
   surfaces near the top. Chunks not yet embedded simply fall back to
   lexical-only ranking. Snippets are generated with `ts_headline`.
7. **UI** (`app.py`) queries the search API (`apis.py`), groups results by
   document, and — when the source drive is mounted — renders the matched
   page as a PNG with the query terms highlighted.

## Setup

```bash
git clone <repo>
cd TheLibrary
uv venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env    # fill in POSTGRES_USER/PASSWORD/DB and DATABASE_URL
docker compose up -d
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 < schema.sql
```

### Environment variables (`.env`)

| Variable | Used by | Purpose |
|---|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | `docker-compose.yml` | Credentials for the Postgres container |
| `DATABASE_URL` | `thelibrary/config.py` | Full connection string used by the app |
| `CORPUS_DIR` | `thelibrary/config.py` | Root directory of the PDF corpus (defaults to `test_corpus`) |
| `DRIVE_ID` | `thelibrary/config.py` | Your desired drive UUID (KEEP THIS SAFE AND SECRET!) |

## Running it

```bash
# Ingest, extract, backfill metadata, chunk, and embed a folder of PDFs
python main.py

# Search API (http://127.0.0.1:8000/docs for the interactive docs)
uvicorn apis:app --host 127.0.0.1 --port 8000

# Search UI (talks to the API above)
streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

`main.py` is an interactive menu: option 1 ingests a new folder end to end
(discovery through embedding); option 2 re-scans a folder and ingests only
files that are new or whose size/modified time changed, without re-hashing
unchanged files.

The first embedding call downloads `bge-small-en-v1.5` (~130MB) from the
Hugging Face Hub and caches it locally; after that it loads from cache.

## License

MIT — see [LICENSE](LICENSE).
