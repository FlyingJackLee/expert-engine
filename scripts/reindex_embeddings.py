"""Operational command for rebuilding vectors after an embedding model change."""
from app.knowledge.postgres import PostgresKnowledgeRepository


def main() -> None:
    """Reindex existing PostgreSQL chunks using the configured embedding endpoint."""
    result = PostgresKnowledgeRepository().reindex_embeddings()
    print(result)


if __name__ == "__main__":
    main()
