from app.config import KNOWLEDGE_BACKEND
from app.llm import gateway
from app.knowledge.seed import SEED_EVIDENCE


def retrieve(query: str, types: set[str] | None = None, limit: int = 6, city: str | None = None, topics: list[str] | None = None) -> list[dict]:
    """Knowledge retrieval facade. Postgres is opt-in until the service is provisioned."""
    if KNOWLEDGE_BACKEND == "postgres":
        from app.knowledge.postgres import PostgresKnowledgeRepository
        return PostgresKnowledgeRepository().search(query, types, limit, city=city, topics=topics, query_embedding=gateway.embed_texts([query]))
    if KNOWLEDGE_BACKEND != "seed":
        raise ValueError(f"Unsupported KNOWLEDGE_BACKEND: {KNOWLEDGE_BACKEND}")
    # This deterministic fallback exists only for the Phase 1 demo. It keeps tests
    # independent of Docker while exposing the same Evidence contract as PostgreSQL.
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
