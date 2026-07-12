# 真实医保结算数据接入说明

## 当前状态

项目已经支持把真实医保结算导出文件导入为本地 SQLite 只读库，再通过 H5 的“真实执行”按钮执行规则。

当前项目里还没有真实结算数据。现有 `database/sample_claims.db` 是样例库，只用于验证流程。

## 需要准备的两类文件

放到目录：

```text
data/claims_import/inbox
```

建议文件名：

```text
settlement_main.csv
fee_detail.csv
```

也支持 `.xlsx`。

### 1. 结算主表 settlement_main

模板：

```text
data/claims_import/templates/settlement_main_template.csv
```

目标字段：

```text
setl_id, mdtrt_id, fixmedins_code, psn_no, gend, age, fund_pay_sumamt, setl_time
```

### 2. 费用明细表 fee_detail

模板：

```text
data/claims_import/templates/fee_detail_template.csv
```

目标字段：

```text
setl_id, mdtrt_id, hilist_code, hilist_name, cnt, pric, det_item_fee_sumamt, fee_ocur_time
```

## 字段映射

复制映射模板：

```text
config/claims_import_mapping.example.json
```

如真实导出的字段名不同，在 `columns` 里增加别名即可。例如：

```json
"setl_id": ["setl_id", "结算流水号", "结算ID", "结算单据号"]
```

导入器会按别名自动匹配真实文件表头。

## 导入命令

```powershell
& "C:\Users\21403\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" data_ingestion/import_claims_to_sqlite.py --mapping config/claims_import_mapping.example.json --output data/claims_import/output/claims_real.db --write-local-config
```

导入完成后会自动更新：

```text
config/database.local.json
```

然后 H5 的“真实执行”会读取：

```text
data/claims_import/output/claims_real.db
```

## 验证

启动 API 后访问：

```text
GET /api/v1/database/status
```

页面顶部也会显示：

```text
结算 N｜明细 N
```

如果仍然显示很小的数量，说明当前还在样例库或测试库。

## 安全边界

- 导入后的库按只读方式打开；
- 执行前仍需要专家确认；
- SQL 必须来自受控模板；
- `psn_no` 不直接输出，只输出脱敏 ID；
- 查询结果可查看任务详情并导出 CSV。
