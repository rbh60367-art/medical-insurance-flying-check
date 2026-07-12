# 规则定义导出报告

规则定义数量：43

## 按规则类型统计

| rule_type | 数量 | executor | sql_template |
|---|---:|---|---|
| indication_limit | 14 | IndicationLimitRule | indication_limit_v1 |
| age_limit | 6 | AgeLimitRule | age_limit_v1 |
| encounter_type_limit | 4 | EncounterTypeLimitRule | encounter_type_limit_v1 |
| insurance_type_limit | 4 | InsuranceTypeLimitRule | insurance_type_limit_v1 |
| gender_limit | 3 | GenderLimitRule | gender_limit_v1 |
| treatment_course_limit | 3 | TreatmentCourseLimitRule | treatment_course_limit_v1 |
| frequency_limit | 2 | FrequencyLimitRule | frequency_limit_v1 |
| institution_level_limit | 2 | InstitutionLevelLimitRule | institution_level_limit_v1 |
| payment_scope_limit | 2 | PaymentScopeLimitRule | payment_scope_limit_v1 |
| second_line_drug_limit | 2 | SecondLineDrugLimitRule | second_line_drug_limit_v1 |
| duplicate_charge | 1 | DuplicateChargeRule | duplicate_charge_v1 |

## 注意

当前导出是工作表级规则定义草案，下一步需要按每个 Excel 的表结构展开到 item 级规则明细。
