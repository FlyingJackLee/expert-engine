CREATE TABLE IF NOT EXISTS expert_runs (
    run_id TEXT PRIMARY KEY,
    expert_id TEXT NOT NULL,
    status TEXT NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_expert_runs_status ON expert_runs (status);
