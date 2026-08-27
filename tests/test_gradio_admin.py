"""Unit contracts for the optional dataset administration console."""
from pathlib import Path

from scripts.gradio_admin import inspect_dataset


def test_inspect_dataset_requires_all_uploads():
    """The UI reports a clear instruction before attempting import."""
    assert "请先上传" in inspect_dataset([])


def test_inspect_dataset_surfaces_schema_errors(tmp_path: Path):
    """Dataset validation remains the single gate used by the UI."""
    path = tmp_path / "events.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    assert "校验失败" in inspect_dataset([str(path)])
