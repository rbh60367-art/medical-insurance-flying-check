from __future__ import annotations

from rule_engine.executors.base import QueryContext, RuleDefinition, SqlBuildResult
from rule_engine.templates.registry import render_template


class AgeLimitRule:
    rule_type = "age_limit"

    def build_sql(self, rule: RuleDefinition, context: QueryContext) -> SqlBuildResult:
        sql, parameters = render_template(
            rule.sql_template_id,
            {
                "item_codes": rule.target_codes,
                "date_start": context.date_start,
                "date_end": context.date_end,
                "min_age": rule.condition.get("min_age"),
                "max_age": rule.condition.get("max_age"),
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
                "patient_age",
                "amount",
            ],
            explanation_template="项目命中年龄限制规则，患者年龄超出规则允许范围。",
        )
