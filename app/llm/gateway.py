"""Single boundary for model calls and schema validation.

Nodes must call this module instead of a provider SDK directly so model selection,
prompt versions, observability and retry policy can evolve independently.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import TypeVar

from openai import BadRequestError, OpenAI
from pydantic import BaseModel

from app.config import (LLM_API_KEY, LLM_BASE_URL, LLM_ENABLED, LLM_EVENT_MODEL,
                        LLM_NEED_MODEL, LLM_RESEARCH_MODEL, LLM_REVIEW_MODEL,
                        LLM_SYNTHESIS_MODEL, LLM_KNOWLEDGE_MODEL,
                        LLM_CANDIDATE_MODEL, EMBEDDING_ENABLED,
                        EMBEDDING_MODEL)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


@dataclass(frozen=True)
class ModelProfile:
    """Versioned model routing key for one reasoning responsibility."""

    name: str
    model: str
    base_url: str = ""
    api_key: str = ""
    temperature: float = 0.0


MODEL_PROFILES = {
    "event_analyzer": ModelProfile("event_analyzer", LLM_EVENT_MODEL),
    "research_planner": ModelProfile("research_planner", LLM_RESEARCH_MODEL),
    "opportunity_synthesis": ModelProfile("opportunity_synthesis", LLM_SYNTHESIS_MODEL),
    "evidence_critic": ModelProfile("evidence_critic", LLM_REVIEW_MODEL),
    "need_reasoning": ModelProfile("need_reasoning", LLM_NEED_MODEL),
    "candidate_reasoning": ModelProfile("candidate_reasoning", LLM_CANDIDATE_MODEL),
    "knowledge_extraction": ModelProfile("knowledge_extraction", LLM_KNOWLEDGE_MODEL),
    "embedding": ModelProfile("embedding", EMBEDDING_MODEL),
}


def resolve_model_profile(profile_name: str) -> ModelProfile:
    """Resolve a profile-specific endpoint override with global defaults as fallback."""
    profile = MODEL_PROFILES[profile_name]
    prefix = f"LLM_{profile_name.upper()}"
    return ModelProfile(
        name=profile.name,
        model=os.getenv(f"{prefix}_MODEL", profile.model),
        base_url=os.getenv(f"{prefix}_BASE_URL", profile.base_url or LLM_BASE_URL),
        api_key=os.getenv(f"{prefix}_API_KEY", profile.api_key or LLM_API_KEY),
        temperature=profile.temperature,
    )


class LLMGateway:
    """Provider-neutral boundary for schema-constrained model generation."""

    def resolve_model_profile(self, profile_name: str) -> ModelProfile:
        """Expose resolved endpoint settings to persistence integrations safely."""
        return resolve_model_profile(profile_name)

    def enabled_for(self, profile_name: str) -> bool:
        """Only enable a node when global opt-in and a node-specific model exist."""
        profile = resolve_model_profile(profile_name)
        return LLM_ENABLED and bool(profile.api_key) and bool(profile.model)

    def structured_generate(self, profile_name: str, system_prompt: str, user_prompt: str, schema: type[SchemaT]) -> SchemaT | None:
        """Return validated structured output, or ``None`` when this node is disabled.

        Provider failures deliberately propagate. Nodes may decide to fall back only
        where a deterministic fallback is safe; silently fabricating a response is
        never a gateway responsibility.
        """
        if not self.enabled_for(profile_name):
            return None
        profile = resolve_model_profile(profile_name)
        client = OpenAI(api_key=profile.api_key, base_url=profile.base_url)
        # Some compatible gateways advertise neither JSON Schema nor JSON Object.
        # Supplying the contract in-band makes the final prompt-only fallback useful
        # while local Pydantic validation remains the authoritative guardrail.
        schema_instruction = (
            "返回结果必须严格符合以下 JSON Schema；字段名、嵌套结构和数值类型不可改变：\n"
            f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": schema_instruction},
            {"role": "user", "content": user_prompt},
        ]
        request = {"model": profile.model, "temperature": profile.temperature, "messages": messages}
        response = self._create_with_structured_output_fallback(client, request, schema)
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError(f"{profile_name} returned an empty structured response")
        return schema.model_validate_json(self._strip_markdown_fence(content))

    def embed_texts(self, texts: list[str]) -> list[list[float]] | None:
        """Generate optional embeddings through the same provider boundary as LLM calls."""
        profile = resolve_model_profile("embedding")
        if not (EMBEDDING_ENABLED and profile.api_key and profile.model):
            return None
        client = OpenAI(api_key=profile.api_key, base_url=profile.base_url)
        response = client.embeddings.create(model=profile.model, input=texts)
        return [list(item.embedding) for item in sorted(response.data, key=lambda item: item.index)]

    @staticmethod
    def _create_with_structured_output_fallback(client: OpenAI, request: dict, schema: type[SchemaT]):
        """Use the strongest structured-output feature supported by the gateway.

        OpenAI-compatible gateways differ substantially: some reject JSON Schema,
        and some reject every ``response_format`` value. The final fallback still
        demands JSON in the prompt and always performs local Pydantic validation.
        """
        try:
            return client.chat.completions.create(
                **request,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": schema.__name__, "strict": True, "schema": schema.model_json_schema()},
                },
            )
        except BadRequestError as error:
            if "response_format" not in str(error).lower():
                raise

        try:
            return client.chat.completions.create(**request, response_format={"type": "json_object"})
        except BadRequestError as error:
            if "response_format" not in str(error).lower():
                raise

        # The user message carries the source content; the additional system rule
        # makes no-format gateways return a parseable object rather than prose.
        fallback_request = dict(request)
        fallback_request["messages"] = [
            *request["messages"],
            {"role": "system", "content": "最终只能输出一个合法 JSON 对象，不要使用 Markdown 或解释文字。"},
        ]
        return client.chat.completions.create(**fallback_request)

    @staticmethod
    def _strip_markdown_fence(content: str) -> str:
        """Accept a common provider deviation while retaining strict JSON validation."""
        stripped = content.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            return stripped.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return stripped


gateway = LLMGateway()
