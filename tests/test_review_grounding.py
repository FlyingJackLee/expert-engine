"""Unit contracts for reviewer routing from citation validation results."""
from app.nodes.core import review
from app.experts import load_profile


def test_review_routes_invalid_grounding_to_claim_type():
    """An ungrounded claim creates a structured issue and targeted retry."""
    state = {
        "evidence": [{"type": "POLICY"}],
        "departments": [{"evidence_ids": ["e1"]}],
        "grounding": [{"claim_type": "DEPARTMENT", "status": "UNGROUNDED", "citations": [{"validation": {"complete": False, "missing": ["content"]}}]}],
        "expert_profile": load_profile("housing_digitalization"),
        "score": {"confidence": 0.5},
    }
    result = review(state)["review_result"]
    assert result["decision"] == "RESEARCH_MORE"
    assert result["retry_targets"] == ["DEPARTMENT"]
    assert result["issues"][0]["type"] == "INVALID_CITATION"
