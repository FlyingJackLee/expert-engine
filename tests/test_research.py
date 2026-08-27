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
    ]
    assert result["research_city"] == "重庆"
