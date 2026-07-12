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
]


@dataclass
class ParsedRow:
    source_file: str
    sheet_name: str
    row_number: int
    headers: list[str]
    values: list[str]
    raw: dict[str, str]


@dataclass
class LinkedRuleItem:
    item_rule_id: str
    rule_type: str
    source_file: str
    source_sheet: str
    knowledge_point_id: str
    item_code: str
    item_name: str
    condition_text: str
    gender_limit: str
    age_limit: str
    raw_row_json: str
    link_status: str
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
        target = rel_map.get(sheet.attrib.get(rid_attr, ""))
        if target:
            path = ("xl/" + target.lstrip("/")).replace("xl/../", "", 1)
            sheets.append((sheet.attrib.get("name", "Sheet"), path))
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
            value_node = cell.find("m:v", ns)
            inline_node = cell.find("m:is", ns)
            cell_type = cell.attrib.get("t")
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
        joined = " ".join(cell for cell in row if cell)
        score = len([cell for cell in row if cell])
        if re.search("编码|代码|名称|规则|限制|项目|药品|备注|性别|年龄|对应知识点", joined):
            score += 10
        if score > best_score:
            best_index = idx
            best_score = score
    return best_index


def get_by_patterns(raw: dict[str, str], patterns: list[str], exclude: list[str] | None = None) -> str:
    exclude = exclude or []
    for pattern in patterns:
        for key, value in raw.items():
            if any(re.search(item, key) for item in exclude):
                continue
            if re.search(pattern, key) and value:
                return value
    return ""


def parse_sheet(source_file: str, sheet_name: str, rows: list[tuple[int, list[str]]]) -> list[ParsedRow]:
    if not rows:
        return []
    header_idx = find_header_index(rows)
    headers = rows[header_idx][1]
    parsed: list[ParsedRow] = []
    for row_number, values in rows[header_idx + 1 :]:
        raw = {headers[i] or f"col_{i + 1}": values[i] for i in range(min(len(headers), len(values))) if values[i]}
        if raw:
            parsed.append(ParsedRow(source_file, sheet_name, row_number, headers, values, raw))
    return parsed


def build_linked_items_for_workbook(source_file: str, parsed_rows: list[ParsedRow]) -> list[LinkedRuleItem]:
    rule_type = infer_rule_type(source_file)
    if rule_type not in PRIORITY_RULE_TYPES:
        return []

    if rule_type == "duplicate_charge":
        linked_pairs: list[LinkedRuleItem] = []
        for row in parsed_rows:
            code_a = get_by_patterns(row.raw, ["医疗服务项目A代码", "项目A代码"])
            code_b = get_by_patterns(row.raw, ["医疗服务项目B代码", "项目B代码"])
            name_a = get_by_patterns(row.raw, ["医疗服务项目A名称", "项目A名称"])
            name_b = get_by_patterns(row.raw, ["医疗服务项目B名称", "项目B名称"])
            if not (code_a and code_b):
                continue
            linked_pairs.append(
                LinkedRuleItem(
                    item_rule_id="",
                    rule_type=rule_type,
                    source_file=source_file,
                    source_sheet=row.sheet_name,
                    knowledge_point_id=get_by_patterns(row.raw, ["^序号$"]),
                    item_code=f"{code_a}|{code_b}",
                    item_name=f"{name_a}|{name_b}",
                    condition_text=get_by_patterns(row.raw, ["检出逻辑", "逻辑依据", "备注", "时间区间"]),
                    gender_limit="",
                    age_limit="",
                    raw_row_json=json.dumps({"pair_row": row.raw}, ensure_ascii=False),
                    link_status="pair_direct",
                    status="draft",
                )
            )
        return linked_pairs

    details_by_kp: dict[str, ParsedRow] = {}
    code_rows: list[ParsedRow] = []
    direct_rows: list[ParsedRow] = []

    for row in parsed_rows:
        kp_for_code = get_by_patterns(row.raw, ["对应知识点序号"])
        item_code = get_by_patterns(row.raw, ["药品代码$", "项目代码$", "^编码$", "^代码$"], ["数量", "参考"])
        if kp_for_code and item_code:
            code_rows.append(row)
            continue

        kp_for_detail = get_by_patterns(row.raw, ["^序号$"])
        condition = get_by_patterns(row.raw, ["检出逻辑", "逻辑依据", "限定性别", "年龄", "备注"])
        if kp_for_detail and condition:
            details_by_kp[kp_for_detail] = row

        if item_code:
            direct_rows.append(row)

    linked: list[LinkedRuleItem] = []
    for row in code_rows:
        kp = get_by_patterns(row.raw, ["对应知识点序号"])
        detail = details_by_kp.get(kp)
        detail_raw = detail.raw if detail else {}
        merged_raw = {"code_row": row.raw, "detail_row": detail_raw}
        linked.append(
            LinkedRuleItem(
                item_rule_id="",
                rule_type=rule_type,
                source_file=source_file,
                source_sheet=row.sheet_name,
                knowledge_point_id=kp,
                item_code=get_by_patterns(row.raw, ["药品代码$", "项目代码$", "^编码$", "^代码$"], ["数量", "参考"]),
                item_name=get_by_patterns(row.raw, ["药品通用名", "医疗服务项目名称", "项目名称", "药品名称", "名称"])
                or get_by_patterns(detail_raw, ["药品通用名", "医疗服务项目名称", "项目名称", "药品名称", "名称"]),
                condition_text=get_by_patterns(detail_raw, ["检出逻辑", "逻辑依据", "备注", "说明"]),
                gender_limit=get_by_patterns(detail_raw, ["限定性别", "性别"]),
                age_limit=get_by_patterns(detail_raw, ["年龄", "儿童"]),
                raw_row_json=json.dumps(merged_raw, ensure_ascii=False),
                link_status="linked" if detail else "code_without_detail",
                status="draft",
            )
        )

    for row in direct_rows:
        if row in code_rows:
            continue
        linked.append(
            LinkedRuleItem(
                item_rule_id="",
                rule_type=rule_type,
                source_file=source_file,
                source_sheet=row.sheet_name,
                knowledge_point_id=get_by_patterns(row.raw, ["^序号$", "对应知识点序号"]),
                item_code=get_by_patterns(row.raw, ["药品代码$", "项目代码$", "^编码$", "^代码$"], ["数量", "参考"]),
                item_name=get_by_patterns(row.raw, ["药品通用名", "医疗服务项目名称", "项目名称", "药品名称", "名称"]),
                condition_text=get_by_patterns(row.raw, ["检出逻辑", "逻辑依据", "备注", "说明"]),
                gender_limit=get_by_patterns(row.raw, ["限定性别", "性别"]),
                age_limit=get_by_patterns(row.raw, ["年龄", "儿童"]),
                raw_row_json=json.dumps({"direct_row": row.raw}, ensure_ascii=False),
                link_status="direct",
                status="draft",
            )
        )

    return linked


def extract_linked_items(zip_path: Path) -> list[LinkedRuleItem]:
    items: list[LinkedRuleItem] = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".xlsx"):
                continue
            if infer_rule_type(name) not in PRIORITY_RULE_TYPES:
                continue
            parsed_rows: list[ParsedRow] = []
            with zipfile.ZipFile(io.BytesIO(zf.read(name))) as xlsx:
                shared_strings = read_shared_strings(xlsx)
                for sheet_name, sheet_path in read_workbook_sheets(xlsx):
                    parsed_rows.extend(parse_sheet(name, sheet_name, read_sheet_rows(xlsx, sheet_path, shared_strings)))
            items.extend(build_linked_items_for_workbook(name, parsed_rows))

    for index, item in enumerate(items, start=1):
        item.item_rule_id = f"NLRI-{index:06d}"
    return items


def write_csv(path: Path, items: list[LinkedRuleItem]) -> None:
    fields = list(LinkedRuleItem.__dataclass_fields__.keys())
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for item in items:
            writer.writerow(item.__dict__)


def write_jsonl(path: Path, items: list[LinkedRuleItem]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item.__dict__, ensure_ascii=False) + "\n")


def write_report(path: Path, items: list[LinkedRuleItem]) -> None:
    by_type: dict[str, int] = {}
    by_link: dict[str, int] = {}
    for item in items:
        by_type[item.rule_type] = by_type.get(item.rule_type, 0) + 1
        by_link[item.link_status] = by_link.get(item.link_status, 0) + 1

    lines = [
        "# 优先规则 linked item 明细报告",
        "",
        f"linked item 数量：{len(items)}",
        "",
        "## 按规则类型统计",
        "",
        "| rule_type | 数量 |",
        "|---|---:|",
    ]
    for key, count in sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {key} | {count} |")
    lines.extend(["", "## 按链接状态统计", "", "| link_status | 数量 |", "|---|---:|"])
    for key, count in sorted(by_link.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {key} | {count} |")

    lines.extend(["", "## 样例", "", "| item_rule_id | rule_type | item_code | item_name | condition | link_status |", "|---|---|---|---|---|---|"])
    for item in items[:20]:
        condition = (item.condition_text or item.gender_limit or item.age_limit)[:80]
        lines.append(f"| {item.item_rule_id} | {item.rule_type} | {item.item_code} | {item.item_name} | {condition} | {item.link_status} |")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--national-rules-zip", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    items = extract_linked_items(Path(args.national_rules_zip))
    write_csv(Path(args.output_csv), items)
    write_jsonl(Path(args.output_jsonl), items)
    write_report(Path(args.output_md), items)
    print(f"linked_items={len(items)}")
    print(args.output_md)


if __name__ == "__main__":
    main()
