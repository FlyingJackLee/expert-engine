"""PostgreSQL knowledge repository.

The embedding column is intentionally nullable: Phase 2 persists evidence first;
vector search is enabled after an embedding provider is configured in the LLM Gateway.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import DATABASE_URL


class PostgresKnowledgeRepository:
    """PostgreSQL implementation for source-document ingestion and retrieval."""
    def __init__(self, dsn: str = DATABASE_URL) -> None:
        """Bind knowledge operations to the configured PostgreSQL database."""
        self.dsn = dsn

    def ingest(self, document: dict[str, Any]) -> None:
        """Upsert a source document and its chunks atomically.

        Keeping document metadata separate from chunks lets later retrieval return a
        small, citable evidence slice instead of moving full source files through
        LangGraph state.
        """
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                self.ingest_with_cursor(cursor, document)

    @staticmethod
    def ingest_with_cursor(cursor: Any, document: dict[str, Any]) -> None:
        """Upsert a document using a caller-owned transaction cursor."""
        cursor.execute(
                    """
                    INSERT INTO knowledge_documents
                    (document_id, source_type, title, source_url, organization, reliability, effective_date, metadata)
                    VALUES (%(document_id)s, %(source_type)s, %(title)s, %(source_url)s, %(organization)s,
                            %(reliability)s, %(effective_date)s, %(metadata)s::jsonb)
                    ON CONFLICT (document_id) DO UPDATE SET
                      source_type = EXCLUDED.source_type, title = EXCLUDED.title, source_url = EXCLUDED.source_url,
                      organization = EXCLUDED.organization, reliability = EXCLUDED.reliability,
                      effective_date = EXCLUDED.effective_date, metadata = EXCLUDED.metadata
                    """,
                    {**document, "effective_date": document.get("effective_date"), "metadata": json.dumps(document.get("metadata", {}))},
        )
        for index, content in enumerate(document["chunks"]):
            cursor.execute(
                        """
                        INSERT INTO knowledge_chunks (chunk_id, document_id, chunk_index, content)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (document_id, chunk_index) DO UPDATE SET content = EXCLUDED.content
                        """,
                        (f"{document['document_id']}:chunk:{index}", document["document_id"], index, content),
            )

    def search(self, query: str, types: set[str] | None = None, limit: int = 6, *, city: str | None = None, topics: list[str] | None = None) -> list[dict[str, Any]]:
        """Return ranked evidence with metadata filters applied in the database."""
        type_filter = list(types) if types else None
        topic_filter = topics or None
        query_terms = [term for term in query.replace("，", " ").split() if len(term) > 1][:8]
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                # Chinese text has no reliable whitespace tokenization here. Until a
                # dedicated embedding/BM25 service is configured, substring overlap
                # provides a deterministic baseline and always preserves filters.
                cursor.execute(
                    """
                    SELECT COALESCE(d.metadata ->> 'seed_evidence_id', c.chunk_id) AS evidence_id,
                           d.source_type AS type, d.document_id AS source_id, d.title, c.content,
                           d.organization, d.source_url, d.reliability, d.effective_date, d.metadata, c.chunk_index,
                           CASE WHEN cardinality(%s::text[]) = 0 THEN 0
                                ELSE cardinality(ARRAY(SELECT term FROM unnest(%s::text[]) AS term WHERE c.content ILIKE '%%' || term || '%%')) END AS matched_terms
                    FROM knowledge_chunks c
                    JOIN knowledge_documents d ON d.document_id = c.document_id
                    WHERE (%s::text[] IS NULL OR d.source_type = ANY(%s::text[]))
                      AND (%s::text IS NULL OR d.metadata ->> 'city' = %s)
                      AND (%s::text[] IS NULL OR d.metadata -> 'topics' ?| %s::text[])
                    ORDER BY matched_terms DESC, d.reliability DESC, d.effective_date DESC NULLS LAST, d.document_id
                    LIMIT %s
                    """,
                    (query_terms, query_terms, type_filter, type_filter, city, city, topic_filter, topic_filter, limit),
                )
                rows = cursor.fetchall()
        return [
            # Imported seed data retains its stable ID for regression compatibility;
            # documents supplied by users expose their immutable chunk ID instead.
            {"evidence_id": row["evidence_id"], "type": row["type"], "source_id": row["source_id"], "title": row["title"], "content": row["content"], "organization": row["organization"], "source_url": row["source_url"], "relevance": min(1.0, 0.55 + row["matched_terms"] * 0.1), "reliability": row["reliability"], "effective_date": row["effective_date"].isoformat() if isinstance(row["effective_date"], date) else None, "chunk_index": row["chunk_index"], "metadata": row["metadata"]}
            for row in rows
        ]
