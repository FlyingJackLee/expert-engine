"""Small, dependency-free observability helpers for local development.

Logs deliberately contain identifiers and summaries only. Event content, user
context, credentials and full evidence bodies must not be emitted here.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any


def configure_logging(level: str) -> None:
    """Configure concise key-value logs once at application startup."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def graph_node(name: str, node: Callable[[dict[str, Any]], dict[str, Any]]) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Emit safe start/end/failure summaries around a LangGraph node."""
    logger = logging.getLogger("app.graph")

    def wrapped(state: dict[str, Any]) -> dict[str, Any]:
        """Run one graph node while recording safe timing and outcome metadata."""
        run_id = state.get("run_id", "pending")
        started = time.perf_counter()
        logger.debug("graph_node_started run_id=%s node=%s", run_id, name)
        try:
            result = node(state)
        except Exception:
            logger.exception(
                "graph_node_failed run_id=%s node=%s duration_ms=%d",
                run_id,
                name,
                (time.perf_counter() - started) * 1000,
            )
            raise
        logger.debug(
            "graph_node_completed run_id=%s node=%s duration_ms=%d output_keys=%s",
            result.get("run_id", run_id),
            name,
            (time.perf_counter() - started) * 1000,
            sorted(result.keys()),
        )
        return result

    return wrapped
