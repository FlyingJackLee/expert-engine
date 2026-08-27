CREATE TABLE IF NOT EXISTS expert_run_feedback (
    feedback_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES expert_runs(run_id) ON DELETE CASCADE,
    outcome TEXT NOT NULL,
    notes TEXT NOT NULL,
    submitted_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_expert_run_feedback_run_id ON expert_run_feedback (run_id, created_at DESC);
