from app.matching import evidence_score


def test_evidence_score_prefers_relevant_reliable_local_topic_evidence():
    matching = {"relevance": 0.8, "reliability": 0.9, "metadata": {"city": "重庆", "topics": ["城市生命线"]}}
    generic = {"relevance": 0.8, "reliability": 0.9, "metadata": {}}
    assert evidence_score(matching, city="重庆", topics=["城市生命线"]) > evidence_score(generic, city="重庆", topics=["城市生命线"])
