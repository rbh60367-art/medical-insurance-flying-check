# 优先规则 item 入库说明

## 1. 文件

优先规则 linked item 明细：

```text
assets_manifest/linked_priority_rule_items.csv
```

JSONL 种子：

```text
database/seeds/linked_priority_rule_items_draft.jsonl
```

SQL 导入文件：

```text
database/seeds/002_seed_linked_priority_rule_items.sql
```

## 2. 入库顺序

先执行表结构：

```text
database/migrations/001_core_assets_rules_rag.sql
```

再执行种子数据：

```text
database/seeds/002_seed_linked_priority_rule_items.sql
```

## 3. 当前数据规模

```text
linked item：11770
 gender_limit：6472
 age_limit：4398
 duplicate_charge：900
```

## 4. 当前状态

所有导出的 item 目前状态为：

```text
draft
```

后续需要专家或规则管理员确认后再改为：

```text
active
```

## 5. 注意事项

- 性别、年龄类规则已尽量按知识点序号合并规则明细和药品代码。
- 重复收费类规则使用 A/B 项目对，`item_code` 格式为 `项目A代码|项目B代码`。
- 这些编码仍需与本省医保目录和医院数据库实际编码建立映射后，才能用于真实 SQL 查询。
- 规则命中只代表疑点，不代表最终违规结论。

## 6. 最小测试

```powershell
$env:PYTHONPATH="D:\iwen_codex\codex_shop\medical-insurance-flying-check"
python D:\iwen_codex\codex_shop\medical-insurance-flying-check\tests\run_minimal_tests.py
```
