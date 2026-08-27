"""Standard Expert capability and knowledge-readiness reporting service."""
from __future__ import annotations

import json
import os
import subprocess
import sys

from app.knowledge.postgres import PostgresKnowledgeRepository
from app.schemas.domain import EvidenceType


def capability_report(expert_profile_id: str = "AUTO") -> dict:
    """Combine isolated golden evaluation with current knowledge-domain coverage."""
    benchmark = _run_benchmark()
    try:
        available = {str(row["source_type"]) for row in PostgresKnowledgeRepository().summary()}
    except Exception as exc:  # pragma: no cover - deployment infrastructure branch
        available = set()
        benchmark["knowledge_error"] = str(exc)
    required = {item.value for item in EvidenceType}
    total = benchmark.get("total", 0)
    benchmark.update({
        "expert_profile_id": expert_profile_id,
        "capability_score": round(benchmark.get("passed", 0) / total * 100, 1) if total else None,
        "knowledge_readiness": round(len(available & required) / len(required) * 100, 1),
        "available_knowledge_domains": sorted(available & required),
        "missing_knowledge_domains": sorted(required - available),
    })
    return benchmark


def _run_benchmark() -> dict:
    """Run the deterministic benchmark in an isolated environment."""
    forced = {"LLM_ENABLED": "false", "KNOWLEDGE_BACKEND": "seed", "HITL_CHECKPOINT_BACKEND": "memory"}
    environment = {**os.environ, **forced}
    completed = subprocess.run([sys.executable, "-m", "evaluation.run_benchmark"], capture_output=True, text=True, env=environment, check=False)
    if completed.returncode != 0:
        return {"error": completed.stderr.strip() or completed.stdout.strip()}
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"error": "Benchmark 输出无法解析"}
