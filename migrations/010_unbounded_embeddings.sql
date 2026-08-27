ALTER TABLE knowledge_chunks
    ALTER COLUMN embedding TYPE vector;

ALTER TABLE knowledge_chunks
    ADD COLUMN IF NOT EXISTS embedding_model TEXT;
