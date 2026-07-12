from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FORBIDDEN_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "grant",
    "revoke",
    "merge",
    "execute",
    "exec",
    "call",
    "copy",
}


@dataclass(frozen=True)
class SqlValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]
    tables: list[str]
    fields: list[str]


def load_field_mapping(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"--.*?$", "", sql, flags=re.MULTILINE)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql


def extract_tables(sql: str) -> list[str]:
    found = re.findall(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", sql, flags=re.IGNORECASE)
    return sorted(set(item.lower() for item in found))


def extract_aliases(sql: str) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for table, alias in re.findall(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", sql, flags=re.IGNORECASE):
        if alias.lower() not in {"on", "where", "group", "order", "limit"}:
            aliases[alias.lower()] = table.lower()
    return aliases


def extract_qualified_fields(sql: str) -> list[str]:
    pairs = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\b", sql)
    return sorted(set(f"{alias.lower()}.{field.lower()}" for alias, field in pairs))


def validate_sql(sql: str, parameters: dict[str, Any], field_mapping: dict[str, Any]) -> SqlValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    cleaned = strip_sql_comments(sql).strip()
    lowered = cleaned.lower()

    if not lowered.startswith("select"):
        errors.append("SQL must start with SELECT")

    statements = [item.strip() for item in cleaned.split(";") if item.strip()]
    if len(statements) > 1:
        errors.append("Only one SQL statement is allowed")

    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            errors.append(f"Forbidden SQL keyword: {keyword.upper()}")

    tables = extract_tables(cleaned)
    allowed_tables = set(field_mapping.get("tables", {}).keys())
    for table in tables:
        if table not in allowed_tables:
            errors.append(f"Table is not whitelisted: {table}")

    if not tables:
        errors.append("No table found in SQL")

    aliases = extract_aliases(cleaned)
    alias_to_table = dict(aliases)
    for table, config in field_mapping.get("tables", {}).items():
        alias = str(config.get("alias", "")).lower()
        if alias:
            alias_to_table.setdefault(alias, table)
        alias_to_table.setdefault(table, table)

    fields = extract_qualified_fields(cleaned)
    for qualified in fields:
        alias, field = qualified.split(".", 1)
        table = alias_to_table.get(alias)
        if not table:
            warnings.append(f"Unknown SQL alias: {alias}")
            continue
        allowed_fields = set(field_mapping.get("tables", {}).get(table, {}).get("fields", {}).keys())
        if field not in allowed_fields:
            errors.append(f"Field is not whitelisted: {qualified}")

    for required in field_mapping.get("required_filters", []):
        if required not in parameters:
            errors.append(f"Missing required SQL parameter: {required}")

    if "fee_ocur_time" not in lowered and "setl_time" not in lowered:
        errors.append("SQL must include a date range filter on fee_ocur_time or setl_time")

    sensitive_fields = set(field_mapping.get("sensitive_fields", []))
    select_part = lowered.split(" from ")[0]
    for field in sensitive_fields:
        if re.search(rf"\b{field}\b", select_part) and "md5" not in select_part:
            errors.append(f"Sensitive field must be masked in SELECT: {field}")

    return SqlValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        tables=tables,
        fields=fields,
    )
