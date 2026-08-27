"""Small, dependency-free benchmark runner for the current expert contract."""
from __future__ import annotations

import json
import os
from pathlib import Path

# Golden-data regression must be reproducible and must not spend tokens because
# a developer happened to have LLM credentials in .env. Set this explicitly only
# when conducting a separately governed live-model evaluation.
if os.getenv("EVALUATION_ALLOW_LLM", "false").lower() != "true":
    os.environ["LLM_ENABLED"] = "false"
# Golden-data regression also remains independent from any local city data.
os.environ["KNOWLEDGE_BACKEND"] = "seed"

from app.graph.main import expert_graph
from evaluation.metrics import evaluate_case, summarize_outcomes


def run(path: Path | None = None) -> dict[str, object]:
    source = path or Path(__file__).with_name("benchmark_housing_v1.json")
    benchmark = json.loads(source.read_text(encoding="utf-8"))
    outcomes: list[dict[str, object]] = []
    for case in benchmark["cases"]:
        state = expert_graph.invoke({"raw_event": case["event"], "expert_id": benchmark["expert_id"], "include_internal": False, "user_context": {}})
        outcomes.append(evaluate_case(case, state))
    return summarize_outcomes(outcomes)


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, ensure_ascii=False))
    if report["failed"]:
        raise SystemExit(1)
