# 医保 RAG 与文档转换处理计划

## 总览

- RAG 候选文档：84
- 待转换/解压文件：25
- 表格类项目/价格/附件候选：143

## RAG 候选文档格式

| 项 | 数量 |
|---|---:|
| .pdf | 58 |
| .docx | 11 |
| .xlsx | 11 |
| .md | 2 |
| .xls | 2 |

## 待转换格式

| 项 | 数量 |
|---|---:|
| .wps | 14 |
| .doc | 8 |
| .et | 2 |
| .rar | 1 |

## 表格类候选分类

| 项 | 数量 |
|---|---:|
| project_catalog_or_price | 143 |

## 处理批次

### 第一批：可直接解析

- PDF：抽正文、页码、标题、文号，进入 policy_documents / policy_chunks。
- DOCX：抽正文和标题，进入 policy_documents / policy_chunks。
- XLSX/XLS：先判断是项目清单、价格目录、政策附件还是普通说明表。

### 第二批：需要转换

- WPS：转换为 DOCX 或 PDF 后进入 RAG。
- DOC：转换为 DOCX 或 PDF 后进入 RAG。
- ET：转换为 XLSX 后重新分类。
- RAR：解压后重新登记资产台账。

## 输出要求

每个 RAG chunk 必须带来源：标题、文号、发文日期、原始路径、页码或附件名。

## 待转换样例

| asset_id | file_ext | file_name | parse_status |
|---|---|---|---|
| A000035 | .rar | 33批发文稿.rar | needs_convert |
| A000062 | .doc | 青海省新增医疗服务价格项目申报材料.doc | needs_convert |
| A000074 | .doc | 关于调整放射检查类等医疗服务价格项目及医保支付类别的补充通知.doc | needs_convert |
| A000132 | .doc | 青医保局发〔2023〕83号（关于印发青海省医疗保障定点医药机构服务协议（2024版）的通知）.doc | needs_convert |
| A000143 | .wps | 青医保办发23号（6个谈判药新增规格）不予公开.wps | needs_convert |
| A000145 | .wps | 青医保办发36号.wps | needs_convert |
| A000148 | .wps | 青医保办发〔2024〕55号（关于认定部分药品医保目录归属的通知）-不予公开.wps | needs_convert |
| A000150 | .wps | 青医保办发〔2024〕57号（关于复方氨基酸注射液（14AA-SF）等3个药品新增规格及医保支付标准的通知）—不予公开.wps | needs_convert |
| A000152 | .et | 附件.et | needs_convert |
| A000153 | .wps | 青医保办发〔2024〕92号（关于确定国家集中带量采购中选品种同通用名药品医保支付标准的通知）.wps | needs_convert |
| A000167 | .wps | 青医保局发〔2024〕84号.wps | needs_convert |
| A000169 | .doc | 青医保局发〔2024〕85号.doc | needs_convert |
| A000173 | .wps | 青医保办发〔2025〕19号（关于认定部分药品医保目录归属的通知）—不予公开.wps | needs_convert |
| A000175 | .wps | 青医保办发〔2025〕22号（关于转发《国家医疗保障局办公室关于注射用盐酸兰地洛尔等4个药品新增规格及支付标准的通知》的通知）—不予公开.wps | needs_convert |
| A000178 | .wps | 青医保办发〔2025〕40号（关于拓培非格司亭注射液等2个药品新增规格及医保支付标准的通知—不予公开）.wps | needs_convert |
| A000180 | .et | 附件1调出医保药品目录制剂目录.et | needs_convert |
| A000183 | .wps | （青医保办发〔2025〕45号）青海省医疗保障局办公室关于将部分医疗机构制剂品种调出医疗机构制剂医保目录的通知.wps | needs_convert |
| A000196 | .wps | 青医保局发〔2024〕16号（门诊慢特病目录通知）.wps | needs_convert |
| A000204 | .doc | 8.1青医保办发〔2024〕69号（关于调整全省按病组和按病种分值付费分组方案的通知）.doc | needs_convert |
| A000214 | .wps | 青医保办发〔2025〕11号（关于调整按病组和按病种分值付费有关事项的通知）.wps | needs_convert |
| A000217 | .wps | 青医保办发〔2025〕17号（关于动态调整按病组和病种分值付费费率点值及完善付费政策的通知）.wps | needs_convert |
| A000219 | .wps | 青医保办发〔2025〕41号（关于调整按病种付费有关政策的通知）.wps | needs_convert |
| A000255 | .doc | 青海省新增医疗服务价格项目申报材料.doc | needs_convert |
| A000267 | .doc | 关于调整放射检查类等医疗服务价格项目及医保支付类别的补充通知.doc | needs_convert |
| A000324 | .doc | 青医保局发〔2023〕83号（关于印发青海省医疗保障定点医药机构服务协议（2024版）的通知）.doc | needs_convert |
