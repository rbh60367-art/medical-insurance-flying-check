from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from backend.app.core.db_executor import execute_readonly_query


ROOT = Path(__file__).resolve().parents[1]


def build_sample_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE settlement_main (
              setl_id TEXT PRIMARY KEY,
              mdtrt_id TEXT,
              fixmedins_code TEXT,
              psn_no TEXT,
              gend TEXT,
              age INTEGER,
              fund_pay_sumamt REAL,
              setl_time TEXT
            );
            CREATE TABLE fee_detail (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              setl_id TEXT,
              mdtrt_id TEXT,
              hilist_code TEXT,
              hilist_name TEXT,
              cnt REAL,
              pric REAL,
              det_item_fee_sumamt REAL,
              fee_ocur_time TEXT
            );
            """
        )
        conn.execute("INSERT INTO settlement_main VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("S001", "M001", "H1001", "P001", "1", 45, 180.0, "2025-03-10"))
        conn.executemany(
            "INSERT INTO fee_detail (setl_id, mdtrt_id, hilist_code, hilist_name, cnt, pric, det_item_fee_sumamt, fee_ocur_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("S001", "M001", "001103000010000", "急诊监护费", 1, 120.0, 120.0, "2025-03-10"),
                ("S001", "M001", "001102000030000", "急诊诊查费", 1, 30.0, 30.0, "2025-03-10"),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def test_readonly_sqlite_executor_runs_duplicate_charge(tmp_path: Path | None = None) -> None:
    work_dir = tmp_path or (ROOT / "backend" / "runtime" / "test_db_executor")
    work_dir.mkdir(parents=True, exist_ok=True)
    db_path = work_dir / "sample.db"
    config_path = work_dir / "database.local.json"
    if db_path.exists():
        db_path.unlink()
    build_sample_db(db_path)
    config_path.write_text(
        json.dumps({"enabled": True, "provider": "sqlite", "readonly": True, "sqlite_path": str(db_path), "max_rows": 50}, ensure_ascii=False),
        encoding="utf-8",
    )
    old_config = os.environ.get("MEDICAL_INSURANCE_DB_CONFIG")
    os.environ["MEDICAL_INSURANCE_DB_CONFIG"] = str(config_path)
    try:
        result = execute_readonly_query(
            ROOT,
            {
                "item_rule_id": "NLRI-010871",
                "rule_type": "duplicate_charge",
                "item_code": "001103000010000|001102000030000",
                "item_name": "急诊监护费|急诊诊查费",
                "condition_text": "项目A和项目B同时收费",
            },
            {
                "sql_template_id": "duplicate_charge_pair_v1",
                "sql": """
                SELECT
                  sm.fixmedins_code AS institution_code,
                  md5(sm.psn_no) AS patient_id_masked,
                  sm.mdtrt_id AS encounter_id,
                  sm.setl_id AS settlement_id,
                  SUM(fa.det_item_fee_sumamt) AS item_a_amount,
                  SUM(fb.det_item_fee_sumamt) AS item_b_amount,
                  SUM(fa.det_item_fee_sumamt + fb.det_item_fee_sumamt) AS total_amount
                FROM settlement_main sm
                JOIN fee_detail fa ON sm.setl_id = fa.setl_id
                JOIN fee_detail fb ON sm.setl_id = fb.setl_id
                WHERE fa.hilist_code = :item_code_a
                  AND fb.hilist_code = :item_code_b
                  AND fa.fee_ocur_time >= :date_start
                  AND fa.fee_ocur_time < :date_end
                  AND fb.fee_ocur_time >= :date_start
                  AND fb.fee_ocur_time < :date_end
                GROUP BY sm.fixmedins_code, sm.psn_no, sm.mdtrt_id, sm.setl_id
                """,
                "parameters": {
                    "item_code_a": "001103000010000",
                    "item_code_b": "001102000030000",
                    "date_start": "2025-01-01",
                    "date_end": "2026-01-01",
                },
            },
        )
    finally:
        if old_config is None:
            os.environ.pop("MEDICAL_INSURANCE_DB_CONFIG", None)
        else:
            os.environ["MEDICAL_INSURANCE_DB_CONFIG"] = old_config

    assert result.status == "completed_real"
    assert result.execution["sql_executed"] is True
    assert result.summary["detail_count"] == 1
    assert result.details[0]["settlement_id"] == "S001"
