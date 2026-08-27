"""Minimal Gradio console for validating and importing city JSONL datasets."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from app.knowledge.dataset import DatasetValidationError, load_dataset
from app.knowledge.postgres import PostgresKnowledgeRepository


def inspect_dataset(files: list[str] | None) -> str:
    """Validate uploaded dataset files and return an operator-friendly summary."""
    if not files:
        return "请先上传 source_manifest.jsonl、events.jsonl、organization_cards.jsonl、capability_cards.jsonl、case_cards.jsonl。"
    with tempfile.TemporaryDirectory(prefix="expert-dataset-") as directory:
        _copy_files(files, Path(directory))
        try:
            result = load_dataset(directory)
        except DatasetValidationError as exc:
            return f"校验失败：{exc}"
        return f"校验通过：{len(result.documents)} 条 VERIFIED 文档，跳过 {result.skipped_drafts} 条草稿。"


def import_dataset(files: list[str] | None) -> str:
    """Validate first, then atomically ingest verified documents into PostgreSQL."""
    if not files:
        return "请先上传数据集文件。"
    with tempfile.TemporaryDirectory(prefix="expert-dataset-") as directory:
        _copy_files(files, Path(directory))
        try:
            result = load_dataset(directory)
            repository = PostgresKnowledgeRepository()
            for document in result.documents:
                repository.ingest(document.model_dump())
        except DatasetValidationError as exc:
            return f"导入中止，校验失败：{exc}"
        return f"导入完成：{len(result.documents)} 条 VERIFIED 文档，跳过 {result.skipped_drafts} 条草稿。"


def export_verified_dataset(files: list[str] | None) -> str | None:
    """Export validated documents as normalized JSONL for downstream review."""
    if not files:
        return None
    with tempfile.TemporaryDirectory(prefix="expert-dataset-") as directory:
        _copy_files(files, Path(directory))
        try:
            result = load_dataset(directory)
        except DatasetValidationError as exc:
            return _write_report({"status": "INVALID", "error": str(exc)})
        with tempfile.NamedTemporaryFile(prefix="expert-verified-", suffix=".jsonl", delete=False) as handle:
            output = Path(handle.name)
        output.write_text("".join(json.dumps(document.model_dump(), ensure_ascii=False, default=str) + "\n" for document in result.documents), encoding="utf-8")
        return str(output)


def export_validation_report(files: list[str] | None) -> str:
    """Return a JSON report that can be copied or saved when validation fails."""
    if not files:
        return json.dumps({"status": "INVALID", "error": "未上传文件"}, ensure_ascii=False)
    with tempfile.TemporaryDirectory(prefix="expert-dataset-") as directory:
        _copy_files(files, Path(directory))
        try:
            result = load_dataset(directory)
        except DatasetValidationError as exc:
            return json.dumps({"status": "INVALID", "error": str(exc)}, ensure_ascii=False)
        return json.dumps({"status": "VALID", "verified_documents": len(result.documents), "skipped_drafts": result.skipped_drafts}, ensure_ascii=False)


def _write_report(report: dict) -> str:
    """Persist a small JSON report and return its downloadable path."""
    with tempfile.NamedTemporaryFile(prefix="expert-validation-", suffix=".json", delete=False) as handle:
        output = Path(handle.name)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(output)


def _copy_files(files: list[str], directory: Path) -> None:
    """Copy only uploaded files by basename so the validator controls the schema."""
    for file_path in files:
        source = Path(file_path)
        shutil.copy2(source, directory / source.name)


def build_demo():
    """Build the optional Gradio UI without making Gradio a core runtime dependency."""
    try:
        import gradio as gr
    except ImportError as exc:  # pragma: no cover - exercised in deployment environment
        raise RuntimeError("Install the optional admin dependency before starting Gradio: uv sync --extra admin") from exc
    with gr.Blocks(title="Expert Engine 数据集管理") as demo:
        gr.Markdown("## Expert Engine 数据集管理\n上传 JSONL 后先校验，再导入 VERIFIED 记录。")
        files = gr.File(file_count="multiple", file_types=[".jsonl"], type="filepath", label="JSONL 数据集")
        output = gr.Textbox(label="操作结果", lines=3)
        report = gr.Textbox(label="校验报告", lines=3)
        download = gr.File(label="导出文件")
        with gr.Row():
            gr.Button("校验", variant="secondary").click(inspect_dataset, files, output)
            gr.Button("导入 PostgreSQL", variant="primary").click(import_dataset, files, output)
            gr.Button("导出 VERIFIED JSONL").click(export_verified_dataset, files, download)
            gr.Button("查看校验报告").click(export_validation_report, files, report)
    return demo


if __name__ == "__main__":
    build_demo().launch()
