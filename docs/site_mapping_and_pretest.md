# 现场映射与前期测试补充说明

## 1. 本次补齐内容

根据《医保飞检智能检索项目架构与前期开发任务》收敛版要求，本次补齐第一阶段最关键的现场适配基础能力：

- 规则最低字段需求矩阵；
- 核心字段别名推荐；
- 项目编码和项目名称匹配；
- 轻量只读探测；
- 基于现场映射配置生成查询；
- 双 Schema 样例测试。

这些能力服务于主线：

```text
国家规则标准化
  -> 现场核心表和字段映射
  -> 项目编码匹配
  -> 生成映射配置
  -> 受控 SQL
  -> 只读数据库查询
  -> H5 返回结果
```

## 2. 新增模块

```text
backend/app/core/site_mapping.py
```

主要函数：

- `recommend_field_mapping(columns)`：根据字段名、别名、中文名推荐标准字段映射；
- `match_project_codes(national_items, site_items)`：国家项目与现场项目编码/名称匹配；
- `required_field_matrix()`：返回各类规则最低字段需求；
- `probe_sqlite_mapping(db_path, table_mapping, field_mapping)`：对映射配置做轻量探测；
- `execute_duplicate_charge_with_mapping(...)`：验证同一规则通过不同现场映射执行。

## 3. 双 Schema 测试

新增测试：

```text
tests/test_site_mapping.py
```

测试构造两套 SQLite：

标准 Schema：

```text
settlement_main.settlement_id
fee_detail.item_code
fee_detail.item_name
fee_detail.quantity
fee_detail.amount
fee_detail.fee_time
```

地方 Schema：

```text
js_main.jslsh
mx_fee.xmbm
mx_fee.xmmc
mx_fee.sl
mx_fee.je
mx_fee.fssj
```

同一条重复收费规则：

```text
急诊监护费 001103000010000
急诊诊查费 001102000030000
```

在两套 Schema 下通过不同映射配置得到相同结果：

```text
hit_count = 1
total_amount = 120
```

## 4. 当前边界

当前只做第一阶段最小能力，不做：

- 多数据库通用平台；
- 映射审批流；
- 复杂大模型编排；
- 自动处理复杂一对多、多对一项目映射。

少量不确定字段和项目映射由现场人工确认。

## 5. 下一步

建议下一步继续补：

- H5 表选择和字段映射页面；
- 映射配置保存到 `site_mapping/`；
- 规则模板全部改为读取标准字段和映射配置；
- 项目编码匹配结果导出 CSV；
- 轻量探测结果返回 H5。