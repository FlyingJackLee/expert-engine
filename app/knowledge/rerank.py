"""Deterministic evidence reranking used before expert matching."""
from __future__ import annotations


def rerank_evidence(query: str, evidence: list[dict]) -> list[dict]:
    """Fuse lexical coverage, initial retrieval relevance, and source reliability."""
    terms = {term.lower() for term in query.replace("，", " ").split() if len(term) > 1}
    ranked = []
    for item in evidence:
        searchable = f'{item["title"]} {item["content"]}'.lower()
        lexical = sum(term in searchable for term in terms) / len(terms) if terms else 0.0
        # Reranking may promote a well-supported match, but must not erase a
        # stronger relevance score supplied by the retrieval backend.
        blended = item["relevance"] * 0.5 + lexical * 0.3 + item["reliability"] * 0.2
        relevance = round(max(item["relevance"], blended), 2)
        ranked.append({**item, "relevance": relevance})
    return sorted(ranked, key=lambda item: (-item["relevance"], -item["reliability"], item["evidence_id"]))
