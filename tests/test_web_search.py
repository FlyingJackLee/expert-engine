"""Unit contracts for the optional web-search adapter."""
import io
import json

from app.knowledge.web import WebSearchClient


def test_web_search_maps_snippets_to_citations(monkeypatch):
    """External snippets retain URL and become auditable evidence."""
    payload = {"results": [{"url": "https://example.test/a", "title": "标题", "snippet": "摘要", "score": 0.8}]}
    monkeypatch.setattr("app.knowledge.web.request.urlopen", lambda *_args, **_kwargs: _Response(payload))
    result = WebSearchClient("https://search.test").search("城市生命线")
    assert result == [{"evidence_id": "https://example.test/a", "type": "WEB", "source_id": "https://example.test/a", "title": "标题", "content": "摘要", "organization": None, "source_url": "https://example.test/a", "relevance": 0.8, "metadata": {}}]


def test_web_search_ignores_empty_query():
    """Empty research questions must not call a remote provider."""
    assert WebSearchClient("https://search.test").search(" ") == []


class _Response(io.BytesIO):
    """Context-manager response double for the standard-library HTTP client."""

    def __init__(self, payload):
        super().__init__(json.dumps(payload).encode())

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
