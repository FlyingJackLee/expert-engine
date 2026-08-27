"""Generic, evidence-only candidate ranking shared by expert runtimes."""
from __future__ import annotations

from app.config import MATCHING_WEIGHTS


def evidence_score(item: dict, *, city: str | None = None, topics: list[str] | None = None) -> float:
    """Rank an evidence item without adding facts not present in its metadata."""
    metadata = item.get("metadata") or {}
    context_scores = []
    if city:
        item_city = metadata.get("city")
        context_scores.append(1.0 if item_city == city else 0.5 if not item_city else 0.0)
    if topics:
        item_topics = set(metadata.get("topics") or [])
        context_scores.append(1.0 if item_topics.intersection(topics) else 0.5 if not item_topics else 0.0)
    context = sum(context_scores) / len(context_scores) if context_scores else 0.5
    return round(
        item["relevance"] * MATCHING_WEIGHTS["relevance"]
        + item["reliability"] * MATCHING_WEIGHTS["reliability"]
        + context * MATCHING_WEIGHTS["context"],
        2,
    )
