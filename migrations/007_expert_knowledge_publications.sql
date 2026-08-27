CREATE TABLE IF NOT EXISTS expert_knowledge_publications (
    publication_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL UNIQUE REFERENCES expert_knowledge_candidates(candidate_id) ON DELETE RESTRICT,
    document_id TEXT NOT NULL UNIQUE REFERENCES knowledge_documents(document_id) ON DELETE RESTRICT,
    expert_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (expert_id, version)
);

CREATE INDEX IF NOT EXISTS idx_expert_knowledge_publications_expert_version
    ON expert_knowledge_publications (expert_id, version DESC);
