# 国家两库规则 Schema 映射草案

## 1. 目标

把国家医保智能监管两库 Excel 转换为可执行规则库。

转换结果不是普通文档切片，而是进入以下结构：

```text
rule_definitions
rule_items
rule_parameters
rule_sql_templates
golden_cases
```

## 2. 通用规则定义

```yaml
rule_id: 规则唯一 ID
rule_code: 程序内规则编码
rule_name: 规则名称
rule_type: 规则类型
target_type: drug / medical_service / chinese_medicine / consumable
target_codes: 规则适用项目编码
target_names: 规则适用项目名称
condition: 规则条件
sql_template_id: SQL 模板 ID
executor_class: 规则执行器
policy_basis: 政策依据
source_file: 来源 Excel
version: 版本
status: draft / active / disabled
effective_from: 生效日期
effective_to: 失效日期
```

## 3. 规则类型映射

| 国家两库文件特征 | rule_type | executor_class | SQL 模板 |
|---|---|---|---|
| 区分性别使用 | gender_limit | GenderLimitRule | gender_limit_v1 |
| 儿童专用 / 限儿童 / 限年龄 | age_limit | AgeLimitRule | age_limit_v1 |
| 限定频次 / 周期超频次 | frequency_limit | FrequencyLimitRule | frequency_limit_v1 |
| 重复收费 | duplicate_charge | DuplicateChargeRule | duplicate_charge_v1 |
| 限支付疗程 | treatment_course_limit | TreatmentCourseLimitRule | treatment_course_limit_v1 |
| 限医疗机构级别 | institution_level_limit | InstitutionLevelLimitRule | institution_level_limit_v1 |
| 限就医方式 / 互联网医院 | encounter_type_limit | EncounterTypeLimitRule | encounter_type_limit_v1 |
| 限适应症 | indication_limit | IndicationLimitRule | indication_limit_v1 |
| 限工伤保险 / 限生育保险 | insurance_type_limit | InsuranceTypeLimitRule | insurance_type_limit_v1 |
| 不予支付 / 支付范围 | payment_scope_limit | PaymentScopeLimitRule | payment_scope_limit_v1 |

## 4. MVP 优先级

第一批实现：

1. `gender_limit`
2. `age_limit`
3. `duplicate_charge`

第二批实现：

1. `frequency_limit`
2. `treatment_course_limit`
3. `institution_level_limit`
4. `encounter_type_limit`

第三批实现：

1. `indication_limit`
2. `insurance_type_limit`
3. `payment_scope_limit`

## 5. 转换后的执行边界

- Excel 原始内容必须保留来源文件。
- 每条规则必须有版本。
- 每条规则必须绑定执行器。
- 每条规则必须绑定 SQL 模板。
- 规则执行前必须经过专家确认。
- 规则命中只表示疑点，不表示最终违规。
