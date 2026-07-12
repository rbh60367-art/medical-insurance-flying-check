# 当前进度

## 已完成

### 1. 项目骨架

已在 `D:\iwen_codex\codex_shop\medical-insurance-flying-check` 建立项目骨架：

- `docs`
- `assets_manifest`
- `data_ingestion`
- `rule_engine`
- `rag_knowledge_base`
- `database`
- `backend`
- `frontend`
- `tests`
- `deployment`

### 2. 资料资产台账

已将以下资料纳入资产台账：

- 医保飞检架构文档；
- 本省政策文件 ZIP；
- 国家医保智能监管两库 ZIP。

资产统计：

```text
资产总数：353
国家两库规则来源：26
医保 RAG 候选文档：84
待转换/解压文件：25
表格类项目/价格/附件候选：143
```

关键文件：

- `assets_manifest/raw_assets.csv`
- `assets_manifest/asset_summary.md`
- `assets_manifest/conversion_queue.csv`
- `assets_manifest/rag_processing_plan.md`

### 3. 国家两库规则检查

已抽取 26 个 Excel 的 43 个工作表。

推断规则类型：

```text
indication_limit        14
age_limit                6
encounter_type_limit     4
insurance_type_limit     4
gender_limit             3
treatment_course_limit   3
frequency_limit          2
institution_level_limit  2
payment_scope_limit      2
second_line_drug_limit   2
duplicate_charge         1
```

关键文件：

- `assets_manifest/national_rule_excel_inspection.md`
- `assets_manifest/national_rule_excel_inspection.csv`

### 4. 规则定义草案

已生成 43 条工作表级规则定义草案。

关键文件：

- `database/seeds/national_rule_definitions_draft.jsonl`
- `assets_manifest/national_rule_definitions_export.md`

### 5. 优先规则 item 明细

已优先导出 3 类规则：

- `gender_limit`
- `age_limit`
- `duplicate_charge`

linked item 统计：

```text
linked item 数量：11770
gender_limit：6472
age_limit：4398
duplicate_charge：900
```

关键文件：

- `assets_manifest/linked_priority_rule_items.csv`
- `database/seeds/linked_priority_rule_items_draft.jsonl`
- `assets_manifest/linked_priority_rule_items_export.md`

## 需要注意

`linked_priority_rule_items_draft.jsonl` 已经比原始抽取更接近可执行规则：

- 性别、年龄类规则尽量将“知识点明细”和“对应药品代码表”按知识点序号合并。
- 重复收费类规则已按 A/B 项目对导出，`item_code` 形式为 `项目A代码|项目B代码`。

当前仍是 draft 状态，后续需要：

- 根据真实医保数据库字段做编码映射；
- 根据专家确认规则口径补充有效期、排除条件和适用范围；
- 将 item 明细导入数据库表；
- 用金标准案例回归测试。

## 下一步

建议顺序：

1. 建立 item 级规则入库 SQL 或导入脚本。
2. 为 3 类优先规则补齐 SQL 模板和执行器测试。
3. 开始本省政策 RAG 第一批解析：PDF、DOCX、XLSX、XLS。
4. 建立 WPS、ET、DOC、RAR 转换队列处理方案。
5. 准备 5 个专家问题做端到端验证。


## 2026-07-12 追加：医保 RAG 草案

已生成医保 RAG 第一批文档和 chunk 草案：

```text
policy_documents：84
policy_chunks：254
```

解析状态：

```text
parsed：24
needs_pdf_text_extractor：58
needs_xls_converter：2
```

关键文件：

- `database/seeds/policy_documents_draft.jsonl`
- `database/seeds/policy_chunks_draft.jsonl`
- `database/seeds/003_seed_policy_rag_drafts.sql`
- `assets_manifest/policy_rag_draft_export.md`
- `docs/policy_rag_import.md`

已补充本地关键词检索脚本：

- `rag_knowledge_base/retrieval/simple_search.py`

当前限制：PDF 正文提取需要后续接入 PDF extractor；当前先保留标题、文号、来源和处理状态。

## 2026-07-12 追加：PDF 提取与后端 API

已接入 PDF 文本提取：

- 优先使用 `pypdf`；
- 失败时回退 `pdfplumber`；
- MVP 阶段每个 PDF 最多抽取前 15 页；
- 成功将 RAG chunk 从 254 提升到 334。

当前 RAG 解析状态：

```text
parsed：31
needs_pdf_text_extractor：51
needs_xls_converter：2
```

已搭建最小后端 API：

```text
backend/app/server.py
http://127.0.0.1:8010
```

已验证接口：

- `GET /health`
- `GET /api/v1/stats`
- `GET /api/v1/policy/search`
- `GET /api/v1/rules/search`
- `POST /api/v1/query/preview`

示例问题：

```text
查询急诊监护费和急诊诊查费是否存在重复收费
```

接口能识别候选规则类型 `duplicate_charge`，并返回对应 A/B 项目对规则。

## 2026-07-12 追加：专家确认后生成受控 SQL

已新增接口：

```text
POST /api/v1/query/confirm
```

已验证示例：

```text
item_rule_id = NLRI-010871
急诊监护费|急诊诊查费
```

生成 SQL 模板：

```text
duplicate_charge_pair_v1
```

安全边界：

```text
only_select = true
uses_template = true
requires_readonly_connection = true
requires_expert_confirmation = true
executes_sql = false
```

当前支持 SQL 生成的规则类型：

- `duplicate_charge`
- `gender_limit`
- `age_limit`

## 2026-07-12 追加：H5 查询闭环

已新增 H5 页面：

```text
frontend/index.html
http://127.0.0.1:8010/h5
```

当前页面支持：

- 输入专家问题；
- 调用 `/api/v1/query/preview`；
- 展示候选规则；
- 展示政策 RAG 命中；
- 选择候选规则；
- 调用 `/api/v1/query/confirm`；
- 展示受控 SQL 和参数。

已通过 HTTP 验证 H5 能返回 HTML，API 统计接口正常。

## 2026-07-12 追加：字段映射与 SQL 安全校验

已新增字段映射配置：

```text
config/field_mapping.json
```

已新增 SQL 安全校验器：

```text
backend/app/core/sql_safety.py
```

已接入接口：

- `POST /api/v1/query/confirm` 自动返回 `sql_validation`；
- `POST /api/v1/sql/validate` 支持独立校验。

已验证 `NLRI-010871` 生成的重复收费 SQL：

```text
sql_validation.valid = true
```

已新增测试：

```text
tests/test_sql_safety.py
```

最小测试已通过：

```text
minimal tests passed
```

## 2026-07-12 追加：模拟执行与 H5 结果页

已新增模拟执行器：

```text
backend/app/core/mock_executor.py
```

已新增接口：

```text
POST /api/v1/query/mock-execute
```

当前闭环已扩展为：

```text
专家问题 → 规则/RAG 预览 → 专家确认 → 生成受控 SQL → SQL 安全校验 → 模拟执行结果
```

已验证示例规则：

```text
item_rule_id = NLRI-010871
急诊监护费|急诊诊查费
```

模拟执行返回：

- 任务号；
- 机构数、患者数、结算人次、明细数、疑点金额；
- 机构排名；
- 月度趋势；
- 疑点明细样例；
- SQL 校验结果。

重要边界：当前是 mock 模式，`sql_executed = false`，不会连接真实医保数据库。

H5 已新增“模拟执行”和“模拟结果”区域，可直接打开：

```text
http://127.0.0.1:8010/h5
```

已新增测试：

```text
tests/test_mock_executor.py
```

当前验证结果：

```text
minimal tests passed
GET /health = ok
POST /api/v1/query/mock-execute = completed_mock
```

## 2026-07-12 追加：任务记录与 CSV 导出

已新增任务追踪能力：

```text
GET /api/v1/tasks/{task_id}
GET /api/v1/tasks/{task_id}/export
```

当前实现：

- 模拟执行后生成稳定 `task_id`；
- 任务结果写入内存，并追加到 `backend/runtime/task_runs.jsonl`；
- 可按任务号重新读取详情；
- 可导出疑点明细 CSV；
- H5 页面已增加“查看任务”和“导出 CSV”。

已补充正式数据库迁移草案：

```text
database/migrations/004_task_runs_and_exports.sql
```

验证结果：

```text
POST /api/v1/query/mock-execute = completed_mock
GET /api/v1/tasks/MOCK-B5603F2BF3AA = completed_mock
GET /api/v1/tasks/MOCK-B5603F2BF3AA/export = CSV
minimal tests passed
```

## 2026-07-12 追加：真实只读数据库执行层

已新增只读数据库执行器：

```text
backend/app/core/db_executor.py
```

已新增配置模板：

```text
config/database.example.json
```

已新增接口：

```text
POST /api/v1/query/execute
```

安全行为：

- 未配置 `config/database.local.json` 时返回 `database_not_configured`；
- 配置必须启用 `readonly = true`；
- 执行前仍经过 SQL 安全校验；
- 查询结果写入任务记录，并支持任务详情和 CSV 导出。

已新增样例库脚本：

```text
database/seeds/create_sample_claims_sqlite.py
```

已用样例 SQLite 验证真实执行链路：

```text
status = completed_real
execution.sql_executed = true
row_count = 1
```

H5 已增加“真实执行”按钮，与“模拟执行”并行。

## 2026-07-12 追加：真实结算数据导入通道

项目当前没有真实医保结算数据文件，只有样例库。已补齐真实数据接入通道：

```text
data/claims_import/inbox
data/claims_import/templates
data/claims_import/output
config/claims_import_mapping.example.json
data_ingestion/import_claims_to_sqlite.py
docs/real_claims_data_import.md
```

支持：

- CSV 导入；
- XLSX 导入；
- 中文表头别名映射；
- 生成 SQLite 只读执行库；
- 自动更新 `config/database.local.json`；
- H5 顶部显示当前结算主表和费用明细表行数；
- `GET /api/v1/database/status` 查看数据库状态。

已新增测试：

```text
tests/test_claims_importer.py
```

验证结果：

```text
真实导出 CSV → SQLite → 只读执行器 → completed_real
minimal tests passed
```

## 2026-07-12 追加：快速查询库与证据图谱

已按下一步方案补充第一版快速查询库和证据关系层。

新增后端模块：

```text
backend/app/core/quick_query.py
backend/app/core/evidence_graph.py
```

新增接口：

```text
GET /api/v1/quick-search
GET /api/v1/evidence/graph
```

已接入：

- `/api/v1/query/preview` 返回候选 `evidence_graph`；
- `/api/v1/query/confirm` 返回规则证据链；
- mock/真实执行任务结果返回含 `Finding` 的证据链；
- H5 增加“快速查询”和“依据链 / 证据图谱”节点连线可视化；
- 新增关系层迁移草案 `database/migrations/005_quick_query_and_evidence_graph.sql`。

当前边界：收费项目代码库仍是资产级快速查询，完整项目代码、价格、支付类别结构化是下一步。
