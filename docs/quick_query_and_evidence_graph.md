# 快速查询库与证据图谱说明

## 当前改动

本项目已按下一步方案补充第一版快速查询库和证据关系层。

新增接口：

```text
GET /api/v1/quick-search?query=急诊监护费&library=all&limit=8
GET /api/v1/evidence/graph?item_rule_id=NLRI-010871
```

查询范围：

- `charge_item_catalog`：收费项目、价格、目录类资产快速查询
- `rule_item`：国家两库规则 item 查询
- `policy_document`：政策 chunk 查询
- `source_asset`：原始资料台账查询
- `all`：综合查询

## 证据图谱当前形态

当前不是 Neo4j 图数据库，而是轻量关系层。API 返回统一结构：

```json
{
  "nodes": [],
  "edges": []
}
```

已支持的实体：

- `RuleItem`
- `RuleDefinition`
- `ChargeItem`
- `ChargeCode`
- `SourceAsset`
- `QueryTask`
- `Finding`
- `PolicyDocument`
- `PolicyClause`

已支持的关系：

- `belongs_to`
- `applies_to`
- `has_code`
- `derived_from`
- `has_finding`
- `triggered_by`
- `part_of`
- `mentions`

## 示例

```text
NLRI-010871
急诊监护费|急诊诊查费
```

可形成：

```text
RuleItem -> applies_to -> ChargeItem -> has_code -> ChargeCode
RuleItem -> derived_from -> SourceAsset
QueryTask -> has_finding -> Finding -> triggered_by -> RuleItem
```

## 边界

- 当前收费项目代码库仍是“目录/价格资产级查询”，还没有完成所有项目代码、价格、支付类别的结构化抽取。
- 当前证据链可解释规则来源和涉及项目，但价格版本与政策条款关联仍需后续结构化收费项目库后补齐。
- 查询结果是疑点线索，不是违规结论。

## 后续建设

下一步应优先处理：

1. 解析诊疗项目目录和医疗服务价格调整附件。
2. 建立 `charge_items`、`charge_codes`、`price_versions` 数据。
3. 将政策条款和附件表格建立 `based_on` / `mentions` 关系。
4. 在 H5 中把节点和关系做成可视化链路，而不只是数量摘要。