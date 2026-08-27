"""Convert business-friendly CSV collection files into validated JSONL inputs."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


FILES = {
    "sources": "01_来源登记.csv",
    "events": "02_事件线索.csv",
    "organizations": "03_组织职责.csv",
    "capabilities": "04_我方能力.csv",
    "cases": "05_历史案例.csv",
}
SOURCE_TYPE_MAP = {"政策": "POLICY", "组织职责": "RESPONSIBILITY", "新闻/项目": "INDUSTRY", "行业": "INDUSTRY", "案例": "CASE", "能力": "CAPABILITY", "内部": "INTERNAL"}


def convert_package(source_dir: str | Path, output_dir: str | Path) -> dict[str, int]:
    """Convert one business package and return output row counts by JSONL file."""
    source = Path(source_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rows = {key: _read_csv(source / filename) for key, filename in FILES.items()}
    _write(output / "source_manifest.jsonl", [_source(row) for row in rows["sources"]])
    _write(output / "events.jsonl", [_event(row) for row in rows["events"]])
    _write(output / "organization_cards.jsonl", [_organization(row) for row in rows["organizations"]])
    _write(output / "capability_cards.jsonl", [_capability(row) for row in rows["capabilities"]])
    _write(output / "case_cards.jsonl", [_case(row) for row in rows["cases"]])
    return {f"{key}.jsonl": len(value) for key, value in rows.items()}


def _read_csv(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 CSV and fail clearly when a business template is missing."""
    if not path.is_file():
        raise ValueError(f"缺少业务文件：{path.name}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _source(row: dict[str, str]) -> dict:
    """Map source registration columns to the technical source manifest contract."""
    return {"source_id": row.get("来源编号", ""), "title": row.get("来源标题", ""), "source_type": SOURCE_TYPE_MAP.get(row.get("来源类型", ""), row.get("来源类型", "")), "publishing_organization": row.get("发布单位", ""), "published_at": _null(row.get("发布日期")), "effective_date": None, "source_url": _null(row.get("官方链接")), "access_method": "PUBLIC_URL" if row.get("官方链接") else "ARCHIVED_FILE", "archived_file": _null(row.get("原文文件名")), "sha256": None, "collected_at": None, "collector": None, "status": "VERIFIED" if row.get("是否确认") == "是" else "DRAFT", "notes": row.get("备注", "")}


def _event(row: dict[str, str]) -> dict:
    """Map an event spreadsheet row to the ingestion event contract."""
    return {"event_id": row.get("事件编号", ""), "title": row.get("事件标题", ""), "content": row.get("发生了什么", ""), "source_id": row.get("来源编号", ""), "source_url": None, "published_at": None, "city": _null(row.get("城市")), "topics": _split(row.get("主题")), "status": row.get("状态", "DRAFT")}


def _organization(row: dict[str, str]) -> dict:
    """Map an organization or department row to the responsibility-card contract."""
    return {"organization_id": row.get("单位或处室", ""), "organization_name": row.get("单位或处室", ""), "organization_type": row.get("组织类型", ""), "organization_level": "CITY", "department_id": None, "department_name": None, "project_roles": _split(row.get("可能承担角色")), "responsibilities": _split(row.get("有来源证明的职责")), "evidence_ids": _split(row.get("来源编号")), "source_url": None, "status": row.get("确认情况", "DRAFT"), "uncertainties": _split(row.get("不确定事项"))}


def _capability(row: dict[str, str]) -> dict:
    """Map an internal capability row to the capability-card contract."""
    return {"capability_id": row.get("能力名称", ""), "name": row.get("能力名称", ""), "category": "PLATFORM", "description": row.get("能解决什么问题", ""), "applicable_topics": _split(row.get("适用主题")), "evidence_ids": _split(row.get("证明材料编号")), "visibility": "PUBLIC_OR_AUTHORIZED" if row.get("是否可对外使用") == "是" else "AUTHORIZED_ONLY", "status": row.get("状态", "DRAFT")}


def _case(row: dict[str, str]) -> dict:
    """Map a historical case row to the case-card contract."""
    return {"case_id": row.get("案例名称", ""), "name": row.get("案例名称", ""), "customer_type": row.get("客户类型或城市", ""), "city": row.get("客户类型或城市", ""), "topics": [], "delivered_capabilities": _split(row.get("对应能力")), "outcomes": _split(row.get("结果")), "evidence_ids": _split(row.get("证明材料编号")), "visibility": "PUBLIC_OR_AUTHORIZED", "status": row.get("状态", "DRAFT")}


def _split(value: str | None) -> list[str]:
    """Parse the business convention of semicolon-separated values."""
    return [item.strip() for item in (value or "").replace("；", ";").split(";") if item.strip()]


def _null(value: str | None) -> str | None:
    """Convert blank spreadsheet cells to explicit nulls."""
    return value.strip() if value and value.strip() else None


def _write(path: Path, rows: list[dict]) -> None:
    """Write UTF-8 JSONL for the existing Dataset Validator."""
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    """Convert a business package from the command line."""
    parser = argparse.ArgumentParser(description="Convert business CSV package to system JSONL")
    parser.add_argument("source_dir")
    parser.add_argument("output_dir")
    args = parser.parse_args()
    print(convert_package(args.source_dir, args.output_dir))


if __name__ == "__main__":
    main()
