from __future__ import annotations

import argparse
import csv
import hashlib
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


RULE_KEYWORDS = [
    "性别",
    "儿童",
    "年龄",
    "重复收费",
    "限定频次",
    "周期超频次",
    "支付疗程",
    "医疗机构级别",
    "适应症",
    "就医方式",
    "互联网医院",
    "工伤保险",
    "生育保险",
]

PROJECT_CATALOG_KEYWORDS = [
    "诊疗项目目录",
    "医疗服务价格",
    "价格项目",
    "汇总表",
    "项目价格",
]

POLICY_KEYWORDS = [
    "通知",
    "医保局",
    "医疗保障局",
    "政策",
    "支付",
    "集采",
    "集中带量采购",
]

CONVERSION_EXTENSIONS = {".wps", ".et", ".doc", ".rar"}
DIRECT_PARSE_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".md"}


@dataclass
class Asset:
    asset_id: str
    source_package: str
    original_path: str
    file_name: str
    file_ext: str
    file_size: int
    content_hash: str
    category: str
    target_module: str
    convert_required: str
    parse_status: str
    parse_error: str


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def classify(name: str, ext: str, source_package: str) -> tuple[str, str, str, str]:
    text = name.lower()
    convert_required = "yes" if ext in CONVERSION_EXTENSIONS else "no"
    initial_status = "needs_convert" if convert_required == "yes" else "raw_registered"

    if ext == "":
        return "directory", "asset_manifest", "no", "raw_registered"

    if "国家医保智能监管两库" in source_package:
        if ext in {".xlsx", ".xls"}:
            return "rule_source", "rule_engine", convert_required, initial_status

    if any(keyword in name for keyword in PROJECT_CATALOG_KEYWORDS):
        return "project_catalog_or_price", "data_ingestion", convert_required, initial_status

    if ext in CONVERSION_EXTENSIONS:
        return "needs_conversion", "data_ingestion", "yes", "needs_convert"

    if any(keyword in name for keyword in POLICY_KEYWORDS) or ext in {".pdf", ".docx", ".doc", ".wps", ".md"}:
        return "policy_document", "rag_knowledge_base", convert_required, initial_status

    if ext in {".xlsx", ".xls", ".et"}:
        return "table_attachment", "data_ingestion", convert_required, initial_status

    return "unclassified", "manual_review", convert_required, "manual_review"


def zip_assets(zip_path: Path, index_start: int) -> tuple[list[Asset], int]:
    assets: list[Asset] = []
    zip_hash = sha256_file(zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        for entry in zf.infolist():
            name = entry.filename
            file_name = Path(name).name
            ext = Path(file_name).suffix.lower()
            category, target, convert_required, status = classify(name, ext, zip_path.name)
            assets.append(
                Asset(
                    asset_id=f"A{index_start:06d}",
                    source_package=zip_path.name,
                    original_path=name,
                    file_name=file_name,
                    file_ext=ext,
                    file_size=entry.file_size,
                    content_hash=zip_hash if entry.is_dir() else f"zip:{zip_hash}:{entry.CRC}",
                    category=category,
                    target_module=target,
                    convert_required=convert_required,
                    parse_status=status,
                    parse_error="",
                )
            )
            index_start += 1
    return assets, index_start


def file_asset(path: Path, index: int) -> Asset:
    ext = path.suffix.lower()
    category, target, convert_required, status = classify(path.name, ext, path.name)
    return Asset(
        asset_id=f"A{index:06d}",
        source_package="single_file",
        original_path=str(path),
        file_name=path.name,
        file_ext=ext,
        file_size=path.stat().st_size,
        content_hash=sha256_file(path),
        category=category,
        target_module=target,
        convert_required=convert_required,
        parse_status=status,
        parse_error="",
    )


def write_csv(path: Path, rows: list[Asset]) -> None:
    fields = list(Asset.__dataclass_fields__.keys())
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def write_filtered(path: Path, rows: list[Asset], predicate) -> None:
    write_csv(path, [row for row in rows if predicate(row)])


def write_summary(path: Path, rows: list[Asset]) -> None:
    by_ext: dict[str, int] = {}
    by_category: dict[str, int] = {}
    by_target: dict[str, int] = {}
    for row in rows:
        by_ext[row.file_ext or "(directory)"] = by_ext.get(row.file_ext or "(directory)", 0) + 1
        by_category[row.category] = by_category.get(row.category, 0) + 1
        by_target[row.target_module] = by_target.get(row.target_module, 0) + 1

    def table(title: str, data: dict[str, int]) -> list[str]:
        lines = [f"## {title}", "", "| 项 | 数量 |", "|---|---:|"]
        for key, count in sorted(data.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"| {key} | {count} |")
        lines.append("")
        return lines

    lines = [
        "# 原始资料资产盘点摘要",
        "",
        f"生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "",
        f"资产总数：{len(rows)}",
        "",
    ]
    lines.extend(table("按文件格式统计", by_ext))
    lines.extend(table("按分类统计", by_category))
    lines.extend(table("按目标模块统计", by_target))
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--architecture-md", required=True)
    parser.add_argument("--province-zip", required=True)
    parser.add_argument("--national-rules-zip", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[Asset] = []
    index = 1
    rows.append(file_asset(Path(args.architecture_md), index))
    index += 1
    for zip_arg in [args.province_zip, args.national_rules_zip]:
        zip_rows, index = zip_assets(Path(zip_arg), index)
        rows.extend(zip_rows)

    write_csv(output_dir / "raw_assets.csv", rows)
    write_filtered(output_dir / "rule_source_files.csv", rows, lambda row: row.target_module == "rule_engine")
    write_filtered(output_dir / "rag_source_files.csv", rows, lambda row: row.target_module == "rag_knowledge_base")
    write_filtered(output_dir / "conversion_queue.csv", rows, lambda row: row.convert_required == "yes")
    write_summary(output_dir / "asset_summary.md", rows)

    print(f"assets={len(rows)}")
    print(output_dir / "raw_assets.csv")
    print(output_dir / "asset_summary.md")


if __name__ == "__main__":
    main()
