CREATE TABLE IF NOT EXISTS expert_run_reviews (
    review_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES expert_runs(run_id) ON DELETE CASCADE,
    decision TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    notes TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_expert_run_reviews_run_id ON expert_run_reviews (run_id, created_at DESC);
