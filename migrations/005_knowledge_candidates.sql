CREATE TABLE IF NOT EXISTS expert_knowledge_candidates (
    candidate_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES expert_runs(run_id) ON DELETE CASCADE,
    expert_id TEXT NOT NULL,
    status TEXT NOT NULL,
    content JSONB NOT NULL,
    source_feedback_ids JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_expert_knowledge_candidates_run_id
    ON expert_knowledge_candidates (run_id, created_at DESC);
