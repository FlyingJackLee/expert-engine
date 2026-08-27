"""Small, dependency-free observability helpers for local development.

Logs deliberately contain identifiers and summaries only. Event content, user
context, credentials and full evidence bodies must not be emitted here.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any
from threading import Lock

_GRAPH_EVENTS: dict[str, list[dict[str, Any]]] = {}
_EVENT_LOCK = Lock()


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
        record_graph_event(run_id, "NODE_STARTED", name)
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
            record_graph_event(run_id, "NODE_FAILED", name, error="node execution failed", duration_ms=round((time.perf_counter() - started) * 1000))
            raise
        logger.debug(
            "graph_node_completed run_id=%s node=%s duration_ms=%d output_keys=%s",
            result.get("run_id", run_id),
            name,
            (time.perf_counter() - started) * 1000,
            sorted(result.keys()),
        )
        record_graph_event(result.get("run_id", run_id), "NODE_COMPLETED", name, duration_ms=round((time.perf_counter() - started) * 1000), output_keys=sorted(result.keys()))
        return result

    return wrapped


def record_graph_event(run_id: str, event_type: str, node: str, **details: Any) -> None:
    """Record a safe, process-local graph event for live status consumers."""
    event = {"run_id": run_id, "event_type": event_type, "node": node, "timestamp": time.time(), **details}
    with _EVENT_LOCK:
        _GRAPH_EVENTS.setdefault(run_id, []).append(event)


def get_graph_events(run_id: str) -> list[dict[str, Any]]:
    """Return a snapshot of graph events without exposing input or evidence bodies."""
    with _EVENT_LOCK:
        return list(_GRAPH_EVENTS.get(run_id, []))
