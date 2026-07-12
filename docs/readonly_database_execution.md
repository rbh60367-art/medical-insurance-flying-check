# 只读数据库执行层

## 目标

把当前 MVP 从 mock 结果推进到真实医保库只读查询，同时保留安全边界：

- 专家确认后才能执行；
- SQL 必须来自受控模板；
- SQL 必须通过白名单和脱敏校验；
- 数据库连接必须是只读；
- 查询结果进入任务记录，可查看详情和导出 CSV。

## 配置

复制模板：

```text
config/database.example.json → config/database.local.json
```

当前 MVP 已支持 SQLite 只读连接：

```json
{
  "enabled": true,
  "provider": "sqlite",
  "readonly": true,
  "sqlite_path": "D:/path/to/readonly_medical_insurance.db",
  "timeout_seconds": 10,
  "max_rows": 500
}
```

真实生产库后续可以扩展 provider，例如 PostgreSQL、MySQL、ODBC。扩展时必须继续保持只读账号和 SQL 安全校验。

## 接口

```text
POST /api/v1/query/execute
```

请求：

```json
{
  "item_rule_id": "NLRI-010871",
  "date_start": "2025-01-01",
  "date_end": "2026-01-01"
}
```

未配置数据库时返回：

```json
{
  "code": "database_not_configured"
}
```

配置成功后返回：

```text
status = completed_real
execution.mode = readonly_database
execution.sql_executed = true
```

## 样例库

已提供样例 SQLite 生成脚本：

```text
database/seeds/create_sample_claims_sqlite.py
```

生成后会得到：

```text
database/sample_claims.db
```

该样例库只用于本地验证字段映射和执行链路，不代表真实医保数据。

## 当前支持规则

真实执行沿用已有 SQL 模板，目前支持：

- `duplicate_charge`
- `gender_limit`
- `age_limit`

当前已用样例库验证：

```text
item_rule_id = NLRI-010871
status = completed_real
row_count = 1
settlement_id = S001
```
