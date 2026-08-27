import pytest

from app.experts import ExpertNotFoundError, list_profiles, load_runtime, resolve_expert_id


def test_default_expert_is_discovered_from_profile_not_graph_code():
    expert_id = resolve_expert_id("AUTO")
    profile = list_profiles()[expert_id]
    runtime = load_runtime(profile)
    assert profile["is_default"] is True
    assert runtime.default_topic


def test_unknown_expert_is_rejected_by_registry():
    with pytest.raises(ExpertNotFoundError, match="Unknown expert_id"):
        resolve_expert_id("does_not_exist")
