"""Configurable web-search adapter for external research evidence."""
from __future__ import annotations

import json
from urllib import request


class WebSearchClient:
    """Call a deployment-provided JSON search endpoint and return Evidence records."""

    def __init__(self, base_url: str, api_key: str = "", timeout: float = 8.0) -> None:
        """Bind the client to an externally configured search service."""
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout

    def search(self, query: str, limit: int = 6) -> list[dict]:
        """Query the provider and map its generic result list to citations."""
        if not query.strip() or limit < 1:
            return []
        payload = json.dumps({"query": query, "limit": limit}).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        http_request = request.Request(self.base_url, data=payload, headers=headers, method="POST")
        with request.urlopen(http_request, timeout=self.timeout) as response:
            body = json.load(response)
        return [_map_result(item, index) for index, item in enumerate(body.get("results", []))]


def _map_result(item: dict, index: int) -> dict:
    """Convert a web result into a citable external evidence envelope."""
    return {
        "evidence_id": item.get("evidence_id") or item.get("url") or f"web:{index}",
        "type": item.get("type", "WEB"),
        "source_id": item.get("source_id") or item.get("url") or f"web:{index}",
        "title": item.get("title", ""),
        "content": item.get("content") or item.get("snippet", ""),
        "organization": item.get("organization"),
        "source_url": item.get("url"),
        "relevance": float(item.get("relevance", item.get("score", 0.0)) or 0.0),
        "metadata": item.get("metadata", {}),
    }
