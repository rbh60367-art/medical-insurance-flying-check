from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STANDARD_FIELD_ALIASES: dict[str, list[str]] = {
    "settlement_id": ["settlement_id", "setl_id", "结算流水号", "结算id", "jslsh"],
    "encounter_id": ["encounter_id", "mdtrt_id", "就诊流水号", "就诊id", "jzlsh"],
    "institution_code": ["institution_code", "fixmedins_code", "医疗机构编码", "jgdm"],
    "institution_name": ["institution_name", "fixmedins_name", "医疗机构名称", "jgmc"],
    "department_name": ["department_name", "dept_name", "科室名称", "ksmc"],
    "item_code": ["item_code", "hilist_code", "医保项目编码", "项目编码", "xmbm"],
    "item_name": ["item_name", "hilist_name", "医保项目名称", "项目名称", "xmmc"],
    "insurance_flag": ["insurance_flag", "医保标识", "是否医保", "ybbs"],
    "unit_price": ["unit_price", "pric", "单价", "dj"],
    "quantity": ["quantity", "cnt", "数量", "sl"],
    "amount": ["amount", "det_item_fee_sumamt", "金额", "je"],
    "fee_time": ["fee_time", "fee_ocur_time", "费用发生时间", "发生时间", "fssj"],
    "refund_flag": ["refund_flag", "退费标识", "冲销标识", "tfflag"],
    "gender": ["gender", "gend", "性别", "xb"],
    "age": ["age", "年龄", "nl"],
}

RULE_REQUIRED_FIELDS: dict[str, dict[str, list[str]]] = {
    "duplicate_charge": {
        "required": ["settlement_id", "item_code", "item_name", "quantity", "amount", "fee_time"],
        "recommended": ["department_name", "refund_flag"],
    },
    "frequency_limit": {
        "required": ["settlement_id", "item_code", "quantity", "fee_time"],
        "recommended": ["department_name", "refund_flag"],
    },
    "insurance_flag_check": {
        "required": ["item_code", "insurance_flag", "amount"],
        "recommended": ["item_name"],
    },
    "price_check": {
        "required": ["item_code", "unit_price", "quantity", "amount", "fee_time"],
        "recommended": ["item_name"],
    },
}


def normalize_name(value: str) -> str:
    text = str(value or "").lower().strip()
    text = re.sub(r"[\s_\-（）()【】\[\]、，,.:：]+", "", text)
    return text


def recommend_field_mapping(columns: list[str]) -> dict[str, dict[str, Any]]:
    normalized_columns = {normalize_name(column): column for column in columns}
    result: dict[str, dict[str, Any]] = {}
    for field, aliases in STANDARD_FIELD_ALIASES.items():
        matched = None
        status = "pending"
        reason = "未匹配，需现场人工确认"
        for alias in aliases:
            key = normalize_name(alias)
            if key in normalized_columns:
                matched = normalized_columns[key]
                status = "exact" if normalize_name(field) == key else "recommended"
                reason = f"字段名或别名匹配：{alias}"
                break
        result[field] = {
            "standard_field": field,
            "column": matched,
            "status": status,
            "confidence": 1.0 if status == "exact" else (0.82 if status == "recommended" else 0.0),
            "reason": reason,
        }
    return result


def match_project_codes(national_items: list[dict], site_items: list[dict]) -> list[dict]:
    site_by_code = {str(row.get("item_code", "")).strip(): row for row in site_items if row.get("item_code")}
    site_by_name = {normalize_name(row.get("item_name", "")): row for row in site_items if row.get("item_name")}
    matches: list[dict] = []
    for national in national_items:
        code = str(national.get("item_code", "")).strip()
        name = str(national.get("item_name", "")).strip()
        site = site_by_code.get(code)
        status = "exact"
        reason = "国家编码与现场编码精确匹配"
        if not site:
            site = site_by_name.get(normalize_name(name))
            status = "recommended" if site else "unmatched"
            reason = "项目名称标准化匹配" if site else "未匹配，需人工确认"
        matches.append({
            "national_item_code": code,
            "national_item_name": name,
            "site_item_code": site.get("item_code") if site else None,
            "site_item_name": site.get("item_name") if site else None,
            "status": status,
            "reason": reason,
        })
    return matches


def required_field_matrix() -> dict[str, dict[str, list[str]]]:
    return RULE_REQUIRED_FIELDS


def probe_sqlite_mapping(db_path: Path, table_mapping: dict[str, str], field_mapping: dict[str, dict[str, str]], rule_type: str = "duplicate_charge") -> dict:
    required = RULE_REQUIRED_FIELDS[rule_type]["required"]
    missing_fields = [field for field in required if field not in field_mapping or not field_mapping[field].get("column")]
    conn = sqlite3.connect(db_path)
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing_tables = [table for table in table_mapping.values() if table not in tables]
        null_rates = {}
        row_counts = {}
        for logical, physical in table_mapping.items():
            if physical not in tables:
                continue
            row_counts[logical] = conn.execute(f'SELECT COUNT(*) FROM "{physical}"').fetchone()[0]
            for standard_field, meta in field_mapping.items():
                if meta.get("table") != logical:
                    continue
                column = meta.get("column")
                total = row_counts[logical]
                nulls = conn.execute(f'SELECT COUNT(*) FROM "{physical}" WHERE "{column}" IS NULL OR "{column}" = ""').fetchone()[0]
                null_rates[standard_field] = nulls / total if total else 0
        status = "ready" if not missing_fields and not missing_tables else ("partially_ready" if not missing_tables else "blocked")
        return {
            "mapping_status": status,
            "available_rules": [rule_type] if status == "ready" else [],
            "missing_fields": missing_fields,
            "missing_tables": missing_tables,
            "probe_summary": {"row_counts": row_counts, "null_rates": null_rates},
        }
    finally:
        conn.close()


def execute_duplicate_charge_with_mapping(db_path: Path, mapping: dict, item_code_a: str, item_code_b: str, date_start: str, date_end: str) -> dict:
    tables = mapping["tables"]
    fields = mapping["fields"]
    sm = tables["settlement_main"]
    fd = tables["fee_detail"]

    def col(field: str) -> str:
        return fields[field]["column"]

    sql = f'''
SELECT
  m."{col('settlement_id')}" AS settlement_id,
  SUM(CASE WHEN f."{col('item_code')}" = :item_code_a THEN f."{col('amount')}" ELSE 0 END) AS item_a_amount,
  SUM(CASE WHEN f."{col('item_code')}" = :item_code_b THEN f."{col('amount')}" ELSE 0 END) AS item_b_amount,
  SUM(f."{col('amount')}") AS total_amount
FROM "{sm}" m
JOIN "{fd}" f ON m."{col('settlement_id')}" = f."{col('settlement_id')}"
WHERE f."{col('item_code')}" IN (:item_code_a, :item_code_b)
  AND f."{col('fee_time')}" >= :date_start
  AND f."{col('fee_time')}" < :date_end
GROUP BY m."{col('settlement_id')}"
HAVING SUM(CASE WHEN f."{col('item_code')}" = :item_code_a THEN 1 ELSE 0 END) > 0
   AND SUM(CASE WHEN f."{col('item_code')}" = :item_code_b THEN 1 ELSE 0 END) > 0
'''.strip()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in conn.execute(sql, {
            "item_code_a": item_code_a,
            "item_code_b": item_code_b,
            "date_start": date_start,
            "date_end": date_end,
        }).fetchall()]
        return {"sql": sql, "rows": rows, "summary": {"hit_count": len(rows), "total_amount": sum(row["total_amount"] for row in rows)}}
    finally:
        conn.close()