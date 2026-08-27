from app.nodes.core import refine_research, route_after_review


def test_reviewer_gaps_produce_a_bounded_follow_up_research_plan(monkeypatch):
    monkeypatch.setattr("app.nodes.core.MAX_RESEARCH_RETRIES", 1)
    state = {
        "retry_count": 0,
        "research_plan": {"questions": ["已有问题"]},
        "review_result": {"decision": "RESEARCH_MORE", "issues": [{"type": "MISSING_POLICY_EVIDENCE", "message": "缺乏政策直接证据。"}]},
    }
    assert route_after_review(state) == "refine_research"
    refined = refine_research(state)
    assert refined["retry_count"] == 1
    assert len(refined["research_plan"]["questions"]) == 2
    state.update(refined)
    assert route_after_review(state) == "finalize"
