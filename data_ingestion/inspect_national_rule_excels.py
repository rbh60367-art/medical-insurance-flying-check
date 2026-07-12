from __future__ import annotations

import argparse
import csv
import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


RULE_TYPE_PATTERNS: list[tuple[str, str]] = [
    ("duplicate_charge", "重复收费"),
    ("gender_limit", "性别"),
    ("age_limit", "儿童|年龄"),
    ("frequency_limit", "限定频次|周期超频次"),
    ("treatment_course_limit", "支付疗程"),
    ("institution_level_limit", "医疗机构级别"),
    ("encounter_type_limit", "就医方式|互联网医院"),
    ("indication_limit", "适应症"),
    ("insurance_type_limit", "工伤保险|生育保险"),
    ("payment_scope_limit", "不予支付|支付范围"),
    ("second_line_drug_limit", "二线使用"),
]

FIELD_HINTS: list[tuple[str, str]] = [
    ("item_code", "编码|代码|项目编码|药品编码"),
    ("item_name", "名称|项目名称|药品名称|通用名"),
    ("rule_condition", "限制|限定|条件|规则|备注|说明"),
    ("gender", "性别|男|女"),
    ("age", "年龄|儿童|岁"),
    ("frequency", "频次|次数|周期"),
    ("institution_level", "机构级别|医院级别|医疗机构"),
    ("encounter_type", "就医方式|门诊|住院|互联网"),
    ("indication", "适应症|诊断"),
    ("insurance_type", "工伤|生育"),
]


@dataclass
class SheetInspection:
    source_file: str
    sheet_name: str
    rule_type: str
    max_row: int
    max_column: int
    header_row: int
    headers: list[str]
    sample_rows: list[list[str]]
    field_mapping: dict[str, list[str]]


def normalize_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("\r", " ").strip()


def xml_text(element) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def read_shared_strings(xlsx: zipfile.ZipFile) -> list[str]:
    try:
        data = xlsx.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ElementTree.fromstring(data)
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    return [xml_text(item) for item in root.findall("m:si", ns)]


def read_workbook_sheets(xlsx: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook = ElementTree.fromstring(xlsx.read("xl/workbook.xml"))
    rels = ElementTree.fromstring(xlsx.read("xl/_rels/workbook.xml.rels"))
    ns = {
        "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    }
    rel_map = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall("rel:Relationship", ns)
        if "Id" in rel.attrib and "Target" in rel.attrib
    }
    sheets: list[tuple[str, str]] = []
    rid_attr = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    for sheet in workbook.findall("m:sheets/m:sheet", ns):
        name = sheet.attrib.get("name", "Sheet")
        target = rel_map.get(sheet.attrib.get(rid_attr, ""))
        if not target:
            continue
        path = "xl/" + target.lstrip("/")
        path = path.replace("xl/../", "", 1)
        sheets.append((name, path))
    return sheets


def column_index(cell_ref: str) -> int:
    letters = re.sub(r"[^A-Z]", "", cell_ref.upper())
    value = 0
    for char in letters:
        value = value * 26 + (ord(char) - ord("A") + 1)
    return max(value - 1, 0)


def read_sheet_preview(
    xlsx: zipfile.ZipFile,
    sheet_path: str,
    shared_strings: list[str],
    max_rows: int = 12,
    max_cols: int = 50,
) -> tuple[list[list[str]], int, int]:
    root = ElementTree.fromstring(xlsx.read(sheet_path))
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    dimension = root.find("m:dimension", ns)
    max_row = 0
    max_column = 0
    if dimension is not None:
        end_ref = dimension.attrib.get("ref", "").split(":")[-1]
        row_match = re.search(r"(\d+)$", end_ref)
        if row_match:
            max_row = int(row_match.group(1))
        max_column = column_index(end_ref) + 1

    rows: list[list[str]] = []
    width = min(max_cols, max(max_column, 1))
    for row in root.findall("m:sheetData/m:row", ns):
        row_index = int(row.attrib.get("r", len(rows) + 1))
        if row_index > max_rows:
            break
        values = [""] * width
        for cell in row.findall("m:c", ns):
            col = column_index(cell.attrib.get("r", ""))
            if col >= width:
                continue
            cell_type = cell.attrib.get("t")
            value_node = cell.find("m:v", ns)
            inline_node = cell.find("m:is", ns)
            value = ""
            if cell_type == "s" and value_node is not None:
                idx = int(value_node.text or "0")
                value = shared_strings[idx] if idx < len(shared_strings) else ""
            elif cell_type == "inlineStr":
                value = xml_text(inline_node)
            elif value_node is not None:
                value = value_node.text or ""
            values[col] = normalize_cell(value)
        rows.append(values)
    return rows, max_row or len(rows), max_column or width


def infer_rule_type(file_name: str) -> str:
    for rule_type, pattern in RULE_TYPE_PATTERNS:
        if re.search(pattern, file_name):
            return rule_type
    return "manual_review"


def find_header_row(rows: list[list[str]]) -> int:
    best_index = 0
    best_score = -1
    for index, row in enumerate(rows):
        non_empty = [cell for cell in row if cell]
        joined = " ".join(non_empty)
        score = len(non_empty)
        if re.search("编码|名称|规则|限制|项目|药品|备注", joined):
            score += 10
        if score > best_score:
            best_index = index
            best_score = score
    return best_index + 1


def infer_field_mapping(headers: list[str]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for header in headers:
        if not header:
            continue
        for field, pattern in FIELD_HINTS:
            if re.search(pattern, header):
                mapping.setdefault(field, []).append(header)
    return mapping


def inspect_sheet(source_file: str, sheet_name: str, preview_rows: list[list[str]], max_row: int, max_column: int) -> SheetInspection:
    header_row = find_header_row(preview_rows) if preview_rows else 1
    headers = preview_rows[header_row - 1][: min(max_column, 50)] if len(preview_rows) >= header_row else []
    sample_rows: list[list[str]] = []
    for row in preview_rows[header_row: header_row + 5]:
        values = [normalize_cell(value) for value in row[: min(max_column, 12)]]
        if any(values):
            sample_rows.append(values)
    return SheetInspection(
        source_file=source_file,
        sheet_name=sheet_name,
        rule_type=infer_rule_type(source_file),
        max_row=max_row,
        max_column=max_column,
        header_row=header_row,
        headers=headers,
        sample_rows=sample_rows,
        field_mapping=infer_field_mapping(headers),
    )


def inspect_zip(zip_path: Path) -> list[SheetInspection]:
    inspections: list[SheetInspection] = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".xlsx"):
                continue
            with zipfile.ZipFile(io.BytesIO(zf.read(name))) as xlsx:
                shared_strings = read_shared_strings(xlsx)
                for sheet_name, sheet_path in read_workbook_sheets(xlsx):
                    preview, max_row, max_column = read_sheet_preview(xlsx, sheet_path, shared_strings)
                    inspections.append(inspect_sheet(name, sheet_name, preview, max_row, max_column))
    return inspections


def write_csv(path: Path, inspections: list[SheetInspection]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "source_file",
                "sheet_name",
                "rule_type",
                "max_row",
                "max_column",
                "header_row",
                "headers_json",
                "field_mapping_json",
                "sample_rows_json",
            ],
        )
        writer.writeheader()
        for item in inspections:
            writer.writerow(
                {
                    "source_file": item.source_file,
                    "sheet_name": item.sheet_name,
                    "rule_type": item.rule_type,
                    "max_row": item.max_row,
                    "max_column": item.max_column,
                    "header_row": item.header_row,
                    "headers_json": json.dumps(item.headers, ensure_ascii=False),
                    "field_mapping_json": json.dumps(item.field_mapping, ensure_ascii=False),
                    "sample_rows_json": json.dumps(item.sample_rows, ensure_ascii=False),
                }
            )


def write_report(path: Path, inspections: list[SheetInspection]) -> None:
    by_rule: dict[str, int] = {}
    for item in inspections:
        by_rule[item.rule_type] = by_rule.get(item.rule_type, 0) + 1

    lines = [
        "# 国家两库规则 Excel 检查报告",
        "",
        f"工作表数量：{len(inspections)}",
        "",
        "## 按规则类型推断",
        "",
        "| 规则类型 | 工作表数量 |",
        "|---|---:|",
    ]
    for rule_type, count in sorted(by_rule.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {rule_type} | {count} |")

    lines.extend(["", "## 文件表头样例", ""])
    for item in inspections:
        lines.extend(
            [
                f"### {Path(item.source_file).name} / {item.sheet_name}",
                "",
                f"- 推断规则类型：`{item.rule_type}`",
                f"- 行列规模：{item.max_row} 行，{item.max_column} 列",
                f"- 表头行：第 {item.header_row} 行",
                f"- 表头：`{json.dumps(item.headers, ensure_ascii=False)}`",
                f"- 字段映射：`{json.dumps(item.field_mapping, ensure_ascii=False)}`",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--national-rules-zip", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    inspections = inspect_zip(Path(args.national_rules_zip))
    write_csv(output_dir / "national_rule_excel_inspection.csv", inspections)
    write_report(output_dir / "national_rule_excel_inspection.md", inspections)
    print(f"sheets={len(inspections)}")
    print(output_dir / "national_rule_excel_inspection.md")


if __name__ == "__main__":
    main()
