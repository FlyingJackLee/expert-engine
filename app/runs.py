"""Run-result storage with a test-friendly in-memory backend and PostgreSQL persistence."""
from __future__ import annotations

import json
from typing import Protocol
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from app.config import DATABASE_URL, RUN_BACKEND


class RunRepository(Protocol):
    """Storage contract for persisted analysis results and human reviews."""
    def save(self, run_id: str, expert_id: str, status: str, result: dict) -> None:
        """Persist one completed or pending analysis result."""
    def get(self, run_id: str) -> dict | None:
        """Return a saved analysis result by its stable run ID."""
    def record_review(self, run_id: str, decision: str, reviewer_id: str, notes: str) -> str | None:
        """Append an audited human decision and return the new run status."""
    def record_feedback(self, run_id: str, outcome: str, notes: str, submitted_by: str) -> str | None:
        """Append a structured real-world outcome note for a saved run."""


class InMemoryRunRepository:
    """Process-local repository used only for fast, isolated tests."""
    def __init__(self) -> None:
        """Initialize an empty process-local record collection."""
        self.records: dict[str, dict] = {}

    def save(self, run_id: str, expert_id: str, status: str, result: dict) -> None:
        """Store a result in process memory for one isolated test process."""
        existing = self.records.get(run_id, {})
        self.records[run_id] = {"expert_id": expert_id, "status": status, "result": result, "reviews": existing.get("reviews", [])}

    def get(self, run_id: str) -> dict | None:
        """Look up a test result without touching infrastructure."""
        record = self.records.get(run_id)
        return record["result"] if record else None

    def record_review(self, run_id: str, decision: str, reviewer_id: str, notes: str) -> str | None:
        """Record a test-only audit item and update the local status."""
        record = self.records.get(run_id)
        if not record:
            return None
        status = {"APPROVE": "COMPLETED", "REJECT": "REJECTED", "REQUEST_RESEARCH": "PENDING_REVIEW"}[decision]
        record["status"] = status
        record["reviews"].append({"review_id": str(uuid4()), "decision": decision, "reviewer_id": reviewer_id, "notes": notes})
        return status

    def record_feedback(self, run_id: str, outcome: str, notes: str, submitted_by: str) -> str | None:
        """Store test feedback alongside the corresponding in-memory run."""
        record = self.records.get(run_id)
        if not record:
            return None
        feedback_id = str(uuid4())
        record.setdefault("feedback", []).append({"feedback_id": feedback_id, "outcome": outcome, "notes": notes, "submitted_by": submitted_by})
        return feedback_id


class PostgresRunRepository:
    """PostgreSQL repository used by deployed API processes."""
    def __init__(self, dsn: str = DATABASE_URL) -> None:
        """Bind the repository to one PostgreSQL connection string."""
        self.dsn = dsn

    def save(self, run_id: str, expert_id: str, status: str, result: dict) -> None:
        """Upsert a result so it survives API process restarts."""
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO expert_runs (run_id, expert_id, status, result)
                    VALUES (%s, %s, %s, %s::jsonb)
                    ON CONFLICT (run_id) DO UPDATE SET
                        expert_id = EXCLUDED.expert_id, status = EXCLUDED.status,
                        result = EXCLUDED.result, updated_at = now()
                    """,
                    (run_id, expert_id, status, json.dumps(result)),
                )

    def get(self, run_id: str) -> dict | None:
        """Fetch the JSON result stored for a persisted run."""
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT result FROM expert_runs WHERE run_id = %s", (run_id,))
                row = cursor.fetchone()
        return row["result"] if row else None

    def record_review(self, run_id: str, decision: str, reviewer_id: str, notes: str) -> str | None:
        """Transactionally persist an audit item and the resulting run status."""
        status = {"APPROVE": "COMPLETED", "REJECT": "REJECTED", "REQUEST_RESEARCH": "PENDING_REVIEW"}[decision]
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE expert_runs SET status = %s, updated_at = now() WHERE run_id = %s", (status, run_id))
                if cursor.rowcount == 0:
                    return None
                cursor.execute(
                    "INSERT INTO expert_run_reviews (review_id, run_id, decision, reviewer_id, notes) VALUES (%s, %s, %s, %s, %s)",
                    (str(uuid4()), run_id, decision, reviewer_id, notes),
                )
        return status

    def record_feedback(self, run_id: str, outcome: str, notes: str, submitted_by: str) -> str | None:
        """Persist one follow-up outcome after confirming its run exists."""
        feedback_id = str(uuid4())
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM expert_runs WHERE run_id = %s", (run_id,))
                if cursor.fetchone() is None:
                    return None
                cursor.execute("INSERT INTO expert_run_feedback (feedback_id, run_id, outcome, notes, submitted_by) VALUES (%s, %s, %s, %s, %s)", (feedback_id, run_id, outcome, notes, submitted_by))
        return feedback_id


_memory_repository = InMemoryRunRepository()


def get_run_repository() -> RunRepository:
    """Select the configured persistence backend at the application boundary."""
    if RUN_BACKEND == "memory":
        return _memory_repository
    if RUN_BACKEND == "postgres":
        return PostgresRunRepository()
    raise ValueError(f"Unsupported RUN_BACKEND: {RUN_BACKEND}")
