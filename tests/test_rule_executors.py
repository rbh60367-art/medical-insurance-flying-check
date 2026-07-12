from rule_engine.executors import AgeLimitRule, DuplicateChargeRule, GenderLimitRule
from rule_engine.executors.base import QueryContext, RuleDefinition


def test_gender_limit_builds_sql():
    rule = RuleDefinition(
        rule_id="R-GENDER-1",
        rule_code="gender_limit_demo",
        rule_name="药品区分性别使用",
        rule_type="gender_limit",
        target_type="drug",
        target_codes=["XL02BBA326A001010102180"],
        condition={"allowed_gender": "男"},
        sql_template_id="gender_limit_v1",
        version="v1",
        source_file="第一批-1_药品区分性别使用.xlsx",
    )
    result = GenderLimitRule().build_sql(rule, QueryContext("2025-01-01", "2026-01-01"))
    assert result.rule_id == "R-GENDER-1"
    assert "fd.hilist_code = ANY(:item_codes)" in result.sql
    assert result.parameters["allowed_gender"] == "男"


def test_age_limit_builds_sql():
    rule = RuleDefinition(
        rule_id="R-AGE-1",
        rule_code="age_limit_demo",
        rule_name="药品儿童专用",
        rule_type="age_limit",
        target_type="drug",
        target_codes=["ZD03AAA0043010100166"],
        condition={"min_age": None, "max_age": 14},
        sql_template_id="age_limit_v1",
        version="v1",
        source_file="第一批-3_药品儿童专用.xlsx",
    )
    result = AgeLimitRule().build_sql(rule, QueryContext("2025-01-01", "2026-01-01"))
    assert result.parameters["max_age"] == 14
    assert "sm.age" in result.sql


def test_duplicate_charge_builds_sql():
    rule = RuleDefinition(
        rule_id="R-DUP-1",
        rule_code="duplicate_charge_demo",
        rule_name="医疗服务项目重复收费",
        rule_type="duplicate_charge",
        target_type="medical_service_pair",
        target_codes=["001103000010000", "001102000030000"],
        condition={"threshold": 1, "aggregation_scope": "encounter_id"},
        sql_template_id="duplicate_charge_v1",
        version="v1",
        source_file="第七批_医疗服务项目重复收费.xlsx",
    )
    result = DuplicateChargeRule().build_sql(rule, QueryContext("2025-01-01", "2026-01-01"))
    assert result.parameters["threshold"] == 1
    assert "HAVING COUNT(*) > :threshold" in result.sql
