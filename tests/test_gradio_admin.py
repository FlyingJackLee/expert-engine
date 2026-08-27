"""Unit contracts for the optional dataset administration console."""
from pathlib import Path

from scripts.gradio_admin import export_validation_report, inspect_dataset


def test_inspect_dataset_requires_all_uploads():
    """The UI reports a clear instruction before attempting import."""
    assert "请先上传" in inspect_dataset([])


def test_inspect_dataset_surfaces_schema_errors(tmp_path: Path):
    """Dataset validation remains the single gate used by the UI."""
    path = tmp_path / "events.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    assert "校验失败" in inspect_dataset([str(path)])


def test_export_validation_report_is_machine_readable_for_invalid_upload(tmp_path: Path):
    """Failed validation is exportable without attempting a database write."""
    path = tmp_path / "events.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    report = export_validation_report([str(path)])
    assert '"status": "INVALID"' in report


def test_inspect_dataset_rejects_unknown_profile(tmp_path: Path):
    """Admin metadata must reference a discovered expert profile."""
    paths = []
    for name in ("source_manifest.jsonl", "events.jsonl", "organization_cards.jsonl", "capability_cards.jsonl", "case_cards.jsonl"):
        path = tmp_path / name
        path.write_text("", encoding="utf-8")
        paths.append(str(path))
    assert "未知 expert profile" in inspect_dataset(paths, expert_profile_id="missing")
