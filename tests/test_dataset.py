import json
from pathlib import Path

import pytest

from app.knowledge.dataset import DatasetValidationError, load_dataset


DATASET_DIR = Path("docs/data-collection/chongqing")


def test_draft_dataset_is_valid_but_not_imported_by_default():
    dataset = load_dataset(DATASET_DIR)
    importable_files = ("events.jsonl", "organization_cards.jsonl", "capability_cards.jsonl", "case_cards.jsonl")
    expected_drafts = sum(
        1
        for filename in importable_files
        for line in (DATASET_DIR / filename).read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("status") != "VERIFIED"
    )
    assert dataset.skipped_drafts == expected_drafts
    assert all(document.metadata["record_type"] in {"event", "organization_card", "capability_card", "case_card"} for document in dataset.documents)


def test_draft_dataset_can_be_converted_for_local_integration():
    dataset = load_dataset(DATASET_DIR, include_draft=True)
    documents = {document.document_id: document for document in dataset.documents}
    assert "evt_cq_001" in documents
    assert documents["evt_cq_001"].metadata["source_id"] == "src_cq_2025_005"
    assert "case:case_tianjin_smart_gas:src_company_002" in documents
    assert documents["case:case_tianjin_smart_gas:src_company_002"].source_type == "CASE"


def test_unknown_evidence_source_is_rejected(tmp_path: Path):
    for name in ("source_manifest.jsonl", "events.jsonl", "organization_cards.jsonl", "capability_cards.jsonl", "case_cards.jsonl"):
        (tmp_path / name).write_text((DATASET_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "events.jsonl").write_text('{"event_id":"evt","title":"测试事件","content":"足够长度的测试内容","source_id":"missing","status":"VERIFIED"}\n', encoding="utf-8")
    with pytest.raises(DatasetValidationError, match="unknown source_id"):
        load_dataset(tmp_path, include_draft=True)
