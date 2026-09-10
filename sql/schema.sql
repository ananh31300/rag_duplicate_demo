CREATE TABLE legal_instrument (
    instrument_id TEXT PRIMARY KEY,
    normalized_number TEXT NOT NULL UNIQUE,
    issued_date DATE NOT NULL,
    amends_id TEXT NULL,
    active_version_id TEXT NULL
);
CREATE TABLE document_version (
    version_id TEXT PRIMARY KEY,
    instrument_id TEXT NOT NULL REFERENCES legal_instrument(instrument_id),
    content_hash TEXT NOT NULL,
    effective_from DATE NOT NULL,
    source_url TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PREPARED','VALIDATED','ACTIVE','RETIRED','FAILED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (instrument_id, content_hash)
);
CREATE TABLE legal_chunk (
    version_id TEXT NOT NULL REFERENCES document_version(version_id),
    semantic_chunk_id TEXT NOT NULL,
    chunk_hash TEXT NOT NULL,
    text TEXT NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE NULL,
    PRIMARY KEY (version_id, semantic_chunk_id)
);
CREATE TABLE outbox_event (
    event_id TEXT PRIMARY KEY,
    aggregate_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ NULL
);
CREATE TABLE indexing_job (
    operation_key TEXT PRIMARY KEY,
    version_id TEXT NOT NULL REFERENCES document_version(version_id),
    status TEXT NOT NULL,
    indexed_chunks INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE processed_event (
    event_id TEXT PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

