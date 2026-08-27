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
from app.llm import gateway


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
        embeddings = document.get("embeddings")
        if embeddings is None:
            embeddings = gateway.embed_texts(document["chunks"])
        if embeddings is not None and len(embeddings) != len(document["chunks"]):
            raise ValueError("Embedding provider returned a vector count different from document chunks")
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
                INSERT INTO knowledge_chunks (chunk_id, document_id, chunk_index, content, embedding, embedding_model)
                VALUES (%s, %s, %s, %s, %s::vector, %s)
                ON CONFLICT (document_id, chunk_index) DO UPDATE SET content = EXCLUDED.content, embedding = EXCLUDED.embedding, embedding_model = EXCLUDED.embedding_model
                """,
                (f"{document['document_id']}:chunk:{index}", document["document_id"], index, content, _vector_literal(embeddings[index]) if embeddings else None, gateway.resolve_model_profile("embedding").model if embeddings else None),
            )

    def search(self, query: str, types: set[str] | None = None, limit: int = 6, *, city: str | None = None, topics: list[str] | None = None, query_embedding: list[list[float]] | None = None) -> list[dict[str, Any]]:
        """Return ranked evidence with metadata filters applied in the database."""
        type_filter = list(types) if types else None
        topic_filter = topics or None
        query_terms = [term for term in query.replace("，", " ").split() if len(term) > 1][:8]
        full_text_query = " ".join(query_terms)
        vector_literal = _vector_literal(query_embedding[0]) if query_embedding else None
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                # Full text serves languages with token boundaries; trigram similarity
                # is a language-neutral complement when the source has no whitespace.
                cursor.execute(
                    """
                    SELECT COALESCE(d.metadata ->> 'seed_evidence_id', c.chunk_id) AS evidence_id,
                           d.source_type AS type, d.document_id AS source_id, d.title, c.content,
                           d.organization, d.source_url, d.reliability, d.effective_date, d.metadata, c.chunk_index,
                           CASE WHEN cardinality(%s::text[]) = 0 THEN 0
                                ELSE cardinality(ARRAY(SELECT term FROM unnest(%s::text[]) AS term WHERE concat_ws(' ', d.title, c.content) ILIKE '%%' || term || '%%')) END AS matched_terms,
                           ts_rank_cd(to_tsvector('simple', concat_ws(' ', d.title, c.content)), websearch_to_tsquery('simple', %s)) AS full_text_rank,
                           COALESCE((SELECT MAX(similarity(concat_ws(' ', d.title, c.content), term)) FROM unnest(%s::text[]) AS term), 0) AS trigram_similarity,
                           CASE WHEN %s::vector IS NULL OR c.embedding IS NULL THEN NULL ELSE c.embedding <=> %s::vector END AS vector_distance
                    FROM knowledge_chunks c
                    JOIN knowledge_documents d ON d.document_id = c.document_id
                    WHERE (%s::text[] IS NULL OR d.source_type = ANY(%s::text[]))
                      AND (d.source_type <> 'INTERNAL' OR COALESCE(d.metadata ->> 'knowledge_status', 'PUBLISHED') = 'PUBLISHED')
                      AND (%s::vector IS NULL OR c.embedding IS NULL OR vector_dims(c.embedding) = vector_dims(%s::vector))
                      AND (%s::text IS NULL OR d.metadata ->> 'city' = %s)
                      AND (%s::text[] IS NULL OR d.metadata -> 'topics' ?| %s::text[])
                    ORDER BY vector_distance ASC NULLS LAST, full_text_rank DESC, trigram_similarity DESC, matched_terms DESC, d.reliability DESC, d.effective_date DESC NULLS LAST, d.document_id
                    LIMIT %s
                    """,
                    (query_terms, query_terms, full_text_query, query_terms, vector_literal, vector_literal, type_filter, type_filter, vector_literal, vector_literal, city, city, topic_filter, topic_filter, limit),
                )
                rows = cursor.fetchall()
        return [
            # Imported seed data retains its stable ID for regression compatibility;
            # documents supplied by users expose their immutable chunk ID instead.
            {"evidence_id": row["evidence_id"], "type": row["type"], "source_id": row["source_id"], "title": row["title"], "content": row["content"], "organization": row["organization"], "source_url": row["source_url"], "relevance": _lexical_relevance(row, len(query_terms)), "reliability": row["reliability"], "effective_date": row["effective_date"].isoformat() if isinstance(row["effective_date"], date) else None, "chunk_index": row["chunk_index"], "metadata": row["metadata"]}
            for row in rows
        ]

    def reindex_embeddings(self, batch_size: int = 32) -> dict[str, int | str]:
        """Regenerate all chunk vectors with the currently configured embedding model."""
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT chunk_id, content FROM knowledge_chunks ORDER BY chunk_id")
                chunks = cursor.fetchall()
        if not chunks:
            return {"status": "EMPTY", "processed": 0}
        processed = 0
        model = gateway.resolve_model_profile("embedding").model
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            vectors = gateway.embed_texts([item["content"] for item in batch])
            if vectors is None:
                return {"status": "SKIPPED", "processed": processed}
            if len(vectors) != len(batch):
                raise ValueError("Embedding provider returned a vector count different from reindex batch")
            with psycopg.connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    for item, vector in zip(batch, vectors, strict=True):
                        cursor.execute("UPDATE knowledge_chunks SET embedding = %s::vector, embedding_model = %s WHERE chunk_id = %s", (_vector_literal(vector), model, item["chunk_id"]))
            processed += len(batch)
        return {"status": "COMPLETED", "processed": processed}


def _lexical_relevance(row: dict[str, Any], term_count: int) -> float:
    """Fuse lexical signals without weakening the prior compatible relevance floor."""
    coverage = row["matched_terms"] / term_count if term_count else 0.0
    full_text = min(float(row["full_text_rank"]), 1.0)
    trigram = min(float(row["trigram_similarity"]), 1.0)
    fusion = min(1.0, 0.45 * coverage + 0.35 * full_text + 0.2 * trigram)
    legacy_baseline = min(1.0, 0.55 + row["matched_terms"] * 0.1)
    return round(max(fusion, legacy_baseline), 2)


def _vector_literal(vector: list[float]) -> str | None:
    """Serialize a provider vector for pgvector without assuming its dimension."""
    if not vector:
        return None
    return "[" + ",".join(str(float(value)) for value in vector) + "]"
