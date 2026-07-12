from __future__ import annotations

import csv
import json
import os
from pathlib import Path

from backend.app.core.db_executor import execute_readonly_query
from data_ingestion.import_claims_to_sqlite import main as import_main


ROOT = Path(__file__).resolve().parents[1]


def write_csv(path: Path, headers: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def test_import_claims_csv_and_execute(tmp_path: Path | None = None) -> None:
    work_dir = tmp_path or (ROOT / "backend" / "runtime" / "test_claims_importer")
    inbox = work_dir / "inbox"
    output_db = work_dir / "claims.db"
    mapping_path = work_dir / "mapping.json"
    write_csv(
        inbox / "settlement.csv",
        ["结算流水号", "就诊流水号", "医疗机构编码", "人员编号", "性别", "年龄", "基金支付金额", "结算时间"],
        [
            {"结算流水号": "S100", "就诊流水号": "M100", "医疗机构编码": "H9001", "人员编号": "P9001", "性别": "1", "年龄": 50, "基金支付金额": 100, "结算时间": "2025-02-01"},
        ],
    )
    write_csv(
        inbox / "fee.csv",
        ["结算流水号", "就诊流水号", "医保项目编码", "医保项目名称", "数量", "单价", "明细金额", "费用发生时间"],
        [
            {"结算流水号": "S100", "就诊流水号": "M100", "医保项目编码": "001103000010000", "医保项目名称": "急诊监护费", "数量": 1, "单价": 120, "明细金额": 120, "费用发生时间": "2025-02-01"},
            {"结算流水号": "S100", "就诊流水号": "M100", "医保项目编码": "001102000030000", "医保项目名称": "急诊诊查费", "数量": 1, "单价": 30, "明细金额": 30, "费用发生时间": "2025-02-01"},
        ],
    )
    mapping_path.write_text(
        json.dumps(
            {
                "settlement_main": {
                    "file": str(inbox / "settlement.csv"),
                    "columns": {
                        "setl_id": ["结算流水号"],
                        "mdtrt_id": ["就诊流水号"],
                        "fixmedins_code": ["医疗机构编码"],
                        "psn_no": ["人员编号"],
                        "gend": ["性别"],
                        "age": ["年龄"],
                        "fund_pay_sumamt": ["基金支付金额"],
                        "setl_time": ["结算时间"],
                    },
                },
                "fee_detail": {
                    "file": str(inbox / "fee.csv"),
                    "columns": {
                        "setl_id": ["结算流水号"],
                        "mdtrt_id": ["就诊流水号"],
                        "hilist_code": ["医保项目编码"],
                        "hilist_name": ["医保项目名称"],
                        "cnt": ["数量"],
                        "pric": ["单价"],
                        "det_item_fee_sumamt": ["明细金额"],
                        "fee_ocur_time": ["费用发生时间"],
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    old_argv = os.sys.argv
    os.sys.argv = ["import_claims_to_sqlite", "--mapping", str(mapping_path), "--output", str(output_db)]
    try:
        import_main()
    finally:
        os.sys.argv = old_argv

    config_path = work_dir / "database.local.json"
    config_path.write_text(
        json.dumps({"enabled": True, "provider": "sqlite", "readonly": True, "sqlite_path": str(output_db), "max_rows": 50}, ensure_ascii=False),
        encoding="utf-8",
    )
    old_config = os.environ.get("MEDICAL_INSURANCE_DB_CONFIG")
    os.environ["MEDICAL_INSURANCE_DB_CONFIG"] = str(config_path)
    try:
        result = execute_readonly_query(
            ROOT,
            {"rule_type": "duplicate_charge", "item_code": "001103000010000|001102000030000", "item_name": "急诊监护费|急诊诊查费", "condition_text": "项目A和项目B同时收费"},
            {
                "sql_template_id": "duplicate_charge_pair_v1",
                "sql": """
                SELECT sm.fixmedins_code AS institution_code,
                       md5(sm.psn_no) AS patient_id_masked,
                       sm.mdtrt_id AS encounter_id,
                       sm.setl_id AS settlement_id,
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
                "parameters": {"item_code_a": "001103000010000", "item_code_b": "001102000030000", "date_start": "2025-01-01", "date_end": "2026-01-01"},
            },
        )
    finally:
        if old_config is None:
            os.environ.pop("MEDICAL_INSURANCE_DB_CONFIG", None)
        else:
            os.environ["MEDICAL_INSURANCE_DB_CONFIG"] = old_config

    assert result.status == "completed_real"
    assert result.summary["detail_count"] == 1
    assert result.details[0]["settlement_id"] == "S100"
