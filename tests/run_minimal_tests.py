from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_rule_executors import (
    test_age_limit_builds_sql,
    test_duplicate_charge_builds_sql,
    test_gender_limit_builds_sql,
)
from tests.test_mock_executor import test_mock_executor_returns_safe_result_shape
from tests.test_db_executor import test_readonly_sqlite_executor_runs_duplicate_charge
from tests.test_claims_importer import test_import_claims_csv_and_execute
from tests.test_sql_safety import (
    test_delete_is_rejected,
    test_missing_date_params_rejected,
    test_unknown_table_is_rejected,
    test_valid_select_passes,
)


def main() -> None:
    test_gender_limit_builds_sql()
    test_age_limit_builds_sql()
    test_duplicate_charge_builds_sql()
    test_mock_executor_returns_safe_result_shape()
    test_readonly_sqlite_executor_runs_duplicate_charge()
    test_import_claims_csv_and_execute()
    test_valid_select_passes()
    test_delete_is_rejected()
    test_unknown_table_is_rejected()
    test_missing_date_params_rejected()
    print("minimal tests passed")


if __name__ == "__main__":
    main()
