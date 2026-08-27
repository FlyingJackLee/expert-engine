CREATE TABLE IF NOT EXISTS expert_knowledge_candidate_reviews (
    review_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES expert_knowledge_candidates(candidate_id) ON DELETE CASCADE,
    decision TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    notes TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_expert_knowledge_candidate_reviews_candidate_id
    ON expert_knowledge_candidate_reviews (candidate_id, created_at DESC);
