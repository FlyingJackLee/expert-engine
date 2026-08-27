import os
from pathlib import Path

from dotenv import load_dotenv

# Load the repository-local file once, before reading configuration. Existing
# process environment variables take precedence, which keeps deployment secrets
# controlled by the platform rather than by a checked-out file.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Keep a local-development default; production must inject this through its secret store.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://expert_engine:expert_engine@127.0.0.1:5433/expert_engine",
)
# Seed remains the safe default so a new checkout can run without infrastructure.
KNOWLEDGE_BACKEND = os.getenv("KNOWLEDGE_BACKEND", "seed").lower()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
# A bounded retry keeps a missing evidence source from creating an unbounded
# graph loop. Deployments may increase it after observing retrieval quality.
MAX_RESEARCH_RETRIES = int(os.getenv("MAX_RESEARCH_RETRIES", "1"))
# Analysis results must survive API process restarts in deployed environments.
RUN_BACKEND = os.getenv("RUN_BACKEND", "postgres").lower()
# HITL state must survive a web-process restart in deployed environments.
HITL_CHECKPOINT_BACKEND = os.getenv("HITL_CHECKPOINT_BACKEND", "postgres").lower()
# Generic ranking inputs; these values apply to evidence quality, never to a
# city, organization, product, or other business fact.
MATCHING_WEIGHTS = {"relevance": 0.5, "reliability": 0.3, "context": 0.2}

# Models remain opt-in: business users can validate deterministic behavior without
# requiring credentials or accidentally sending data to an external provider.
LLM_ENABLED = os.getenv("LLM_ENABLED", "false").lower() == "true"
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_EVENT_MODEL = os.getenv("LLM_EVENT_MODEL", "")
LLM_RESEARCH_MODEL = os.getenv("LLM_RESEARCH_MODEL", "")
LLM_SYNTHESIS_MODEL = os.getenv("LLM_SYNTHESIS_MODEL", "")
LLM_REVIEW_MODEL = os.getenv("LLM_REVIEW_MODEL", "")
LLM_NEED_MODEL = os.getenv("LLM_NEED_MODEL", "")
LLM_KNOWLEDGE_MODEL = os.getenv("LLM_KNOWLEDGE_MODEL", "")
# Published expert knowledge remains lower-confidence than primary source material.
PUBLISHED_KNOWLEDGE_RELIABILITY = float(os.getenv("PUBLISHED_KNOWLEDGE_RELIABILITY", "0.8"))
