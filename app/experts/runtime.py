"""Stable interface between the generic graph and an industry expert package."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExpertRuntime:
    """Runtime assets that make one declarative expert profile executable."""
    event_analyzer_prompt: str
    research_planner_prompt: str
    opportunity_synthesis_prompt: str
    evidence_critic_prompt: str
    need_reasoning_prompt: str
    knowledge_extraction_prompt: str
    topic_keywords: dict[str, tuple[str, ...]]
    default_topic: str
