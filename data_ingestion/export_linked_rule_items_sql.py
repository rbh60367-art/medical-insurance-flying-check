from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def sql_string(value: str | None) -> str:
    if value is None or value == "":
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def jsonb_string(value: str | None) -> str:
    if not value:
        return "'{}'::jsonb"
    try:
        json.loads(value)
        normalized = value
    except json.JSONDecodeError:
        normalized = json.dumps({"raw": value}, ensure_ascii=False)
    return "'" + normalized.replace("'", "''") + "'::jsonb"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-sql", required=True)
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    rows = list(csv.DictReader(Path(args.input_csv).open("r", encoding="utf-8-sig")))
    output = Path(args.output_sql)
    output.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "item_rule_id",
        "rule_type",
        "source_file",
        "source_sheet",
        "knowledge_point_id",
        "item_code",
        "item_name",
        "condition_text",
        "gender_limit",
        "age_limit",
        "raw_row",
        "link_status",
        "status",
    ]

    lines = [
        "-- Generated from linked_priority_rule_items.csv",
        "-- Import after database/migrations/001_core_assets_rules_rag.sql",
        "BEGIN;",
        "",
    ]

    for start in range(0, len(rows), args.batch_size):
        batch = rows[start : start + args.batch_size]
        lines.append("INSERT INTO linked_rule_items (")
        lines.append("    " + ", ".join(columns))
        lines.append(") VALUES")
        value_lines = []
        for row in batch:
            values = [
                sql_string(row["item_rule_id"]),
                sql_string(row["rule_type"]),
                sql_string(row["source_file"]),
                sql_string(row["source_sheet"]),
                sql_string(row["knowledge_point_id"]),
                sql_string(row["item_code"]),
                sql_string(row["item_name"]),
                sql_string(row["condition_text"]),
                sql_string(row["gender_limit"]),
                sql_string(row["age_limit"]),
                jsonb_string(row["raw_row_json"]),
                sql_string(row["link_status"]),
                sql_string(row["status"]),
            ]
            value_lines.append("    (" + ", ".join(values) + ")")
        lines.append(",\n".join(value_lines))
        lines.append(
            "ON CONFLICT (item_rule_id) DO UPDATE SET "
            "rule_type = EXCLUDED.rule_type, "
            "source_file = EXCLUDED.source_file, "
            "source_sheet = EXCLUDED.source_sheet, "
            "knowledge_point_id = EXCLUDED.knowledge_point_id, "
            "item_code = EXCLUDED.item_code, "
            "item_name = EXCLUDED.item_name, "
            "condition_text = EXCLUDED.condition_text, "
            "gender_limit = EXCLUDED.gender_limit, "
            "age_limit = EXCLUDED.age_limit, "
            "raw_row = EXCLUDED.raw_row, "
            "link_status = EXCLUDED.link_status, "
            "status = EXCLUDED.status, "
            "updated_at = now();"
        )
        lines.append("")

    lines.append("COMMIT;")
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"rows={len(rows)}")
    print(output)


if __name__ == "__main__":
    main()
