WEIGHTS = {
    "policy_signal": 0.10,
    "need_clarity": 0.15,
    "responsibility_match": 0.20,
    "department_match": 0.10,
    "company_capability": 0.15,
    "historical_case": 0.10,
    "customer_relationship": 0.10,
    "project_procurement": 0.10,
}


def calculate_score(state: dict) -> dict:
    """Calculate a reproducible score from signals, evidence, and matches."""
    analysis = state["event_analysis"]
    evidence = state.get("evidence", [])
    organization_score = max((item["score"] for item in state.get("organizations", [])), default=0.0)
    department_score = max((item["score"] for item in state.get("departments", [])), default=0.0)
    capability_score = max((item["score"] for item in state.get("capabilities", [])), default=0.0)
    need_score = max((item["confidence"] for item in state.get("needs", [])), default=0.0)
    evidence_types = {str(item["type"]) for item in evidence}
    factors = {
        "policy_signal": analysis["signals"]["policy_strength"],
        "need_clarity": need_score,
        "responsibility_match": organization_score,
        "department_match": department_score,
        "company_capability": capability_score,
        "historical_case": 1.0 if "CASE" in evidence_types else 0.0,
        "customer_relationship": 0.0,
        "project_procurement": max(analysis["signals"]["project_signal"], analysis["signals"]["procurement_signal"]),
    }
    opportunity_score = round(sum(factors[name] * WEIGHTS[name] for name in WEIGHTS) * 100)
    reliability = sum(item["reliability"] for item in evidence) / len(evidence) if evidence else 0.0
    coverage = min(1.0, len({item["type"] for item in evidence}) / 4)
    certainty = (need_score + organization_score + department_score) / 3
    confidence = round((reliability * 0.4) + (coverage * 0.3) + (certainty * 0.3), 2)
    level = "A" if opportunity_score >= 80 else "B" if opportunity_score >= 60 else "C"
    return {"opportunity_score": opportunity_score, "level": level, "confidence": confidence, "factors": factors}
