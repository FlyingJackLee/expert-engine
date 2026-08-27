"""Reusable quality metrics for golden-sample analysis evaluation."""
from __future__ import annotations


def evaluate_case(case: dict, state: dict) -> dict:
    """Compare one system result with its business-approved expectations."""
    result = state["final_result"]
    expected = case["expected"]
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
        "historical_knowledge": set(expected.get("required_historical_evidence_ids", [])).issubset(historical_ids)
        and historical_types.issubset({"INTERNAL"}),
    }
    return {"id": case["id"], "passed": all(checks.values()), "checks": checks, "actual": {"topics": state["event_analysis"]["topics"], "score": result["score"]["opportunity_score"], "review_decision": result["review"]["decision"], "evidence_types": sorted(actual_types), "historical_evidence_ids": sorted(historical_ids)}}


def summarize_outcomes(outcomes: list[dict]) -> dict:
    """Aggregate case outcomes into stable regression metrics."""
    passed = sum(bool(item["passed"]) for item in outcomes)
    historical_cases = [item for item in outcomes if "historical_knowledge" in item["checks"]]
    return {"total": len(outcomes), "passed": passed, "failed": len(outcomes) - passed, "historical_knowledge_coverage": sum(item["checks"]["historical_knowledge"] for item in historical_cases) / len(historical_cases) if historical_cases else 1.0, "cases": outcomes}
