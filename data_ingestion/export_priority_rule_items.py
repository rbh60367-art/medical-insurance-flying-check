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


PRIORITY_RULE_TYPES = {"gender_limit", "age_limit", "duplicate_charge"}

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


@dataclass
class ExtractedRuleItem:
    item_rule_id: str
    rule_type: str
    source_file: str
    source_sheet: str
    row_number: int
    item_code: str
    item_name: str
    condition_text: str
    gender_limit: str
    age_limit: str
    frequency_limit: str
    raw_row_json: str
    status: str


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
    rid_attr = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    sheets: list[tuple[str, str]] = []
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


def read_sheet_rows(xlsx: zipfile.ZipFile, sheet_path: str, shared_strings: list[str], max_cols: int = 80) -> list[tuple[int, list[str]]]:
    root = ElementTree.fromstring(xlsx.read(sheet_path))
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows: list[tuple[int, list[str]]] = []
    for row in root.findall("m:sheetData/m:row", ns):
        row_index = int(row.attrib.get("r", len(rows) + 1))
        values = [""] * max_cols
        for cell in row.findall("m:c", ns):
            col = column_index(cell.attrib.get("r", ""))
            if col >= max_cols:
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
        rows.append((row_index, values))
    return rows


def infer_rule_type(file_name: str) -> str:
    for rule_type, pattern in RULE_TYPE_PATTERNS:
        if re.search(pattern, file_name):
            return rule_type
    return "manual_review"


def find_header_index(rows: list[tuple[int, list[str]]]) -> int:
    best_index = 0
    best_score = -1
    for idx, (_, row) in enumerate(rows[:12]):
        non_empty = [cell for cell in row if cell]
        joined = " ".join(non_empty)
        score = len(non_empty)
        if re.search("编码|代码|名称|规则|限制|项目|药品|备注|性别|年龄|频次", joined):
            score += 10
        if score > best_score:
            best_index = idx
            best_score = score
    return best_index


def find_column(headers: list[str], patterns: list[str], exclude_patterns: list[str] | None = None) -> int | None:
    exclude_patterns = exclude_patterns or []
    for pattern in patterns:
        for idx, header in enumerate(headers):
            if not header:
                continue
            if any(re.search(exclude, header) for exclude in exclude_patterns):
                continue
            if re.search(pattern, header):
                return idx
    return None


def extract_items_from_sheet(source_file: str, sheet_name: str, rows: list[tuple[int, list[str]]]) -> list[ExtractedRuleItem]:
    if not rows:
        return []
    rule_type = infer_rule_type(source_file)
    if rule_type not in PRIORITY_RULE_TYPES:
        return []

    header_idx = find_header_index(rows)
    headers = rows[header_idx][1]
    data_rows = rows[header_idx + 1 :]

    code_col = find_column(headers, ["药品代码$", "项目代码", "医保编码", "^编码$", "^代码$"], ["数量", "参考", "对应.*数量"])
    name_col = find_column(headers, ["药品通用名", "医疗服务项目名称", "项目名称", "药品名称", "名称"])
    gender_col = find_column(headers, ["限定性别", "性别"])
    age_col = find_column(headers, ["年龄", "儿童"])
    condition_col = find_column(headers, ["检出逻辑", "逻辑依据", "限制", "限定", "备注", "说明"])
    frequency_col = find_column(headers, ["频次", "次数"])

    extracted: list[ExtractedRuleItem] = []
    for row_number, values in data_rows:
        if not any(values):
            continue
        item_code = values[code_col] if code_col is not None and code_col < len(values) else ""
        item_name = values[name_col] if name_col is not None and name_col < len(values) else ""
        condition_text = values[condition_col] if condition_col is not None and condition_col < len(values) else ""
        gender_limit = values[gender_col] if gender_col is not None and gender_col < len(values) else ""
        age_limit = values[age_col] if age_col is not None and age_col < len(values) else ""
        frequency_limit = values[frequency_col] if frequency_col is not None and frequency_col < len(values) else ""

        if not item_code and not item_name and not condition_text:
            continue

        raw = {headers[i] or f"col_{i + 1}": values[i] for i in range(min(len(headers), len(values))) if values[i]}
        extracted.append(
            ExtractedRuleItem(
                item_rule_id="",
                rule_type=rule_type,
                source_file=source_file,
                source_sheet=sheet_name,
                row_number=row_number,
                item_code=item_code,
                item_name=item_name,
                condition_text=condition_text,
                gender_limit=gender_limit,
                age_limit=age_limit,
                frequency_limit=frequency_limit,
                raw_row_json=json.dumps(raw, ensure_ascii=False),
                status="draft",
            )
        )
    return extracted


def extract_priority_items(zip_path: Path) -> list[ExtractedRuleItem]:
    items: list[ExtractedRuleItem] = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".xlsx"):
                continue
            if infer_rule_type(name) not in PRIORITY_RULE_TYPES:
                continue
            with zipfile.ZipFile(io.BytesIO(zf.read(name))) as xlsx:
                shared_strings = read_shared_strings(xlsx)
                for sheet_name, sheet_path in read_workbook_sheets(xlsx):
                    rows = read_sheet_rows(xlsx, sheet_path, shared_strings)
                    items.extend(extract_items_from_sheet(name, sheet_name, rows))
    for index, item in enumerate(items, start=1):
        item.item_rule_id = f"NRI-{index:06d}"
    return items


def write_csv(path: Path, items: list[ExtractedRuleItem]) -> None:
    fields = list(ExtractedRuleItem.__dataclass_fields__.keys())
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for item in items:
            writer.writerow(item.__dict__)


def write_jsonl(path: Path, items: list[ExtractedRuleItem]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item.__dict__, ensure_ascii=False) + "\n")


def write_report(path: Path, items: list[ExtractedRuleItem]) -> None:
    by_type: dict[str, int] = {}
    by_file: dict[str, int] = {}
    with_code = 0
    with_name = 0
    for item in items:
        by_type[item.rule_type] = by_type.get(item.rule_type, 0) + 1
        by_file[Path(item.source_file).name] = by_file.get(Path(item.source_file).name, 0) + 1
        if item.item_code:
            with_code += 1
        if item.item_name:
            with_name += 1

    lines = [
        "# 优先规则 item 级明细导出报告",
        "",
        f"明细数量：{len(items)}",
        f"带项目/药品编码：{with_code}",
        f"带项目/药品名称：{with_name}",
        "",
        "## 按规则类型统计",
        "",
        "| rule_type | 数量 |",
        "|---|---:|",
    ]
    for key, count in sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {key} | {count} |")

    lines.extend(["", "## 按来源文件统计", "", "| 来源文件 | 数量 |", "|---|---:|"])
    for key, count in sorted(by_file.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {key} | {count} |")

    lines.extend(["", "## 样例", "", "| item_rule_id | rule_type | item_code | item_name | condition |", "|---|---|---|---|---|"])
    for item in items[:20]:
        condition = (item.condition_text or item.gender_limit or item.age_limit or item.frequency_limit)[:80]
        lines.append(f"| {item.item_rule_id} | {item.rule_type} | {item.item_code} | {item.item_name} | {condition} |")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--national-rules-zip", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    items = extract_priority_items(Path(args.national_rules_zip))
    write_csv(Path(args.output_csv), items)
    write_jsonl(Path(args.output_jsonl), items)
    write_report(Path(args.output_md), items)
    print(f"items={len(items)}")
    print(args.output_md)


if __name__ == "__main__":
    main()
