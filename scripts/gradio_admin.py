"""Minimal Gradio console for validating and importing city JSONL datasets."""
from __future__ import annotations

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
        with gr.Row():
            gr.Button("校验", variant="secondary").click(inspect_dataset, files, output)
            gr.Button("导入 PostgreSQL", variant="primary").click(import_dataset, files, output)
    return demo


if __name__ == "__main__":
    build_demo().launch()
