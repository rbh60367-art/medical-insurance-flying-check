# 医保飞检智能助手闭环设计

## 1. 目标

在现有医保飞检 H5 MVP 上增加“文字 + 语音交流”入口，让专家可以像聊天一样提出核查问题，系统自动完成：

1. 语音识别或文字输入；
2. 大模型理解问题意图；
3. 检索政策知识库 RAG；
4. 检索代码化规则库；
5. 生成候选检索条件；
6. 返回界面给专家确认；
7. 确认后生成受控 SQL；
8. 连接只读医保结算数据库检索；
9. 返回疑点明细、统计分析和证据图谱。

## 2. 当前入库实现

当前版本已经入库的能力：

- H5 增加“智能交流”面板；
- 支持文字输入；
- 支持浏览器 Web Speech API 语音识别，识别结果进入同一个文字聊天接口；
- 后端新增 `/api/v1/assistant/chat`；
- 聊天接口会同时检索规则库、政策知识库和四类快速查询库；
- 返回 `generated_conditions`，作为专家确认前的候选检索条件；
- 命中规则时返回 `evidence_graph`；
- 专家确认后复用现有 `/api/v1/query/confirm` 和 `/api/v1/query/execute`；
- 查询结果继续返回统计分析、疑点明细、CSV 导出和证据图谱。

## 3. 闭环流程

```text
语音/文字输入
  ↓
语音识别 ASR（浏览器或服务端）
  ↓
大模型意图理解（规则类型、项目、时间、机构、条件）
  ↓
知识库 RAG 检索（政策依据库）
  ↓
规则库检索（代码化飞检规则）
  ↓
生成候选检索条件 generated_conditions
  ↓
界面返回给专家确认
  ↓
生成受控 SQL
  ↓
只读数据库检索
  ↓
统计分析 / 疑点明细 / 证据图谱
```

## 4. 大模型接入边界

当前代码保留大模型编排位置，默认采用规则和知识库的本地可解释结果生成回复，避免没有 API Key 时无法演示。

后续接真实大模型时建议采用 OpenAI-compatible 接口：

```text
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://...
LLM_API_KEY=...
LLM_MODEL=...
```

大模型只负责理解自然语言问题、提取查询条件、组织解释性回复。大模型不允许直接执行 SQL、绕过专家确认、直接认定违规或自由拼接数据库查询语句。

## 5. 语音识别方案

第一阶段采用浏览器 Web Speech API：无需服务端模型，演示快；缺点是依赖浏览器支持。第二阶段可升级为服务端 ASR：

```text
POST /api/v1/assistant/voice/transcribe
```

输入音频文件，返回转写文本，再进入 `/api/v1/assistant/chat`。

## 6. 检索条件结构

`/api/v1/assistant/chat` 返回：

```json
{
  "generated_conditions": {
    "source": "llm_or_rule_grounded_planner",
    "query_text": "急诊监护费和急诊诊查费是否重复收费",
    "candidate_item_rule_id": "NLRI-010871",
    "candidate_rule_type": "duplicate_charge",
    "candidate_item_code": "001103000010000|001102000030000",
    "candidate_item_name": "急诊监护费|急诊诊查费",
    "date_start": "2025-01-01",
    "date_end": "2026-01-01",
    "execution_mode": "confirm_then_readonly_database_search",
    "requires_expert_confirmation": true,
    "next_api": "/api/v1/query/confirm -> /api/v1/query/execute"
  }
}
```

## 7. 与现有模块关系

- 政策知识库：`policy_chunks_draft.jsonl`；
- 规则库：`linked_priority_rule_items_draft.jsonl` + SQL 模板；
- 四类快速查询库：`backend/app/core/quick_query.py`；
- 证据图谱：`backend/app/core/evidence_graph.py`；
- SQL 安全：`backend/app/core/sql_safety.py`；
- 数据库执行：`backend/app/core/db_executor.py`。

## 8. 验收标准

- 用户可以输入文字问题并得到知识库/规则库支撑的回复；
- 用户可以点击语音按钮，完成语音转文字；
- 系统返回候选检索条件，而不是直接查库；
- 专家确认后才生成 SQL；
- SQL 只能走受控模板和只读连接；
- 查询结果包含统计分析、疑点明细和证据图谱。