from app.config import HITL_CHECKPOINT_BACKEND, KNOWLEDGE_BACKEND


def test_configuration_has_a_safe_default_backend():
    """A missing .env must not stop a fresh checkout from starting."""
    assert KNOWLEDGE_BACKEND in {"seed", "postgres"}
    assert HITL_CHECKPOINT_BACKEND in {"memory", "postgres"}
