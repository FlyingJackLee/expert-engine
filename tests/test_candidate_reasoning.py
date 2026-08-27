"""Safety contracts for constrained LLM candidate selection."""
from app.nodes import core
from app.schemas.domain import CandidateSelection


def test_candidate_reasoning_discards_unknown_ids_before_updating_matches(monkeypatch):
    """A model can select only candidates previously created from evidence."""
    monkeypatch.setattr(
        core.gateway,
        "structured_generate",
        lambda *args: CandidateSelection(
            organization_ids=["org_allowed", "org_unknown"],
            department_ids=[],
            capability_ids=[],
            rationale="优先保留已有证据支撑的候选。",
        ),
    )
    state = {
        "expert_profile": {"id": "test", "runtime": "app.experts.housing:runtime"},
        "event_analysis": {"topics": ["任意主题"]},
        "organizations": [{"organization_id": "org_allowed", "name": "允许候选", "score": 0.8, "evidence_ids": ["ev-1"]}],
        "departments": [{"department_id": "dept_allowed", "name": "允许处室", "score": 0.8, "evidence_ids": ["ev-2"]}],
        "capabilities": [{"capability_id": "cap_allowed", "name": "允许能力", "score": 0.8, "evidence_ids": ["ev-3"]}],
    }
    result = core.reason_about_candidates(state)
    assert result["candidate_reasoning"]["organization_ids"] == ["org_allowed"]
    assert [item["organization_id"] for item in result["organizations"]] == ["org_allowed"]
    assert "departments" not in result
    assert "capabilities" not in result
