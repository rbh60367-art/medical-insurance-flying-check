# 原始资料处理方案

## 1. 输入资料

| 资料 | 当前路径 | 用途 |
|---|---|---|
| 架构设计 MD | `C:/Users/21403/Desktop/医保飞检智能检索_H5_MVP_架构设计方案.md` | 项目蓝图，纳入 docs |
| 本省政策 ZIP | `C:/Users/21403/Desktop/政策文件（本省）.zip` | 医保 RAG、项目清单、价格目录、地方口径 |
| 国家两库 ZIP | `C:/Users/21403/Desktop/国家医保智能监管两库_官方公开附件_第一至十八批_截至2026-07-10.zip` | 代码化规则库 |

## 2. 核心处理原则

所有资料都要使用，但不是同一种处理方式。

```text
国家两库 ZIP
    → 结构化规则库
    → 代码化规则执行器
    → SQL 模板

本省政策 ZIP
    → 医保 RAG 知识库
    → 项目清单 / 价格目录结构化
    → 政策依据引用

架构 MD
    → 项目文档
    → v2 架构修订基线
```

## 3. 文件分类

| 类别 | 来源 | 进入模块 |
|---|---|---|
| 规则表 | 国家两库 Excel | rule_engine |
| 政策正文 | 本省 PDF/DOCX/DOC/WPS | rag_knowledge_base |
| 政策附件表格 | 本省 XLS/XLSX/ET | data_ingestion 后分类 |
| 医疗服务价格目录 | 本省 XLS/XLSX/ET | 项目清单库 + 可选 RAG |
| 压缩包内文件 | RAR | 解压后重新分类 |
| 架构文档 | MD | docs |

## 4. 转换策略

| 格式 | 转换目标 | 后续处理 |
|---|---|---|
| WPS | DOCX 或 PDF | 正文解析、RAG 切片 |
| ET | XLSX | 表格抽取、结构化分类 |
| DOC | DOCX 或 PDF | 正文解析、RAG 切片 |
| RAR | 解压目录 | 重新进入文件台账 |
| PDF | 文本 + 表格 | RAG 切片 |
| XLS/XLSX | 表格数据 | 规则库、项目清单或附件知识 |

转换失败的文件不丢弃，进入 `parse_status = failed`，记录失败原因，等待人工转换或补录。

## 5. 文件台账字段

```yaml
asset_id:
source_package:
original_path:
file_name:
file_ext:
file_size:
content_hash:
category:
target_module:
convert_required:
converted_path:
parse_status:
parse_error:
created_at:
updated_at:
```

## 6. 分类状态

```text
raw_registered       已登记
needs_extract        待解压
needs_convert        待转换
converted            已转换
classified           已分类
parsed               已解析
indexed              已入索引
rule_loaded          已进入规则库
manual_review        待人工确认
failed               处理失败
```
