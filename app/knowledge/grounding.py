"""Deterministic citation validation shared by Evidence Grounding and review."""
from urllib.parse import urlparse


def validate_citation(evidence: dict) -> dict:
    """Return auditable completeness flags without performing network requests."""
    source_url = evidence.get("source_url")
    url_valid = not source_url or urlparse(source_url).scheme in {"http", "https"}
    complete = bool(evidence.get("evidence_id") and evidence.get("source_id") and evidence.get("title") and evidence.get("content") and url_valid)
    return {"complete": complete, "url_valid": url_valid, "missing": _missing_fields(evidence)}


def _missing_fields(evidence: dict) -> list[str]:
    """List absent citation fields so a Reviewer can explain the grounding gap."""
    return [field for field in ("evidence_id", "source_id", "title", "content") if not evidence.get(field)]
