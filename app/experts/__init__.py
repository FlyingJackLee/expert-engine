from importlib import import_module
from pathlib import Path
import json

from app.experts.runtime import ExpertRuntime


class ExpertNotFoundError(ValueError):
    """Raised when an API request cannot resolve an installed expert profile."""


def list_profiles() -> dict[str, dict]:
    """Discover declarative expert profiles instead of hard-coding expert IDs."""
    profiles = {}
    for profile_path in sorted((Path(__file__).parent / "profiles").glob("*.json")):
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        expert_id = profile.get("id")
        if not expert_id or profile_path.stem != expert_id:
            raise ValueError(f"Invalid expert profile: {profile_path}")
        if expert_id in profiles:
            raise ValueError(f"Duplicate expert profile: {expert_id}")
        profiles[expert_id] = profile
    return profiles


def load_profile(expert_id: str) -> dict:
    """Load one discovered profile or raise a registry-specific error."""
    try:
        return list_profiles()[expert_id]
    except KeyError as exc:
        raise ExpertNotFoundError(f"Unknown expert_id: {expert_id}") from exc


def resolve_expert_id(requested_id: str) -> str:
    """Resolve an explicit ID or the sole profile marked as default."""
    if requested_id != "AUTO":
        load_profile(requested_id)
        return requested_id
    defaults = [expert_id for expert_id, profile in list_profiles().items() if profile.get("is_default")]
    if len(defaults) != 1:
        raise ExpertNotFoundError("AUTO requires exactly one profile with is_default=true")
    return defaults[0]


def load_runtime(profile: dict) -> ExpertRuntime:
    """Load the runtime declared by a profile; the graph never imports an industry module."""
    try:
        module_name, attribute = profile["runtime"].split(":", 1)
        runtime = getattr(import_module(module_name), attribute)
    except (KeyError, ValueError, ImportError, AttributeError) as exc:
        raise ValueError(f"Invalid runtime declaration for expert {profile.get('id')}") from exc
    if not isinstance(runtime, ExpertRuntime):
        raise TypeError(f"Expert runtime for {profile.get('id')} must be an ExpertRuntime")
    return runtime
