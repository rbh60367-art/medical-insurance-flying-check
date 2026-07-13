import sqlite3
from pathlib import Path

from backend.app.core.site_mapping import (
    execute_duplicate_charge_with_mapping,
    match_project_codes,
    probe_sqlite_mapping,
    recommend_field_mapping,
    required_field_matrix,
)


def create_standard_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE settlement_main (settlement_id TEXT, department_name TEXT);
        CREATE TABLE fee_detail (
          settlement_id TEXT,
          item_code TEXT,
          item_name TEXT,
          quantity REAL,
          amount REAL,
          fee_time TEXT
        );
        INSERT INTO settlement_main VALUES ('S1', '急诊科');
        INSERT INTO fee_detail VALUES ('S1', '001103000010000', '急诊监护费', 1, 100, '2025-03-01');
        INSERT INTO fee_detail VALUES ('S1', '001102000030000', '急诊诊查费', 1, 20, '2025-03-01');
        """
    )
    conn.commit()
    conn.close()


def create_local_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE js_main (jslsh TEXT, ksmc TEXT);
        CREATE TABLE mx_fee (
          jslsh TEXT,
          xmbm TEXT,
          xmmc TEXT,
          sl REAL,
          je REAL,
          fssj TEXT
        );
        INSERT INTO js_main VALUES ('S1', '急诊科');
        INSERT INTO mx_fee VALUES ('S1', '001103000010000', '急诊监护费', 1, 100, '2025-03-01');
        INSERT INTO mx_fee VALUES ('S1', '001102000030000', '急诊诊查费', 1, 20, '2025-03-01');
        """
    )
    conn.commit()
    conn.close()


STANDARD_MAPPING = {
    "tables": {"settlement_main": "settlement_main", "fee_detail": "fee_detail"},
    "fields": {
        "settlement_id": {"table": "settlement_main", "column": "settlement_id"},
        "item_code": {"table": "fee_detail", "column": "item_code"},
        "item_name": {"table": "fee_detail", "column": "item_name"},
        "quantity": {"table": "fee_detail", "column": "quantity"},
        "amount": {"table": "fee_detail", "column": "amount"},
        "fee_time": {"table": "fee_detail", "column": "fee_time"},
    },
}

LOCAL_MAPPING = {
    "tables": {"settlement_main": "js_main", "fee_detail": "mx_fee"},
    "fields": {
        "settlement_id": {"table": "settlement_main", "column": "jslsh"},
        "item_code": {"table": "fee_detail", "column": "xmbm"},
        "item_name": {"table": "fee_detail", "column": "xmmc"},
        "quantity": {"table": "fee_detail", "column": "sl"},
        "amount": {"table": "fee_detail", "column": "je"},
        "fee_time": {"table": "fee_detail", "column": "fssj"},
    },
}


def test_field_recommendation_and_project_matching():
    rec = recommend_field_mapping(["jslsh", "xmbm", "xmmc", "sl", "je", "fssj"])
    assert rec["settlement_id"]["column"] == "jslsh"
    assert rec["item_code"]["column"] == "xmbm"

    chinese_rec = recommend_field_mapping(["结算流水号", "医疗机构名称", "项目编码", "项目名称", "数量", "金额", "费用发生时间", "性别", "年龄"])
    assert chinese_rec["settlement_id"]["column"] == "结算流水号"
    assert chinese_rec["institution_name"]["column"] == "医疗机构名称"
    assert chinese_rec["item_code"]["column"] == "项目编码"
    assert chinese_rec["fee_time"]["column"] == "费用发生时间"
    matches = match_project_codes(
        [{"item_code": "001103000010000", "item_name": "急诊监护费"}],
        [{"item_code": "LOCAL001", "item_name": "急诊 监护费"}],
    )
    assert matches[0]["status"] == "recommended"
    assert matches[0]["site_item_code"] == "LOCAL001"


def test_required_field_matrix_contains_duplicate_charge_minimum():
    matrix = required_field_matrix()
    assert "settlement_id" in matrix["duplicate_charge"]["required"]
    assert "fee_time" in matrix["duplicate_charge"]["required"]


def test_dual_schema_mapping_runs_same_duplicate_charge_result(tmp_path: Path):
    standard_db = tmp_path / "standard.db"
    local_db = tmp_path / "local.db"
    create_standard_db(standard_db)
    create_local_db(local_db)

    standard_probe = probe_sqlite_mapping(standard_db, STANDARD_MAPPING["tables"], STANDARD_MAPPING["fields"])
    local_probe = probe_sqlite_mapping(local_db, LOCAL_MAPPING["tables"], LOCAL_MAPPING["fields"])
    assert standard_probe["mapping_status"] == "ready"
    assert local_probe["mapping_status"] == "ready"

    kwargs = {
        "item_code_a": "001103000010000",
        "item_code_b": "001102000030000",
        "date_start": "2025-01-01",
        "date_end": "2026-01-01",
    }
    standard_result = execute_duplicate_charge_with_mapping(standard_db, STANDARD_MAPPING, **kwargs)
    local_result = execute_duplicate_charge_with_mapping(local_db, LOCAL_MAPPING, **kwargs)
    assert standard_result["summary"] == local_result["summary"]
    assert standard_result["summary"]["hit_count"] == 1
    assert standard_result["summary"]["total_amount"] == 120