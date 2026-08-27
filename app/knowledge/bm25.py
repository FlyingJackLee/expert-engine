"""OpenSearch BM25 adapter with a provider-neutral evidence contract."""
from __future__ import annotations

import json
from urllib import request


class OpenSearchBM25:
    """Query an OpenSearch-compatible `_search` endpoint without embedding business fields."""

    def __init__(self, base_url: str, index: str, api_key: str = "", timeout: float = 8.0) -> None:
        """Bind the adapter to deployment-provided endpoint settings."""
        self.base_url = base_url.rstrip("/")
        self.index = index
        self.api_key = api_key
        self.timeout = timeout

    def search(self, query: str, limit: int = 6) -> list[dict]:
        """Return OpenSearch hits mapped to the engine's evidence envelope."""
        if not query.strip() or limit < 1:
            return []
        payload = json.dumps({"size": limit, "query": {"match": {"content": {"query": query}}}}).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"
        http_request = request.Request(f"{self.base_url}/{self.index}/_search", data=payload, headers=headers, method="POST")
        with request.urlopen(http_request, timeout=self.timeout) as response:
            body = json.load(response)
        results = [_map_hit(hit) for hit in body.get("hits", {}).get("hits", [])]
        peak = max((item["relevance"] for item in results), default=0.0)
        if peak:
            for item in results:
                item["relevance"] = round(item["relevance"] / peak, 4)
        return results


def _map_hit(hit: dict) -> dict:
    """Map an OpenSearch hit while preserving source metadata for citation."""
    source = hit.get("_source", {})
    return {
        "evidence_id": source.get("evidence_id") or hit.get("_id"),
        "type": source.get("type", "UNKNOWN"),
        "source_id": source.get("source_id") or hit.get("_index"),
        "title": source.get("title", ""),
        "content": source.get("content", ""),
        "organization": source.get("organization"),
        "source_url": source.get("source_url"),
        "relevance": float(hit.get("_score") or 0.0),
        "metadata": source.get("metadata", {}),
    }
