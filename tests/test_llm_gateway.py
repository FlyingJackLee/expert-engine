import importlib

from app.llm.gateway import MODEL_PROFILES, gateway, resolve_model_profile
from app.schemas.domain import (EventAnalysis, NeedInference, Opportunity,
                                ResearchPlan, ReviewResult)


def test_unconfigured_gateway_returns_none_without_network_call(monkeypatch):
    """A fresh checkout must not need API credentials to run its regression suite."""
    gateway_module = importlib.import_module("app.llm.gateway")
    monkeypatch.setattr(gateway_module, "LLM_ENABLED", False)
    assert gateway.enabled_for("event_analyzer") is False
    assert gateway.structured_generate("event_analyzer", "system", "user", EventAnalysis) is None
    assert gateway.structured_generate("research_planner", "system", "user", ResearchPlan) is None
    assert gateway.structured_generate("opportunity_synthesis", "system", "user", Opportunity) is None
    assert gateway.structured_generate("evidence_critic", "system", "user", ReviewResult) is None
    assert gateway.structured_generate("need_reasoning", "system", "user", NeedInference) is None
    assert MODEL_PROFILES["event_analyzer"].temperature == 0.0


def test_profile_endpoint_overrides_fall_back_field_by_field(monkeypatch):
    """One responsibility can use a custom URL/key while inheriting its model default."""
    gateway_module = importlib.import_module("app.llm.gateway")
    monkeypatch.setenv("LLM_EVENT_ANALYZER_BASE_URL", "https://event.example/v1")
    monkeypatch.setenv("LLM_EVENT_ANALYZER_API_KEY", "event-secret")
    monkeypatch.setenv("LLM_EVENT_ANALYZER_MODEL", "event-model")
    profile = resolve_model_profile("event_analyzer")
    assert profile.base_url == "https://event.example/v1"
    assert profile.api_key == "event-secret"
    assert profile.model == "event-model"
    monkeypatch.delenv("LLM_EVENT_ANALYZER_API_KEY")
    fallback = gateway_module.resolve_model_profile("event_analyzer")
    assert fallback.base_url == "https://event.example/v1"


def test_unconfigured_embedding_returns_none_without_network_call(monkeypatch):
    """Embedding retrieval remains optional until a model and explicit opt-in exist."""
    gateway_module = importlib.import_module("app.llm.gateway")
    monkeypatch.setattr(gateway_module, "EMBEDDING_ENABLED", False)
    assert gateway.embed_texts(["测试文本"]) is None


def test_embedding_gateway_aligns_provider_results_to_input_order(monkeypatch):
    """Chunk vectors must be restored to input order before database persistence."""
    gateway_module = importlib.import_module("app.llm.gateway")

    class FakeEmbeddings:
        def create(self, **kwargs):
            return type("Response", (), {"data": [type("Item", (), {"index": 1, "embedding": [0.2]})(), type("Item", (), {"index": 0, "embedding": [0.1]})()]})()

    class FakeClient:
        embeddings = FakeEmbeddings()

    monkeypatch.setattr(gateway_module, "EMBEDDING_ENABLED", True)
    monkeypatch.setattr(gateway_module, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(gateway_module, "EMBEDDING_MODEL", "test-embedding")
    monkeypatch.setitem(gateway_module.MODEL_PROFILES, "embedding", gateway_module.ModelProfile("embedding", "test-embedding"))
    monkeypatch.setattr(gateway_module, "OpenAI", lambda **kwargs: FakeClient())
    assert gateway.embed_texts(["first", "second"]) == [[0.1], [0.2]]


def test_gateway_accepts_json_wrapped_in_a_markdown_fence():
    content = '```json\n{"event_type":"POLICY","topics":["城市生命线"],"tasks":[],"signals":{"policy_strength":0.8,"project_signal":0.4,"budget_signal":0.1,"procurement_signal":0.0}}\n```'
    result = EventAnalysis.model_validate_json(gateway._strip_markdown_fence(content))
    assert result.topics == ["城市生命线"]
