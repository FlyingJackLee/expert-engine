"""Run-result storage with a test-friendly in-memory backend and PostgreSQL persistence."""
from __future__ import annotations

import json
from typing import Protocol
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from app.config import DATABASE_URL, RUN_BACKEND


class RunRepository(Protocol):
    """Storage contract for analysis results, reviews, feedback and candidates."""
    def save(self, run_id: str, expert_id: str, status: str, result: dict) -> None:
        """Persist one completed or pending analysis result."""
    def get(self, run_id: str) -> dict | None:
        """Return a saved analysis result by its stable run ID."""
    def record_review(self, run_id: str, decision: str, reviewer_id: str, notes: str) -> str | None:
        """Append an audited human decision and return the new run status."""
    def record_feedback(self, run_id: str, outcome: str, notes: str, submitted_by: str) -> str | None:
        """Append a structured real-world outcome note for a saved run."""
    def candidate_context(self, run_id: str) -> dict | None:
        """Return the result and feedback snapshot required for candidate extraction."""
    def save_candidate(self, run_id: str, expert_id: str, content: dict, source_feedback_ids: list[str]) -> str | None:
        """Persist one candidate in its initial pending-approval state."""
    def get_candidate(self, candidate_id: str) -> dict | None:
        """Return a persisted candidate by its stable identifier."""
    def record_candidate_review(self, candidate_id: str, decision: str, reviewer_id: str, notes: str) -> str | None:
        """Audit an expert decision and return the resulting candidate status."""


class InMemoryRunRepository:
    """Process-local repository used only for fast, isolated tests."""
    def __init__(self) -> None:
        """Initialize an empty process-local record collection."""
        self.records: dict[str, dict] = {}

    def save(self, run_id: str, expert_id: str, status: str, result: dict) -> None:
        """Store a result in process memory for one isolated test process."""
        existing = self.records.get(run_id, {})
        self.records[run_id] = {"expert_id": expert_id, "status": status, "result": result, "reviews": existing.get("reviews", []), "feedback": existing.get("feedback", []), "candidates": existing.get("candidates", [])}

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

    def candidate_context(self, run_id: str) -> dict | None:
        """Return a local immutable-looking snapshot for candidate extraction tests."""
        record = self.records.get(run_id)
        if not record:
            return None
        return {"run_id": run_id, "expert_id": record["expert_id"], "result": record["result"], "feedback": list(record.get("feedback", []))}

    def save_candidate(self, run_id: str, expert_id: str, content: dict, source_feedback_ids: list[str]) -> str | None:
        """Store a pending candidate with its feedback provenance in memory."""
        record = self.records.get(run_id)
        if not record:
            return None
        candidate_id = str(uuid4())
        record.setdefault("candidates", []).append({"candidate_id": candidate_id, "run_id": run_id, "expert_id": expert_id, "status": "PENDING_APPROVAL", "content": content, "source_feedback_ids": source_feedback_ids})
        return candidate_id

    def get_candidate(self, candidate_id: str) -> dict | None:
        """Find a locally stored candidate across isolated test records."""
        for record in self.records.values():
            for candidate in record.get("candidates", []):
                if candidate["candidate_id"] == candidate_id:
                    return candidate
        return None

    def record_candidate_review(self, candidate_id: str, decision: str, reviewer_id: str, notes: str) -> str | None:
        """Audit one local expert decision, allowing only pending candidates to change."""
        candidate = self.get_candidate(candidate_id)
        if candidate is None:
            return None
        if candidate["status"] != "PENDING_APPROVAL":
            return "ALREADY_REVIEWED"
        status = {"APPROVE": "APPROVED", "REJECT": "REJECTED"}[decision]
        candidate["status"] = status
        candidate.setdefault("reviews", []).append({"review_id": str(uuid4()), "decision": decision, "reviewer_id": reviewer_id, "notes": notes})
        return status


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

    def candidate_context(self, run_id: str) -> dict | None:
        """Read one run and all feedback needed to create a traceable candidate."""
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT expert_id, result FROM expert_runs WHERE run_id = %s", (run_id,))
                run = cursor.fetchone()
                if run is None:
                    return None
                cursor.execute("SELECT feedback_id, outcome, notes, submitted_by FROM expert_run_feedback WHERE run_id = %s ORDER BY created_at, feedback_id", (run_id,))
                feedback = cursor.fetchall()
        return {"run_id": run_id, "expert_id": run["expert_id"], "result": run["result"], "feedback": feedback}

    def save_candidate(self, run_id: str, expert_id: str, content: dict, source_feedback_ids: list[str]) -> str | None:
        """Persist a candidate without publishing it into the retrieval knowledge base."""
        candidate_id = str(uuid4())
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM expert_runs WHERE run_id = %s", (run_id,))
                if cursor.fetchone() is None:
                    return None
                cursor.execute(
                    "INSERT INTO expert_knowledge_candidates (candidate_id, run_id, expert_id, status, content, source_feedback_ids) VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb)",
                    (candidate_id, run_id, expert_id, "PENDING_APPROVAL", json.dumps(content), json.dumps(source_feedback_ids)),
                )
        return candidate_id

    def get_candidate(self, candidate_id: str) -> dict | None:
        """Fetch an unpublished candidate for display or later expert approval."""
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT candidate_id, run_id, status, content, source_feedback_ids FROM expert_knowledge_candidates WHERE candidate_id = %s", (candidate_id,))
                return cursor.fetchone()

    def record_candidate_review(self, candidate_id: str, decision: str, reviewer_id: str, notes: str) -> str | None:
        """Atomically audit an expert decision for a candidate still awaiting approval."""
        status = {"APPROVE": "APPROVED", "REJECT": "REJECTED"}[decision]
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE expert_knowledge_candidates SET status = %s WHERE candidate_id = %s AND status = %s", (status, candidate_id, "PENDING_APPROVAL"))
                if cursor.rowcount == 0:
                    cursor.execute("SELECT status FROM expert_knowledge_candidates WHERE candidate_id = %s", (candidate_id,))
                    row = cursor.fetchone()
                    return None if row is None else "ALREADY_REVIEWED"
                cursor.execute(
                    "INSERT INTO expert_knowledge_candidate_reviews (review_id, candidate_id, decision, reviewer_id, notes) VALUES (%s, %s, %s, %s, %s)",
                    (str(uuid4()), candidate_id, decision, reviewer_id, notes),
                )
        return status


_memory_repository = InMemoryRunRepository()


def get_run_repository() -> RunRepository:
    """Select the configured persistence backend at the application boundary."""
    if RUN_BACKEND == "memory":
        return _memory_repository
    if RUN_BACKEND == "postgres":
        return PostgresRunRepository()
    raise ValueError(f"Unsupported RUN_BACKEND: {RUN_BACKEND}")
