from backend.app.core.mock_executor import execute_mock


def test_mock_executor_returns_safe_result_shape() -> None:
    result = execute_mock(
        {
            "item_rule_id": "NLRI-010871",
            "rule_type": "duplicate_charge",
            "item_code": "001103000010000|001102000030000",
            "item_name": "急诊监护费|急诊诊查费",
            "condition_text": "项目A和项目B同时收费",
        },
        {
            "parameters": {
                "date_start": "2025-01-01",
                "date_end": "2026-01-01",
            }
        },
    )

    assert result.status == "completed_mock"
    assert result.execution["mode"] == "mock"
    assert result.execution["sql_executed"] is False
    assert result.summary["institution_count"] > 0
    assert len(result.details) > 0
    assert result.export["available"] is True
    assert result.export["format"] == "csv"
