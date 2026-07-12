from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-assets-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    rows = list(csv.DictReader(Path(args.raw_assets_csv).open("r", encoding="utf-8-sig")))
    rag_rows = [row for row in rows if row["target_module"] == "rag_knowledge_base"]
    convert_rows = [row for row in rows if row["convert_required"] == "yes"]
    table_rows = [row for row in rows if row["category"] in {"project_catalog_or_price", "table_attachment"}]

    def count_by(items: list[dict[str, str]], key: str) -> dict[str, int]:
        data: dict[str, int] = {}
        for item in items:
            value = item.get(key) or "(empty)"
            data[value] = data.get(value, 0) + 1
        return data

    def render_count_table(title: str, data: dict[str, int]) -> list[str]:
        lines = [f"## {title}", "", "| 项 | 数量 |", "|---|---:|"]
        for key, value in sorted(data.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"| {key} | {value} |")
        lines.append("")
        return lines

    lines = [
        "# 医保 RAG 与文档转换处理计划",
        "",
        "## 总览",
        "",
        f"- RAG 候选文档：{len(rag_rows)}",
        f"- 待转换/解压文件：{len(convert_rows)}",
        f"- 表格类项目/价格/附件候选：{len(table_rows)}",
        "",
    ]
    lines.extend(render_count_table("RAG 候选文档格式", count_by(rag_rows, "file_ext")))
    lines.extend(render_count_table("待转换格式", count_by(convert_rows, "file_ext")))
    lines.extend(render_count_table("表格类候选分类", count_by(table_rows, "category")))

    lines.extend(
        [
            "## 处理批次",
            "",
            "### 第一批：可直接解析",
            "",
            "- PDF：抽正文、页码、标题、文号，进入 policy_documents / policy_chunks。",
            "- DOCX：抽正文和标题，进入 policy_documents / policy_chunks。",
            "- XLSX/XLS：先判断是项目清单、价格目录、政策附件还是普通说明表。",
            "",
            "### 第二批：需要转换",
            "",
            "- WPS：转换为 DOCX 或 PDF 后进入 RAG。",
            "- DOC：转换为 DOCX 或 PDF 后进入 RAG。",
            "- ET：转换为 XLSX 后重新分类。",
            "- RAR：解压后重新登记资产台账。",
            "",
            "## 输出要求",
            "",
            "每个 RAG chunk 必须带来源：标题、文号、发文日期、原始路径、页码或附件名。",
            "",
            "## 待转换样例",
            "",
            "| asset_id | file_ext | file_name | parse_status |",
            "|---|---|---|---|",
        ]
    )
    for row in convert_rows[:30]:
        lines.append(f"| {row['asset_id']} | {row['file_ext']} | {row['file_name']} | {row['parse_status']} |")

    Path(args.output_md).write_text("\n".join(lines), encoding="utf-8")
    print(args.output_md)


if __name__ == "__main__":
    main()
