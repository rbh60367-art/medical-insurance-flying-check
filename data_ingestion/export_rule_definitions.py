from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


EXECUTOR_BY_RULE_TYPE = {
    "gender_limit": "GenderLimitRule",
    "age_limit": "AgeLimitRule",
    "duplicate_charge": "DuplicateChargeRule",
    "frequency_limit": "FrequencyLimitRule",
    "treatment_course_limit": "TreatmentCourseLimitRule",
    "institution_level_limit": "InstitutionLevelLimitRule",
    "encounter_type_limit": "EncounterTypeLimitRule",
    "indication_limit": "IndicationLimitRule",
    "insurance_type_limit": "InsuranceTypeLimitRule",
    "payment_scope_limit": "PaymentScopeLimitRule",
    "second_line_drug_limit": "SecondLineDrugLimitRule",
    "manual_review": "ManualReviewRule",
}


SQL_TEMPLATE_BY_RULE_TYPE = {
    "gender_limit": "gender_limit_v1",
    "age_limit": "age_limit_v1",
    "duplicate_charge": "duplicate_charge_v1",
    "frequency_limit": "frequency_limit_v1",
    "treatment_course_limit": "treatment_course_limit_v1",
    "institution_level_limit": "institution_level_limit_v1",
    "encounter_type_limit": "encounter_type_limit_v1",
    "indication_limit": "indication_limit_v1",
    "insurance_type_limit": "insurance_type_limit_v1",
    "payment_scope_limit": "payment_scope_limit_v1",
    "second_line_drug_limit": "second_line_drug_limit_v1",
    "manual_review": "manual_review_v1",
}


def stable_rule_code(rule_type: str, index: int) -> str:
    return f"{rule_type}_{index:03d}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspection-csv", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    inspection_path = Path(args.inspection_csv)
    jsonl_path = Path(args.output_jsonl)
    md_path = Path(args.output_md)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    rows = list(csv.DictReader(inspection_path.open("r", encoding="utf-8-sig")))
    definitions = []
    for index, row in enumerate(rows, start=1):
        rule_type = row["rule_type"]
        rule_code = stable_rule_code(rule_type, index)
        source_name = Path(row["source_file"]).name
        definitions.append(
            {
                "rule_id": f"NRL-{index:04d}",
                "rule_code": rule_code,
                "rule_name": f"{source_name} / {row['sheet_name']}",
                "rule_type": rule_type,
                "target_type": "pending_infer_from_columns",
                "target_codes": [],
                "target_names": [],
                "condition": {
                    "source_headers": json.loads(row["headers_json"]),
                    "field_mapping": json.loads(row["field_mapping_json"]),
                    "needs_item_level_expansion": True,
                },
                "sql_template_id": SQL_TEMPLATE_BY_RULE_TYPE.get(rule_type, "manual_review_v1"),
                "executor_class": EXECUTOR_BY_RULE_TYPE.get(rule_type, "ManualReviewRule"),
                "policy_basis": "国家医保智能监管两库官方公开附件",
                "source_file": row["source_file"],
                "source_sheet": row["sheet_name"],
                "version": "national_public_batches_1_18_2026-07-10",
                "status": "draft",
                "effective_from": None,
                "effective_to": None,
            }
        )

    with jsonl_path.open("w", encoding="utf-8") as f:
        for item in definitions:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    by_type: dict[str, int] = {}
    for item in definitions:
        by_type[item["rule_type"]] = by_type.get(item["rule_type"], 0) + 1

    lines = [
        "# 规则定义导出报告",
        "",
        f"规则定义数量：{len(definitions)}",
        "",
        "## 按规则类型统计",
        "",
        "| rule_type | 数量 | executor | sql_template |",
        "|---|---:|---|---|",
    ]
    for rule_type, count in sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(
            f"| {rule_type} | {count} | {EXECUTOR_BY_RULE_TYPE.get(rule_type, 'ManualReviewRule')} | {SQL_TEMPLATE_BY_RULE_TYPE.get(rule_type, 'manual_review_v1')} |"
        )
    lines.extend(
        [
            "",
            "## 注意",
            "",
            "当前导出是工作表级规则定义草案，下一步需要按每个 Excel 的表结构展开到 item 级规则明细。",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"definitions={len(definitions)}")
    print(jsonl_path)
    print(md_path)


if __name__ == "__main__":
    main()
