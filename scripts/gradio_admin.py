"""Minimal Gradio console for validating and importing city JSONL datasets."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from app.knowledge.dataset import DatasetValidationError, load_dataset
from app.knowledge.postgres import PostgresKnowledgeRepository
from app.observability import get_graph_events
from app.runs import get_run_repository
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


def browse_knowledge(knowledge_domain: str = "ALL", expert_profile_id: str = "AUTO", topic: str = "") -> str:
    """Browse filtered knowledge metadata for Admin verification and export preparation."""
    try:
        rows = PostgresKnowledgeRepository().browse(
            None if knowledge_domain == "ALL" else knowledge_domain,
            None if expert_profile_id == "AUTO" else expert_profile_id,
            topic.strip() or None,
        )
    except Exception as exc:  # pragma: no cover - infrastructure behavior belongs to deployment checks
        return f"知识库暂不可用：{exc}"
    safe_rows = [{"document_id": row["document_id"], "source_type": row["source_type"], "title": row["title"], "organization": row["organization"], "source_url": row["source_url"], "metadata": row["metadata"], "chunks": row["chunks"], "embedded_chunks": row["embedded_chunks"]} for row in rows]
    return json.dumps(safe_rows, ensure_ascii=False, indent=2, default=str) if safe_rows else "没有匹配的知识文档。"


def benchmark_summary() -> str:
    """Run the deterministic golden-sample benchmark and return its compact report."""
    environment = {"LLM_ENABLED": "false", "KNOWLEDGE_BACKEND": "seed", "HITL_CHECKPOINT_BACKEND": "memory"}
    process_env = {**environment, **__import__("os").environ}
    process_env.update(environment)
    completed = subprocess.run([sys.executable, "-m", "evaluation.run_benchmark"], capture_output=True, text=True, env=process_env, check=False)
    if completed.returncode != 0:
        return f"Benchmark 运行失败：{completed.stderr.strip() or completed.stdout.strip()}"
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return f"Benchmark 输出无法解析：{completed.stdout.strip()}"
    return json.dumps({key: report[key] for key in ("total", "passed", "failed", "historical_knowledge_coverage")}, ensure_ascii=False, indent=2)


def runtime_events(run_id: str) -> str:
    """Render safe node events for a run so every Graph entrypoint is observable."""
    if not run_id.strip():
        return "请输入 run_id。"
    events = get_graph_events(run_id.strip())
    return json.dumps(events, ensure_ascii=False, indent=2) if events else "暂未发现运行事件；请确认 run_id 或等待 Graph 启动。"


def recent_runs() -> list[str]:
    """Return recent persisted run IDs for automatic Admin selection."""
    try:
        return [item["run_id"] for item in get_run_repository().list_runs()]
    except Exception:
        return []


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
            browse_domain = gr.Dropdown(["ALL", *[item.value for item in EvidenceType]], value="ALL", label="浏览知识域")
            browse_profile = gr.Dropdown(["AUTO", *sorted(list_profiles())], value="AUTO", label="浏览专家 Profile")
            browse_topic = gr.Textbox(label="主题过滤（可选）")
            browse_output = gr.Textbox(label="知识文档摘要", lines=12)
            gr.Button("浏览知识文档").click(browse_knowledge, [browse_domain, browse_profile, browse_topic], browse_output)
            gr.Markdown("统计按 `source_type` 展示逻辑知识域；正文仍通过 Research 检索和 Evidence 引用链路使用。")
        with gr.Tab("Benchmark 评测"):
            benchmark_output = gr.Textbox(label="评测摘要", lines=8)
            gr.Button("运行黄金样本评测").click(benchmark_summary, outputs=benchmark_output)
        with gr.Tab("运行状态"):
            run_id = gr.Dropdown(recent_runs(), allow_custom_value=True, label="run_id（自动发现，可手工输入）")
            events_output = gr.Textbox(label="节点事件", lines=16)
            with gr.Row():
                refresh_runs = gr.Button("刷新运行列表")
                refresh = gr.Button("刷新运行事件")
            refresh_runs.click(recent_runs, outputs=run_id)
            refresh.click(runtime_events, run_id, events_output)
            timer = gr.Timer(2.0)
            timer.tick(runtime_events, run_id, events_output)
    return demo


if __name__ == "__main__":
    build_demo().launch()
