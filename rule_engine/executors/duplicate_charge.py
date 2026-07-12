from __future__ import annotations

from rule_engine.executors.base import QueryContext, RuleDefinition, SqlBuildResult
from rule_engine.templates.registry import render_template


class DuplicateChargeRule:
    rule_type = "duplicate_charge"

    def build_sql(self, rule: RuleDefinition, context: QueryContext) -> SqlBuildResult:
        sql, parameters = render_template(
            rule.sql_template_id,
            {
                "item_codes": rule.target_codes,
                "date_start": context.date_start,
                "date_end": context.date_end,
                "threshold": rule.condition.get("threshold", 1),
                "aggregation_scope": rule.condition.get("aggregation_scope", "encounter_id"),
            },
        )
        return SqlBuildResult(
            rule_id=rule.rule_id,
            sql_template_id=rule.sql_template_id,
            sql=sql,
            parameters=parameters,
            output_columns=[
                "institution_code",
                "patient_id_masked",
                "encounter_id",
                "item_code",
                "item_name",
                "charge_count",
                "amount",
            ],
            explanation_template="同一聚合范围内项目收费次数超过规则阈值，形成重复收费疑点。",
        )
