"""Test-wide safety configuration applied before application modules are imported."""
import os

# Unit and regression tests must never spend tokens or depend on a developer's
# local .env credentials. Live model checks are an explicit manual operation.
os.environ["LLM_ENABLED"] = "false"
# Regression tests must also remain independent from a developer's local
# PostgreSQL data, which may contain incomplete or experimental city records.
os.environ["KNOWLEDGE_BACKEND"] = "seed"
os.environ["RUN_BACKEND"] = "memory"
