# 医保 RAG 草案入库说明

## 1. 当前输出

文档草案：

```text
database/seeds/policy_documents_draft.jsonl
```

切片草案：

```text
database/seeds/policy_chunks_draft.jsonl
```

SQL 入库文件：

```text
database/seeds/003_seed_policy_rag_drafts.sql
```

导出报告：

```text
assets_manifest/policy_rag_draft_export.md
```

## 2. 当前规模

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

## 3. 当前能力边界

当前环境没有 PDF 解析库，也没有 pdftotext，因此 PDF 暂时只生成文档级记录、标题、文号和占位 chunk，状态标记为：

```text
needs_pdf_text_extractor
```

DOCX、XLSX、MD 已经可以无第三方依赖抽取文本并生成 chunk。

## 4. 入库顺序

先执行表结构：

```text
database/migrations/001_core_assets_rules_rag.sql
```

再执行 RAG 种子：

```text
database/seeds/003_seed_policy_rag_drafts.sql
```

## 5. 本地检索冒烟测试

```powershell
python rag_knowledge_base/retrieval/simple_search.py `
  --chunks-jsonl database/seeds/policy_chunks_draft.jsonl `
  --query "规则库 RAG 医保 SQL" `
  --limit 3
```

## 6. 下一步

- 接入 PDF 文本提取工具或解析库。
- 将 `.xls` 转换或解析为文本/表格。
- 为 policy_chunks 增加 embedding 字段或独立向量索引表。
- 建立查询接口，返回政策标题、文号、原文片段、来源文件。
