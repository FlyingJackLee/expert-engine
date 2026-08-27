import logging

from app.config import BM25_API_KEY, BM25_BASE_URL, BM25_ENABLED, BM25_INDEX, KNOWLEDGE_BACKEND
from app.knowledge.bm25 import OpenSearchBM25
from app.llm import gateway
from app.knowledge.seed import SEED_EVIDENCE

logger = logging.getLogger(__name__)


def retrieve(query: str, types: set[str] | None = None, limit: int = 6, city: str | None = None, topics: list[str] | None = None) -> list[dict]:
    """Knowledge retrieval facade. Postgres is opt-in until the service is provisioned."""
    if KNOWLEDGE_BACKEND == "postgres":
        from app.knowledge.postgres import PostgresKnowledgeRepository
        primary = PostgresKnowledgeRepository().search(query, types, limit, city=city, topics=topics, query_embedding=gateway.embed_texts([query]))
    elif KNOWLEDGE_BACKEND == "seed":
        primary = _seed_retrieve(query, types, limit)
    else:
        raise ValueError(f"Unsupported KNOWLEDGE_BACKEND: {KNOWLEDGE_BACKEND}")

    bm25 = _bm25_retrieve(query, types, limit, city=city, topics=topics)
    return _merge_evidence(primary, bm25, limit)


def _seed_retrieve(query: str, types: set[str] | None, limit: int) -> list[dict]:
    """Retrieve from deterministic seed data for local development and tests."""
    query_terms = set(query.lower().replace("，", " ").split())
    ranked: list[tuple[int, dict]] = []
    for item in SEED_EVIDENCE:
        if types and str(item["type"]) not in types:
            continue
        searchable = f'{item["title"]} {item["content"]}'.lower()
        score = sum(term in searchable for term in query_terms if len(term) > 1)
        if score or any(keyword in searchable for keyword in ("生命线", "住建", "城市")):
            ranked.append((score, dict(item)))
    return [item for _, item in sorted(ranked, key=lambda pair: pair[0], reverse=True)[:limit]]


def _bm25_retrieve(query: str, types: set[str] | None, limit: int, *, city: str | None, topics: list[str] | None) -> list[dict]:
    """Query optional BM25 and apply engine-owned metadata filters after retrieval."""
    if not BM25_ENABLED or not BM25_BASE_URL:
        return []
    try:
        results = OpenSearchBM25(BM25_BASE_URL, BM25_INDEX, BM25_API_KEY).search(query, limit)
    except Exception as exc:  # pragma: no cover - network behavior belongs to integration tests
        logger.warning("BM25 retrieval unavailable; continuing with primary knowledge backend: %s", exc)
        return []
    filtered = []
    for item in results:
        metadata = item.get("metadata") or {}
        if types and item.get("type") not in types:
            continue
        if city and metadata.get("city") != city:
            continue
        if topics and not set(topics).intersection(metadata.get("topics", [])):
            continue
        filtered.append(item)
    return filtered


def _merge_evidence(primary: list[dict], secondary: list[dict], limit: int) -> list[dict]:
    """Deduplicate multi-source evidence and rank by normalized relevance."""
    merged = {item["evidence_id"]: item for item in [*primary, *secondary]}
    return sorted(merged.values(), key=lambda item: (float(item.get("relevance", 0.0)), item["evidence_id"]), reverse=True)[:limit]
