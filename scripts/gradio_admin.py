"""Minimal Gradio console for validating and importing city JSONL datasets."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from app.knowledge.dataset import DatasetValidationError, load_dataset
from app.knowledge.postgres import PostgresKnowledgeRepository
from app.experts import list_profiles
from app.schemas.domain import EvidenceType


def inspect_dataset(files: list[str] | None, knowledge_domain: str = "ALL", expert_profile_id: str = "AUTO") -> str:
    """Validate uploaded dataset files and return an operator-friendly summary."""
    if not files:
        return "请先上传 source_manifest.jsonl、events.jsonl、organization_cards.jsonl、capability_cards.jsonl、case_cards.jsonl。"
    with tempfile.TemporaryDirectory(prefix="expert-dataset-") as directory:
        _copy_files(files, Path(directory))
        try:
            result = _scoped_import(load_dataset(directory), knowledge_domain, expert_profile_id)
        except DatasetValidationError as exc:
            return f"校验失败：{exc}"
        return f"校验通过：{len(result.documents)} 条 VERIFIED 文档，跳过 {result.skipped_drafts} 条草稿。"


def import_dataset(files: list[str] | None, knowledge_domain: str = "ALL", expert_profile_id: str = "AUTO") -> str:
    """Validate first, then atomically ingest verified documents into PostgreSQL."""
    if not files:
        return "请先上传数据集文件。"
    with tempfile.TemporaryDirectory(prefix="expert-dataset-") as directory:
        _copy_files(files, Path(directory))
        try:
            result = _scoped_import(load_dataset(directory), knowledge_domain, expert_profile_id)
            repository = PostgresKnowledgeRepository()
            for document in result.documents:
                payload = document.model_dump()
                payload["metadata"]["expert_profile_id"] = expert_profile_id
                repository.ingest(payload)
        except DatasetValidationError as exc:
            return f"导入中止，校验失败：{exc}"
        return f"导入完成：{len(result.documents)} 条 VERIFIED 文档，跳过 {result.skipped_drafts} 条草稿。"


def export_verified_dataset(files: list[str] | None, knowledge_domain: str = "ALL", expert_profile_id: str = "AUTO") -> str | None:
    """Export validated documents as normalized JSONL for downstream review."""
    if not files:
        return None
    with tempfile.TemporaryDirectory(prefix="expert-dataset-") as directory:
        _copy_files(files, Path(directory))
        try:
            result = _scoped_import(load_dataset(directory), knowledge_domain, expert_profile_id)
        except DatasetValidationError as exc:
            return _write_report({"status": "INVALID", "error": str(exc)})
        with tempfile.NamedTemporaryFile(prefix="expert-verified-", suffix=".jsonl", delete=False) as handle:
            output = Path(handle.name)
        output.write_text("".join(json.dumps(document.model_dump(), ensure_ascii=False, default=str) + "\n" for document in result.documents), encoding="utf-8")
        return str(output)


def export_validation_report(files: list[str] | None, knowledge_domain: str = "ALL", expert_profile_id: str = "AUTO") -> str:
    """Return a JSON report that can be copied or saved when validation fails."""
    if not files:
        return json.dumps({"status": "INVALID", "error": "未上传文件"}, ensure_ascii=False)
    with tempfile.TemporaryDirectory(prefix="expert-dataset-") as directory:
        _copy_files(files, Path(directory))
        try:
            result = _scoped_import(load_dataset(directory), knowledge_domain, expert_profile_id)
        except DatasetValidationError as exc:
            return json.dumps({"status": "INVALID", "error": str(exc)}, ensure_ascii=False)
        return json.dumps({"status": "VALID", "verified_documents": len(result.documents), "skipped_drafts": result.skipped_drafts}, ensure_ascii=False)


def _write_report(report: dict) -> str:
    """Persist a small JSON report and return its downloadable path."""
    with tempfile.NamedTemporaryFile(prefix="expert-validation-", suffix=".json", delete=False) as handle:
        output = Path(handle.name)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(output)


def knowledge_summary() -> str:
    """Show logical RAG domains and vector coverage without exposing document bodies."""
    try:
        rows = PostgresKnowledgeRepository().summary()
    except Exception as exc:  # pragma: no cover - infrastructure behavior belongs to deployment checks
        return f"知识库暂不可用：{exc}"
    if not rows:
        return "知识库暂无数据。"
    return "\n".join(f"{row['source_type']}: 文档 {row['documents']}，片段 {row['chunks']}，已有向量 {row['embedded_chunks']}" for row in rows)


def benchmark_summary() -> str:
    """Run the deterministic golden-sample benchmark and return its compact report."""
    from evaluation.run_benchmark import run

    report = run()
    return json.dumps({key: report[key] for key in ("total", "passed", "failed", "historical_knowledge_coverage")}, ensure_ascii=False, indent=2)


def _scoped_import(result, knowledge_domain: str, expert_profile_id: str):
    """Validate the selected knowledge domain and expert profile before operations."""
    if expert_profile_id != "AUTO" and expert_profile_id not in list_profiles():
        raise DatasetValidationError(f"未知 expert profile: {expert_profile_id}")
    if knowledge_domain != "ALL":
        try:
            expected = EvidenceType(knowledge_domain)
        except ValueError as exc:
            raise DatasetValidationError(f"未知 knowledge domain: {knowledge_domain}") from exc
        mismatched = [document.document_id for document in result.documents if document.source_type != expected]
        if mismatched:
            raise DatasetValidationError(f"上传数据包含不属于 {knowledge_domain} 的记录: {', '.join(mismatched[:5])}")
    return result


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
    with gr.Blocks(title="Expert Engine Admin") as demo:
        gr.Markdown("## Expert Engine Admin\n按数据流管理数据集、RAG 知识库和 Benchmark。")
        with gr.Tab("数据集导入"):
            files = gr.File(file_count="multiple", file_types=[".jsonl"], type="filepath", label="JSONL 数据集")
            domain = gr.Dropdown(["ALL", *[item.value for item in EvidenceType]], value="ALL", label="知识域")
            profile = gr.Dropdown(["AUTO", *sorted(list_profiles())], value="AUTO", label="适用专家 Profile")
            output = gr.Textbox(label="操作结果", lines=3)
            report = gr.Textbox(label="校验报告", lines=3)
            download = gr.File(label="导出文件")
            with gr.Row():
                gr.Button("校验", variant="secondary").click(inspect_dataset, [files, domain, profile], output)
                gr.Button("导入 PostgreSQL", variant="primary").click(import_dataset, [files, domain, profile], output)
                gr.Button("导出 VERIFIED JSONL").click(export_verified_dataset, [files, domain, profile], download)
                gr.Button("查看校验报告").click(export_validation_report, [files, domain, profile], report)
        with gr.Tab("知识库 / RAG"):
            knowledge_output = gr.Textbox(label="知识域统计", lines=8)
            gr.Button("刷新知识库统计").click(knowledge_summary, outputs=knowledge_output)
            gr.Markdown("统计按 `source_type` 展示逻辑知识域；正文仍通过 Research 检索和 Evidence 引用链路使用。")
        with gr.Tab("Benchmark 评测"):
            benchmark_output = gr.Textbox(label="评测摘要", lines=8)
            gr.Button("运行黄金样本评测").click(benchmark_summary, outputs=benchmark_output)
    return demo


if __name__ == "__main__":
    build_demo().launch()
