from pathlib import Path

from backend.app.core.sql_safety import load_field_mapping, validate_sql

ROOT = Path(__file__).resolve().parents[1]
FIELD_MAPPING = load_field_mapping(ROOT / "config" / "field_mapping.json")


def test_valid_select_passes():
    sql = """
SELECT sm.fixmedins_code, md5(sm.psn_no), fd.hilist_code
FROM settlement_main sm
JOIN fee_detail fd ON sm.setl_id = fd.setl_id
WHERE fd.fee_ocur_time >= :date_start
  AND fd.fee_ocur_time < :date_end
"""
    result = validate_sql(sql, {"date_start": "2025-01-01", "date_end": "2026-01-01"}, FIELD_MAPPING)
    assert result.valid


def test_delete_is_rejected():
    result = validate_sql("DELETE FROM fee_detail", {"date_start": "2025-01-01", "date_end": "2026-01-01"}, FIELD_MAPPING)
    assert not result.valid
    assert any("DELETE" in err for err in result.errors)


def test_unknown_table_is_rejected():
    sql = "SELECT * FROM secret_table WHERE setl_time >= :date_start AND setl_time < :date_end"
    result = validate_sql(sql, {"date_start": "2025-01-01", "date_end": "2026-01-01"}, FIELD_MAPPING)
    assert not result.valid
    assert any("secret_table" in err for err in result.errors)


def test_missing_date_params_rejected():
    sql = "SELECT sm.fixmedins_code FROM settlement_main sm WHERE sm.setl_time >= :date_start"
    result = validate_sql(sql, {"date_start": "2025-01-01"}, FIELD_MAPPING)
    assert not result.valid
    assert any("date_end" in err for err in result.errors)
