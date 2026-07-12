# 最小后端 API

## 1. 启动

```powershell
python backend/app/server.py
```

当前服务地址：

```text
http://127.0.0.1:8010
```

## 2. 接口

### 健康检查

```text
GET /health
```

返回：

```json
{
  "status": "ok",
  "service": "medical-insurance-flying-check-api"
}
```

### 统计

```text
GET /api/v1/stats
```

当前返回：

```json
{
  "policy_chunks": 334,
  "rule_items": 11770,
  "rule_definitions": 43
}
```

### 政策 RAG 检索

```text
GET /api/v1/policy/search?query=医保支付
```

### 规则检索

```text
GET /api/v1/rules/search?query=重复收费
```

### 查询预览

```text
POST /api/v1/query/preview
```

请求：

```json
{
  "question": "查询急诊监护费和急诊诊查费是否存在重复收费"
}
```

当前能力：

- 推断候选规则类型；
- 检索医保政策 chunk；
- 检索代码化规则 item；
- 返回专家确认前的预览结果；
- 不直接生成或执行 SQL。

## 3. 设计边界

当前 API 是 MVP 串联服务，用于验证：

```text
专家问题 → RAG 检索 → 规则候选 → 专家确认前预览
```

后续在专家确认后，才进入：

```text
规则执行器 → SQL 模板 → 只读数据库查询
```

### 查询确认并生成受控 SQL

```text
POST /api/v1/query/confirm
```

请求：

```json
{
  "item_rule_id": "NLRI-010871",
  "date_start": "2025-01-01",
  "date_end": "2026-01-01"
}
```

返回内容包括：

- 选中的规则 item；
- SQL 模板 ID；
- 受控 SQL；
- SQL 参数；
- 输出字段；
- 安全边界。

当前支持生成 SQL 的规则类型：

```text
duplicate_charge
gender_limit
age_limit
```

注意：该接口只生成 SQL，不执行 SQL。

### 模拟执行

```text
POST /api/v1/query/mock-execute
```

请求：

```json
{
  "item_rule_id": "NLRI-010871",
  "date_start": "2025-01-01",
  "date_end": "2026-01-01"
}
```

返回内容包括：

- mock 任务号；
- 汇总指标；
- 机构排名；
- 月度趋势；
- 疑点明细样例；
- 生成的受控 SQL；
- SQL 安全校验结果。

注意：该接口用于 MVP 演示和联调，`execution.sql_executed = false`，不连接真实医保数据库。

### SQL 安全校验

```text
POST /api/v1/sql/validate
```

当前校验边界：

- 只允许单条 `SELECT`；
- 不允许 DDL/DML；
- 只允许白名单表和字段；
- 日期参数必须存在；
- 敏感字段必须脱敏后输出。
### 任务详情

```text
GET /api/v1/tasks/{task_id}
```

返回指定任务的执行结果，包括规则、SQL、校验结果、汇总、图表和疑点明细样例。

### 任务导出

```text
GET /api/v1/tasks/{task_id}/export
```

当前返回 CSV，包含疑点明细样例字段：机构、患者脱敏 ID、就诊 ID、结算 ID、规则类型、项目编码、项目名称、金额、命中原因。

注意：当前导出仍是 mock 结果；接真实医保库后，该接口保留不变，数据来源切换为真实任务结果。
### 真实只读执行

```text
POST /api/v1/query/execute
```

该接口在专家确认和 SQL 安全校验通过后，调用只读数据库连接执行受控 SQL。未配置 `config/database.local.json` 时返回 `database_not_configured`，不会执行查询。

当前本地样例库验证结果：

```text
status = completed_real
execution.sql_executed = true
```

### 快速查询

```text
GET /api/v1/quick-search?query=急诊监护费&library=all&limit=8
```

`library` 支持：

- `all`
- `charge_item_catalog`
- `rule_item`
- `policy_document`
- `source_asset`

用于按老师要求查询四类库：收费项目代码库、规则库、政策依据库、原始资料台账库。

### 证据图谱

```text
GET /api/v1/evidence/graph?item_rule_id=NLRI-010871
```

返回 `nodes` 和 `edges`，当前是轻量关系层，不依赖 Neo4j。执行任务结果中也会返回 `evidence_graph` 字段。
