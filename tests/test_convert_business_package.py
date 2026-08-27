"""Unit contracts for business CSV to JSONL conversion."""
import json
from pathlib import Path

from scripts.convert_business_package import convert_package


def test_convert_example_package_to_validator_files(tmp_path: Path):
    """Business-friendly examples become the five technical ingestion files."""
    source = Path("docs/data-collection/example-package")
    counts = convert_package(source, tmp_path)
    assert counts["sources.jsonl"] == 3
    event = json.loads((tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert event["topics"] == ["城市生命线", "住建数据治理"]
    source_row = json.loads((tmp_path / "source_manifest.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert source_row["status"] == "DRAFT"
