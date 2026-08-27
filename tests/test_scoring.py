from app.scoring.engine import WEIGHTS, calculate_score


def test_score_is_deterministic_and_weighted():
    state = {"event_analysis": {"signals": {"policy_strength": 1, "project_signal": 1, "procurement_signal": 0}}, "evidence": [{"type": "POLICY", "reliability": 1}, {"type": "INDUSTRY", "reliability": 1}, {"type": "RESPONSIBILITY", "reliability": 1}, {"type": "CASE", "reliability": 1}], "needs": [{"confidence": 1}], "organizations": [{"score": 1}], "departments": [{"score": 1}], "capabilities": [{"score": 1}]}
    score = calculate_score(state)
    assert sum(WEIGHTS.values()) == 1
    assert score["opportunity_score"] == 90
    assert score["confidence"] == 1
