from app.config import KNOWLEDGE_BACKEND


def test_configuration_has_a_safe_default_backend():
    """A missing .env must not stop a fresh checkout from starting."""
    assert KNOWLEDGE_BACKEND in {"seed", "postgres"}
