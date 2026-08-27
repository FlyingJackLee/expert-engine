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


def run(path: Path | None = None) -> dict[str, object]:
    source = path or Path(__file__).with_name("benchmark_housing_v1.json")
    benchmark = json.loads(source.read_text(encoding="utf-8"))
    outcomes: list[dict[str, object]] = []
    for case in benchmark["cases"]:
        state = expert_graph.invoke({"raw_event": case["event"], "expert_id": benchmark["expert_id"], "include_internal": False, "user_context": {}})
        result, expected = state["final_result"], case["expected"]
        actual_types = {str(item["type"]) for item in result["evidence"]}
        historical_types = {str(item["type"]) for item in result["historical_knowledge"]}
        historical_ids = {item["evidence_id"] for item in result["historical_knowledge"]}
        checks = {
            "topics": all(topic in state["event_analysis"]["topics"] for topic in expected["topics"]),
            "organization": result["organizations"][0]["organization_id"] in expected["organization_top3"],
            "department": result["departments"][0]["department_id"] in expected["department_top3"],
            "evidence": set(expected["required_evidence_types"]).issubset(actual_types),
            "review": result["review"]["decision"] == expected.get("review_decision", result["review"]["decision"]),
            "score": result["score"]["opportunity_score"] >= expected.get("min_score", 0),
            # A historical lesson must be visible as a separate, internal-only
            # context. This guards against silently treating experience as a current
            # policy or responsibility source during future retrieval changes.
            "historical_knowledge": set(expected.get("required_historical_evidence_ids", [])).issubset(historical_ids)
            and historical_types.issubset({"INTERNAL"}),
        }
        outcomes.append(
            {
                "id": case["id"],
                "passed": all(checks.values()),
                "checks": checks,
                "actual": {
                    "topics": state["event_analysis"]["topics"],
                    "score": result["score"]["opportunity_score"],
                    "review_decision": result["review"]["decision"],
                    "evidence_types": sorted(actual_types),
                    "historical_evidence_ids": sorted(historical_ids),
                },
            }
        )
    passed = sum(outcome["passed"] for outcome in outcomes)
    historical_cases = [outcome for outcome in outcomes if "historical_knowledge" in outcome["checks"]]
    return {
        "total": len(outcomes),
        "passed": passed,
        "failed": len(outcomes) - passed,
        "historical_knowledge_coverage": sum(outcome["checks"]["historical_knowledge"] for outcome in historical_cases) / len(historical_cases) if historical_cases else 1.0,
        "cases": outcomes,
    }


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, ensure_ascii=False))
    if report["failed"]:
        raise SystemExit(1)
