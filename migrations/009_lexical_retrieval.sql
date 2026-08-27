CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_content_trgm
    ON knowledge_chunks USING GIN (content gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_content_fts
    ON knowledge_chunks USING GIN (to_tsvector('simple', content));
