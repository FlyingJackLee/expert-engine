"""Configurable LangGraph checkpointer construction and schema setup."""
from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import DATABASE_URL, HITL_CHECKPOINT_BACKEND


def build_hitl_checkpointer() -> Any:
    """Return the configured checkpointer for resumable human-review workflows."""
    if HITL_CHECKPOINT_BACKEND == "memory":
        from langgraph.checkpoint.memory import InMemorySaver

        return InMemorySaver()
    if HITL_CHECKPOINT_BACKEND == "postgres":
        from langgraph.checkpoint.postgres import PostgresSaver

        # The saver owns this process-lifetime connection. Autocommit and disabled
        # prepared statements follow the upstream PostgresSaver connection helper.
        connection = psycopg.connect(
            DATABASE_URL,
            autocommit=True,
            prepare_threshold=0,
            row_factory=dict_row,
        )
        return PostgresSaver(connection)
    raise ValueError(f"Unsupported HITL_CHECKPOINT_BACKEND: {HITL_CHECKPOINT_BACKEND}")


def setup_hitl_checkpoint_tables() -> None:
    """Create or upgrade official LangGraph PostgreSQL checkpoint tables."""
    if HITL_CHECKPOINT_BACKEND != "postgres":
        return
    from langgraph.checkpoint.postgres import PostgresSaver

    with PostgresSaver.from_conn_string(DATABASE_URL) as saver:
        saver.setup()
