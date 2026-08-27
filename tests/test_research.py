from app.nodes import core


def test_research_separates_evidence_types_and_applies_city_to_local_sources(monkeypatch):
    calls = []

    def fake_retrieve(query, types=None, limit=6, city=None, topics=None):
        calls.append((types, city, topics))
        return []

    monkeypatch.setattr(core, "retrieve", fake_retrieve)
    result = core.research({"raw_event": {"city": "重庆", "title": "重庆城市生命线"}, "user_context": {}, "event_analysis": {"topics": ["城市生命线"]}, "research_plan": {"questions": ["城市生命线"]}})
    assert calls == [
        ({"POLICY", "INDUSTRY"}, "重庆", ["城市生命线"]),
        ({"RESPONSIBILITY"}, "重庆", None),
        ({"CAPABILITY"}, None, ["城市生命线"]),
        ({"CASE"}, None, ["城市生命线"]),
        ({"INTERNAL"}, None, None),
    ]
    assert result["research_city"] == "重庆"


def test_historical_knowledge_is_explicitly_separated_from_primary_evidence():
    """Only published internal evidence may become historical reasoning context."""
    state = {"evidence": [{"evidence_id": "policy-1", "type": "POLICY"}, {"evidence_id": "knowledge-1", "type": "INTERNAL"}]}
    result = core.extract_historical_knowledge(state)
    assert result["historical_knowledge"] == [{"evidence_id": "knowledge-1", "type": "INTERNAL"}]
