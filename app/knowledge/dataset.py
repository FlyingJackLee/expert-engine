"""Validation and conversion for the documented city JSONL dataset format."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.schemas.domain import EvidenceType, KnowledgeDocumentInput


REQUIRED_FILES = {
    "source_manifest.jsonl",
    "events.jsonl",
    "organization_cards.jsonl",
    "capability_cards.jsonl",
    "case_cards.jsonl",
}
SOURCE_TYPE_MAP = {
    "POLICY": EvidenceType.POLICY,
    "RESPONSIBILITY": EvidenceType.RESPONSIBILITY,
    "COMPANY": EvidenceType.CAPABILITY,
    "NEWS": EvidenceType.INDUSTRY,
    "INDUSTRY": EvidenceType.INDUSTRY,
    "CASE": EvidenceType.CASE,
    "CAPABILITY": EvidenceType.CAPABILITY,
    "INTERNAL": EvidenceType.INTERNAL,
}


class DatasetValidationError(ValueError):
    """Raised when a dataset cannot be safely imported."""


@dataclass(frozen=True)
class DatasetImport:
    """Validated documents and draft-skipping information from one city dataset."""
    documents: list[KnowledgeDocumentInput]
    skipped_drafts: int


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read strict UTF-8 JSONL objects and annotate parse failures by line."""
    if not path.is_file():
        raise DatasetValidationError(f"Missing required dataset file: {path.name}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetValidationError(f"{path.name}:{line_number} is not valid JSON: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise DatasetValidationError(f"{path.name}:{line_number} must contain a JSON object")
        rows.append(value)
    return rows


def _required(row: dict[str, Any], field: str, filename: str) -> Any:
    """Return a mandatory field or raise a source-specific validation error."""
    value = row.get(field)
    if value in (None, "", []):
        raise DatasetValidationError(f"{filename} has a row without {field}")
    return value


def load_dataset(dataset_dir: str | Path, *, include_draft: bool = False) -> DatasetImport:
    """Turn city collection JSONL records into evidence documents.

    A source can underpin several semantic record types (for example a published
    customer story supports both a capability and a case).  Each imported record
    is therefore a distinct knowledge document while retaining the source ID in
    metadata for traceability.
    """
    directory = Path(dataset_dir)
    if not directory.is_dir():
        raise DatasetValidationError(f"Dataset directory does not exist: {directory}")
    missing = sorted(name for name in REQUIRED_FILES if not (directory / name).is_file())
    if missing:
        raise DatasetValidationError(f"Missing required dataset file(s): {', '.join(missing)}")

    rows = {name: _read_jsonl(directory / name) for name in REQUIRED_FILES}
    cities = {event.get("city") for event in rows["events.jsonl"] if event.get("city")}
    dataset_city = next(iter(cities)) if len(cities) == 1 else None
    manifests: dict[str, dict[str, Any]] = {}
    for source in rows["source_manifest.jsonl"]:
        source_id = _required(source, "source_id", "source_manifest.jsonl")
        if source_id in manifests:
            raise DatasetValidationError(f"source_manifest.jsonl has duplicate source_id: {source_id}")
        manifests[source_id] = source

    documents: list[KnowledgeDocumentInput] = []
    skipped_drafts = 0

    def allowed(row: dict[str, Any]) -> bool:
        """Keep only verified records unless an explicit local override is set."""
        nonlocal skipped_drafts
        if include_draft or row.get("status") == "VERIFIED":
            return True
        skipped_drafts += 1
        return False

    def source_for(source_id: str, filename: str) -> dict[str, Any]:
        """Resolve a card reference to its manifest source or report the defect."""
        try:
            return manifests[source_id]
        except KeyError as exc:
            raise DatasetValidationError(f"{filename} references unknown source_id: {source_id}") from exc

    def add_document(document_id: str, source: dict[str, Any], evidence_type: EvidenceType, title: str, chunk: str, metadata: dict[str, Any]) -> None:
        """Create one traceable knowledge document after local field validation."""
        _required(source, "source_id", "source_manifest.jsonl")
        if not title:
            raise DatasetValidationError("dataset has a record without title")
        if not chunk:
            raise DatasetValidationError("dataset has a record without content")
        documents.append(KnowledgeDocumentInput(
            document_id=document_id,
            source_type=evidence_type,
            title=title,
            chunks=[chunk],
            source_url=source.get("source_url"),
            organization=source.get("publishing_organization"),
            reliability=1.0 if source.get("source_type") in {"POLICY", "RESPONSIBILITY"} else 0.8,
            effective_date=source.get("effective_date"),
            metadata={"source_id": source["source_id"], "source_title": source.get("title"), **metadata},
        ))

    for event in rows["events.jsonl"]:
        if not allowed(event):
            continue
        event_id = _required(event, "event_id", "events.jsonl")
        source = source_for(_required(event, "source_id", "events.jsonl"), "events.jsonl")
        source_type = SOURCE_TYPE_MAP.get(source.get("source_type"), EvidenceType.INDUSTRY)
        add_document(event_id, source, source_type, _required(event, "title", "events.jsonl"), _required(event, "content", "events.jsonl"), {"record_type": "event", "topics": event.get("topics", []), "city": event.get("city")})

    for card in rows["organization_cards.jsonl"]:
        if not allowed(card):
            continue
        card_id = _required(card, "department_id", "organization_cards.jsonl") if card.get("department_id") else _required(card, "organization_id", "organization_cards.jsonl")
        for source_id in _required(card, "evidence_ids", "organization_cards.jsonl"):
            source = source_for(source_id, "organization_cards.jsonl")
            subject = card.get("department_name") or _required(card, "organization_name", "organization_cards.jsonl")
            add_document(f"responsibility:{card_id}:{source_id}", source, EvidenceType.RESPONSIBILITY, subject, "；".join(card.get("responsibilities", [])), {"record_type": "organization_card", "organization_id": card.get("organization_id"), "organization_name": card.get("organization_name"), "department_id": card.get("department_id"), "department_name": card.get("department_name"), "city": dataset_city})

    for card in rows["capability_cards.jsonl"]:
        if not allowed(card):
            continue
        card_id = _required(card, "capability_id", "capability_cards.jsonl")
        for source_id in _required(card, "evidence_ids", "capability_cards.jsonl"):
            source = source_for(source_id, "capability_cards.jsonl")
            add_document(f"capability:{card_id}:{source_id}", source, EvidenceType.CAPABILITY, _required(card, "name", "capability_cards.jsonl"), _required(card, "description", "capability_cards.jsonl"), {"record_type": "capability_card", "capability_id": card_id, "topics": card.get("applicable_topics", [])})

    for card in rows["case_cards.jsonl"]:
        if not allowed(card):
            continue
        card_id = _required(card, "case_id", "case_cards.jsonl")
        for source_id in _required(card, "evidence_ids", "case_cards.jsonl"):
            source = source_for(source_id, "case_cards.jsonl")
            add_document(f"case:{card_id}:{source_id}", source, EvidenceType.CASE, _required(card, "name", "case_cards.jsonl"), "；".join(_required(card, "outcomes", "case_cards.jsonl")), {"record_type": "case_card", "case_id": card_id, "topics": card.get("topics", []), "city": card.get("city"), "delivered_capabilities": card.get("delivered_capabilities", [])})

    duplicate_ids = [item for item, count in Counter(document.document_id for document in documents).items() if count > 1]
    if duplicate_ids:
        raise DatasetValidationError(f"Dataset produces duplicate document IDs: {', '.join(sorted(duplicate_ids))}")
    return DatasetImport(documents=documents, skipped_drafts=skipped_drafts)
