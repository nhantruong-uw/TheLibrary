# PDF Knowledge Base

A searchable database over a hard drive of PDFs. Keyword search first, semantic search second, with highlighting back to the original page.

## Architecture

Derived data (extracted text, chunks, embeddings, metadata) lives in Postgres and is always available. The original PDF blobs live on the drive (or S3 later). Search only touches derived data, so it keeps working when the drive is unplugged. Only opening the actual file breaks on disconnect, and that's where the error message goes.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Database | Postgres 16 + pgvector | Metadata, full-text search, and vectors in one place |
| Infra | Docker Compose | Reproducible on any machine; GROBID needs it anyway |
| Extraction | PyMuPDF (`fitz`) | Fast, gives word-level bounding boxes for highlighting |
| OCR | Tesseract (`pytesseract`) | For scanned PDFs with no text layer |
| Metadata | GROBID | Built for academic papers: title, authors, abstract, refs |
| Chunking | LangChain `RecursiveCharacterTextSplitter` | Breaks on paragraph/sentence boundaries |
| Embeddings | `bge-small-en-v1.5` (384-dim) | Runs on CPU for queries; batch on GPU |
| Reranking | `bge-reranker-base` | Cross-encoder over top-k results |
| API | FastAPI | Typed contract, auto docs |
| Frontend | Streamlit, then React | Streamlit gets a UI in a day |

## Setup
git clone <repo>
cd <repo>
uv venv --python 3.11
source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env
docker compose up -d