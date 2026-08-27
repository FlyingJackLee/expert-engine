"""Unit contracts for the optional OpenSearch BM25 adapter."""
import io
import json

from app.knowledge.bm25 import OpenSearchBM25


def test_bm25_maps_hits_to_evidence(monkeypatch):
    """Provider-specific hit details become the shared evidence envelope."""
    payload = {"hits": {"hits": [{"_id": "1", "_index": "docs", "_score": 2.5, "_source": {"content": "正文", "title": "标题"}}]}}
    monkeypatch.setattr("app.knowledge.bm25.request.urlopen", lambda *_args, **_kwargs: _Response(payload))
    result = OpenSearchBM25("http://search", "knowledge").search("城市生命线")
    assert result[0]["evidence_id"] == "1"
    assert result[0]["relevance"] == 2.5


def test_bm25_ignores_empty_query():
    """Empty research questions must not create remote requests."""
    assert OpenSearchBM25("http://search", "knowledge").search(" ") == []


class _Response(io.BytesIO):
    """Small context-manager response double for the standard-library client."""

    def __init__(self, payload):
        super().__init__(json.dumps(payload).encode())

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
