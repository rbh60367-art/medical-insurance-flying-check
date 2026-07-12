from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MockExecutionResult:
    task_id: str
    status: str
    summary: dict[str, Any]
    charts: dict[str, Any]
    details: list[dict[str, Any]]
    export: dict[str, Any]
    execution: dict[str, Any]


def stable_int(seed: str, minimum: int, maximum: int) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16)
    return minimum + (value % (maximum - minimum + 1))


def make_task_id(item_rule_id: str, date_start: str, date_end: str) -> str:
    digest = hashlib.sha256(f"{item_rule_id}:{date_start}:{date_end}".encode("utf-8")).hexdigest()[:12]
    return f"MOCK-{digest.upper()}"


def execute_mock(rule_item: dict[str, Any], sql_result: dict[str, Any]) -> MockExecutionResult:
    params = sql_result.get("parameters", {})
    item_rule_id = str(rule_item.get("item_rule_id", "UNKNOWN"))
    date_start = str(params.get("date_start", ""))
    date_end = str(params.get("date_end", ""))
    seed = f"{item_rule_id}:{date_start}:{date_end}"
    task_id = make_task_id(item_rule_id, date_start, date_end)

    institution_count = stable_int(seed + ":org", 3, 18)
    patient_count = stable_int(seed + ":patient", 20, 680)
    settlement_count = stable_int(seed + ":setl", patient_count, patient_count * 3)
    detail_count = stable_int(seed + ":detail", settlement_count, settlement_count * 5)
    total_amount = stable_int(seed + ":amount", 30000, 2600000)
    fund_amount = int(total_amount * 0.62)

    item_name = str(rule_item.get("item_name") or "疑点项目")
    item_code = str(rule_item.get("item_code") or "")
    rule_type = str(rule_item.get("rule_type") or "")

    details: list[dict[str, Any]] = []
    for index in range(1, min(20, detail_count) + 1):
        row_seed = f"{seed}:row:{index}"
        amount = stable_int(row_seed + ":amount", 120, 9800)
        details.append(
            {
                "row_no": index,
                "institution_code": f"H{stable_int(row_seed + ':h', 1001, 1099)}",
                "institution_name": f"模拟医疗机构{stable_int(row_seed + ':hn', 1, 18)}",
                "patient_id_masked": hashlib.md5(row_seed.encode("utf-8")).hexdigest()[:12],
                "encounter_id": f"MZ{stable_int(row_seed + ':enc', 100000, 999999)}",
                "settlement_id": f"S{stable_int(row_seed + ':setl', 1000000, 9999999)}",
                "rule_type": rule_type,
                "item_code": item_code,
                "item_name": item_name,
                "amount": amount,
                "reason": str(rule_item.get("condition_text") or "命中规则疑点"),
            }
        )

    org_chart = [
        {"name": f"模拟医疗机构{i}", "value": stable_int(f"{seed}:chart:org:{i}", 3, 90)}
        for i in range(1, min(institution_count, 8) + 1)
    ]
    monthly = [
        {"month": f"2025-{i:02d}", "amount": stable_int(f"{seed}:month:{i}", 1000, 90000)}
        for i in range(1, 13)
    ]

    return MockExecutionResult(
        task_id=task_id,
        status="completed_mock",
        summary={
            "institution_count": institution_count,
            "patient_count": patient_count,
            "settlement_count": settlement_count,
            "detail_count": detail_count,
            "total_amount": total_amount,
            "fund_related_amount": fund_amount,
            "rule_type": rule_type,
            "item_name": item_name,
        },
        charts={
            "institution_ranking": org_chart,
            "monthly_trend": monthly,
            "rule_distribution": [{"name": rule_type, "value": detail_count}],
        },
        details=details,
        export={
            "excel_url": f"/api/v1/tasks/{task_id}/export",
            "available": True,
            "format": "csv",
            "reason": "MVP mock mode exports sample detail rows only.",
        },
        execution={
            "mode": "mock",
            "sql_executed": False,
            "date_start": date_start,
            "date_end": date_end,
            "cached": False,
        },
    )
