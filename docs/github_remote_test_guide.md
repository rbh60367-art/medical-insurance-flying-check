# 远程测试说明

## 1. 启动

```powershell
python tests/run_minimal_tests.py
python backend/app/server.py
```

打开：

```text
http://127.0.0.1:8010/h5
```

## 2. 测试流程

1. 点击“解析预览”
2. 点击“确认并生成 SQL”
3. 点击“模拟执行”
4. 点击“查看任务”
5. 点击“导出 CSV”

## 3. 测试真实执行按钮

仓库不含真实医保流水。如需测试只读 SQL 执行，用样例库：

```powershell
python database/seeds/create_sample_claims_sqlite.py
copy config\database.example.json config\database.local.json
```

修改 `config/database.local.json`：

```json
"sqlite_path": "database/sample_claims.db"
```

重新启动服务后，页面点击“真实执行”。

## 4. 真实数据

真实医保结算数据需要单独提供，不在仓库中。导入说明见：

```text
docs/real_claims_data_import.md
```

## 5. 验收结果

测试通过时应看到：

```text
minimal tests passed
```

页面可以展示：

- 候选规则
- 受控 SQL
- SQL 安全校验
- 模拟/样例执行结果
- 任务详情
- CSV 导出
