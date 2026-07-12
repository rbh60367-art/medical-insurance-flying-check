from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DbExecutionResult:
    task_id: str
    status: str
    summary: dict[str, Any]
    charts: dict[str, Any]
    details: list[dict[str, Any]]
    export: dict[str, Any]
    execution: dict[str, Any]


class DatabaseNotConfiguredError(RuntimeError):
    pass


class DatabaseExecutionError(RuntimeError):
    pass


def load_database_config(root: Path) -> dict[str, Any]:
    config_path = os.environ.get("MEDICAL_INSURANCE_DB_CONFIG")
    if config_path:
        path = Path(config_path)
    else:
        path = root / "config" / "database.local.json"
    if not path.exists():
        raise DatabaseNotConfiguredError(
            "database.local.json is not configured; copy config/database.example.json and fill readonly connection settings"
        )
    with path.open("r", encoding="utf-8-sig") as f:
        config = json.load(f)
    if not config.get("enabled"):
        raise DatabaseNotConfiguredError("database execution is disabled in database.local.json")
    if not config.get("readonly", True):
        raise DatabaseExecutionError("database connection must be readonly")
    return config


def make_task_id(sql_template_id: str, params: dict[str, Any]) -> str:
    payload = json.dumps({"template": sql_template_id, "params": params}, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"REAL-{digest.upper()}"


def connect_sqlite(config: dict[str, Any]) -> sqlite3.Connection:
    db_path = config.get("sqlite_path")
    if not db_path:
        raise DatabaseExecutionError("sqlite_path is required for sqlite provider")
    uri = f"file:{Path(db_path).as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=float(config.get("timeout_seconds", 10)))
    conn.row_factory = sqlite3.Row
    conn.create_function("md5", 1, lambda value: hashlib.md5(str(value).encode("utf-8")).hexdigest())
    return conn


def connect_database(config: dict[str, Any]) -> sqlite3.Connection:
    provider = str(config.get("provider", "sqlite")).lower()
    if provider != "sqlite":
        raise DatabaseExecutionError(f"provider not supported in MVP runtime: {provider}")
    return connect_sqlite(config)


def summarize_rows(rows: list[dict[str, Any]], rule_type: str, item_name: str) -> dict[str, Any]:
    institutions = {str(row.get("institution_code", "")) for row in rows if row.get("institution_code") is not None}
    patients = {str(row.get("patient_id_masked", "")) for row in rows if row.get("patient_id_masked") is not None}
    settlements = {str(row.get("settlement_id", row.get("encounter_id", ""))) for row in rows if row.get("settlement_id") or row.get("encounter_id")}
    total_amount = 0.0
    for row in rows:
        for key in ("total_amount", "amount", "item_a_amount", "item_b_amount"):
            value = row.get(key)
            if isinstance(value, (int, float)):
                total_amount += float(value)
                break
    return {
        "institution_count": len(institutions),
        "patient_count": len(patients),
        "settlement_count": len(settlements),
        "detail_count": len(rows),
        "total_amount": round(total_amount, 2),
        "fund_related_amount": None,
        "rule_type": rule_type,
        "item_name": item_name,
    }


def build_charts(rows: list[dict[str, Any]], rule_type: str) -> dict[str, Any]:
    org_counts: dict[str, int] = {}
    for row in rows:
        name = str(row.get("institution_code") or row.get("institution_name") or "未知机构")
        org_counts[name] = org_counts.get(name, 0) + 1
    ranking = sorted(org_counts.items(), key=lambda item: item[1], reverse=True)[:8]
    return {
        "institution_ranking": [{"name": name, "value": value} for name, value in ranking],
        "monthly_trend": [],
        "rule_distribution": [{"name": rule_type, "value": len(rows)}],
    }


def normalize_details(rows: list[dict[str, Any]], rule_item: dict[str, Any]) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        detail = dict(row)
        detail.setdefault("row_no", index)
        detail.setdefault("rule_type", rule_item.get("rule_type"))
        detail.setdefault("item_code", rule_item.get("item_code"))
        detail.setdefault("item_name", rule_item.get("item_name"))
        detail.setdefault("reason", rule_item.get("condition_text") or "命中规则疑点")
        details.append(detail)
    return details


def execute_readonly_query(root: Path, rule_item: dict[str, Any], sql_result: dict[str, Any]) -> DbExecutionResult:
    config = load_database_config(root)
    max_rows = int(config.get("max_rows", 500))
    started = time.time()
    rows: list[dict[str, Any]] = []
    with connect_database(config) as conn:
        cursor = conn.execute(sql_result["sql"], sql_result.get("parameters", {}))
        for row in cursor.fetchmany(max_rows):
            rows.append(dict(row))
    details = normalize_details(rows, rule_item)
    rule_type = str(rule_item.get("rule_type") or "")
    item_name = str(rule_item.get("item_name") or "")
    task_id = make_task_id(sql_result.get("sql_template_id", "unknown"), sql_result.get("parameters", {}))
    elapsed_ms = int((time.time() - started) * 1000)
    return DbExecutionResult(
        task_id=task_id,
        status="completed_real",
        summary=summarize_rows(details, rule_type, item_name),
        charts=build_charts(details, rule_type),
        details=details,
        export={
            "available": True,
            "format": "csv",
            "reason": "Readonly database execution result can be exported as CSV.",
        },
        execution={
            "mode": "readonly_database",
            "sql_executed": True,
            "provider": config.get("provider", "sqlite"),
            "elapsed_ms": elapsed_ms,
            "row_limit": max_rows,
            "row_count": len(details),
        },
    )

def database_status(root: Path) -> dict[str, Any]:
    config = load_database_config(root)
    status: dict[str, Any] = {
        "configured": True,
        "provider": config.get("provider", "sqlite"),
        "readonly": config.get("readonly", True),
        "max_rows": config.get("max_rows", 500),
        "tables": {},
    }
    if config.get("provider", "sqlite") == "sqlite":
        status["sqlite_path"] = config.get("sqlite_path")
    with connect_database(config) as conn:
        for table in ("settlement_main", "fee_detail"):
            try:
                row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
                status["tables"][table] = int(row["count"] if row else 0)
            except Exception as exc:
                status["tables"][table] = {"error": str(exc)}
    return status
