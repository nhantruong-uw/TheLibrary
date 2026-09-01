CREATE TYPE doc_status AS ENUM ('pending', 'extraced', 'chunked', 'embedded', 'failed', 'needs_ocr');

CREATE TABLE documents(
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    drive_id   TEXT NOT NULL,   -- volume UUID from blkid, stable across remounts
    rel_path   TEXT NOT NULL,   -- path relative to the mountpoint
    file_hash CHAR(64) NOT NULL UNIQUE, -- enforce length of hash and uniqueness
    title text,
    authors text[], 
    page_count INT,
    ingested_timestamp TIMESTAMPTZ NOT NULL DEFAULT now(), -- automated and real time-stamp
    status doc_status NOT NULL DEFAULT 'pending'
);

CREATE TABLE chunks(
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_text text,
    page_num INT,
    char_start INT,
    char_end INT,
    chunk_index INT NOT NULL
);