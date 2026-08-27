CREATE TABLE IF NOT EXISTS expert_knowledge_publication_revisions (
    revision_id TEXT PRIMARY KEY,
    publication_id TEXT NOT NULL REFERENCES expert_knowledge_publications(publication_id) ON DELETE RESTRICT,
    action TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    notes TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_expert_knowledge_publication_revisions_publication_id
    ON expert_knowledge_publication_revisions (publication_id, created_at DESC);
