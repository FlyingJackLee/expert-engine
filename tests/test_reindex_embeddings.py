"""Unit contracts for safe vector rebuild batching and configuration handling."""
import pytest

from app.knowledge.postgres import PostgresKnowledgeRepository


def test_reindex_rejects_non_positive_batch_size():
    """Operational reindex must fail before opening a database for invalid input."""
    with pytest.raises(ValueError, match="batch_size"):
        PostgresKnowledgeRepository("unused").reindex_embeddings(0)
