"""Unit contracts for deterministic citation completeness checks."""
from app.knowledge.grounding import validate_citation


def test_validate_citation_accepts_http_source():
    """A complete web citation is eligible for grounded status."""
    result = validate_citation({"evidence_id": "e1", "source_id": "s1", "title": "标题", "content": "正文", "source_url": "https://example.test"})
    assert result == {"complete": True, "url_valid": True, "missing": []}


def test_validate_citation_reports_missing_content():
    """Missing source content is explicit instead of silently marked grounded."""
    result = validate_citation({"evidence_id": "e1", "source_id": "s1", "title": "标题", "content": "", "source_url": "bad"})
    assert result["complete"] is False
    assert result["url_valid"] is False
    assert result["missing"] == ["content"]
