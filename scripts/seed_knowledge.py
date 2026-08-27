from app.knowledge.postgres import PostgresKnowledgeRepository
from app.knowledge.seed import SEED_EVIDENCE


def main() -> None:
    """Load deterministic demo evidence; never use this command for production data."""
    repository = PostgresKnowledgeRepository()
    for evidence in SEED_EVIDENCE:
        repository.ingest(
            {
                "document_id": evidence["source_id"],
                "source_type": str(evidence["type"]),
                "title": evidence["title"],
                "chunks": [evidence["content"]],
                "source_url": evidence["source_url"],
                "organization": evidence["organization"],
                "reliability": evidence["reliability"],
                "effective_date": evidence["effective_date"],
                "metadata": {"seed_evidence_id": evidence["evidence_id"], **evidence.get("metadata", {})},
            }
        )
    print(f"Ingested {len(SEED_EVIDENCE)} seed documents")


if __name__ == "__main__":
    main()
