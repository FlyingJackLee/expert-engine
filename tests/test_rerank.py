from app.knowledge.rerank import rerank_evidence


def test_reranker_prefers_lexically_matching_reliable_evidence():
    evidence = [
        {"evidence_id": "weak", "title": "其他事项", "content": "无相关内容", "relevance": 0.7, "reliability": 0.6},
        {"evidence_id": "strong", "title": "城市生命线建设", "content": "城市生命线监测预警", "relevance": 0.7, "reliability": 1.0},
    ]
    assert rerank_evidence("城市生命线", evidence)[0]["evidence_id"] == "strong"
