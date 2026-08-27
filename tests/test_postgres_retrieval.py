"""Unit contracts for deterministic PostgreSQL lexical-score fusion."""
from app.knowledge.postgres import _hybrid_relevance, _lexical_relevance, _vector_literal


def test_lexical_relevance_fuses_coverage_full_text_and_trigram_signals():
    """All generic lexical signals contribute without exceeding the Evidence range."""
    score = _lexical_relevance(
        {"matched_terms": 2, "full_text_rank": 0.5, "trigram_similarity": 0.75},
        term_count=4,
    )
    assert score == 0.75


def test_lexical_relevance_remains_bounded_for_unusually_large_backend_scores():
    """Database rank variations cannot create an invalid evidence relevance score."""
    assert _lexical_relevance({"matched_terms": 5, "full_text_rank": 9, "trigram_similarity": 3}, term_count=1) == 1.0


def test_vector_literal_preserves_provider_dimension_without_hardcoding_it():
    """The pgvector query payload accepts any configured embedding length."""
    assert _vector_literal([0.1, 0.25, -0.5]) == "[0.1,0.25,-0.5]"
    assert _vector_literal([]) is None


def test_vector_literal_handles_missing_embedding_without_fabricating_values():
    """Disabled or unavailable embedding generation remains a NULL vector."""
    assert _vector_literal(None) is None


def test_hybrid_relevance_falls_back_to_lexical_when_vector_is_missing():
    """A partial embedding rollout must preserve the existing lexical score."""
    assert _hybrid_relevance(0.75, None) == 0.75


def test_hybrid_relevance_bounds_provider_distance():
    """Unexpected provider distances cannot push relevance outside the valid range."""
    assert 0.0 <= _hybrid_relevance(0.4, 2.0) <= 1.0
