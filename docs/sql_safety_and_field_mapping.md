# 字段映射与 SQL 安全校验

## 1. 字段映射配置

配置文件：

```text
config/field_mapping.json
```

当前白名单表：

```text
settlement_main
fee_detail
```

当前敏感字段：

```text
psn_no
```

患者标识在 SELECT 中必须脱敏，例如：

```sql
md5(sm.psn_no) AS patient_id_masked
```

## 2. SQL 安全校验器

代码：

```text
backend/app/core/sql_safety.py
```

校验内容：

- SQL 必须以 SELECT 开头；
- 只允许单条语句；
- 禁止 INSERT、UPDATE、DELETE、DROP、ALTER、TRUNCATE 等关键字；
- 只允许访问白名单表；
- 只允许访问白名单字段；
- 必须包含 date_start 和 date_end 参数；
- 必须包含费用发生时间或结算时间过滤；
- 敏感字段不能明文出现在 SELECT 中。

## 3. API 接口

### 独立校验

```text
POST /api/v1/sql/validate
```

请求：

```json
{
  "sql": "SELECT ...",
  "parameters": {
    "date_start": "2025-01-01",
    "date_end": "2026-01-01"
  }
}
```

### 查询确认时自动校验

```text
POST /api/v1/query/confirm
```

返回中包含：

```json
{
  "sql_validation": {
    "valid": true,
    "errors": [],
    "warnings": [],
    "tables": [],
    "fields": []
  }
}
```

## 4. 测试

```powershell
$env:PYTHONPATH="D:\iwen_codex\codex_shop\medical-insurance-flying-check"
python tests/run_minimal_tests.py
```

当前最小测试覆盖：

- 规则执行器 SQL 生成；
- 合法 SELECT 通过；
- DELETE 被拒绝；
- 未知表被拒绝；
- 缺少 date_end 被拒绝。
