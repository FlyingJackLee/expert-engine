"""Unit contracts for the optional dataset administration console."""
from pathlib import Path

from scripts.gradio_admin import benchmark_summary, browse_knowledge, export_validation_report, inspect_dataset


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


def test_benchmark_summary_exposes_quality_metrics(monkeypatch):
    """The Admin benchmark tab surfaces aggregate quality metrics only."""
    monkeypatch.setattr("evaluation.run_benchmark.run", lambda: {"total": 2, "passed": 1, "failed": 1, "historical_knowledge_coverage": 0.5})
    summary = benchmark_summary()
    assert '"failed": 1' in summary


def test_browse_knowledge_returns_safe_metadata(monkeypatch):
    """The Admin browser exposes metadata and citation fields, not chunk bodies."""
    monkeypatch.setattr("scripts.gradio_admin.PostgresKnowledgeRepository.browse", lambda *_args: [{"document_id": "d1", "source_type": "POLICY", "title": "政策", "organization": "机构", "source_url": "https://example.test", "metadata": {}, "chunks": 1, "embedded_chunks": 1}])
    result = browse_knowledge("POLICY")
    assert '"document_id": "d1"' in result
    assert "content" not in result
