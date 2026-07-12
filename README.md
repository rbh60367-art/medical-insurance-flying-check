# 医保飞检智能检索 H5 MVP

这是一个医保飞检智能检索 MVP，用于演示：

- 政策文件 RAG 检索
- 国家医保智能监管两库规则代码化
- 专家确认后生成受控 SQL
- SQL 安全校验
- 模拟执行 / 样例库只读执行
- 任务详情和 CSV 导出

> 说明：本仓库不包含真实医保结算流水。远程测试默认使用 mock 流程；如需测试“真实执行”，可生成本地样例 SQLite。

## 快速运行

```powershell
python tests/run_minimal_tests.py
python backend/app/server.py
```

浏览器打开：

```text
http://127.0.0.1:8010/h5
```

## 页面测试

1. 点击“解析预览”
2. 点击“确认并生成 SQL”
3. 点击“模拟执行”
4. 点击“查看任务”
5. 点击“导出 CSV”

## 样例库真实执行

如需测试“真实执行”按钮：

```powershell
python database/seeds/create_sample_claims_sqlite.py
copy config\database.example.json config\database.local.json
```

然后把 `config/database.local.json` 里的 `sqlite_path` 改成：

```text
database/sample_claims.db
```

重新启动：

```powershell
python backend/app/server.py
```

## 目录说明

```text
backend/              后端 API
frontend/             H5 页面
rule_engine/          规则执行器和 SQL 模板
rag_knowledge_base/   政策检索
assets_manifest/      原始资料台账
database/             迁移、种子数据、样例库脚本
data_ingestion/       文档和真实数据导入脚本
docs/                 详细设计和说明
tests/                最小测试
```

## 重要边界

- 不提交真实患者、结算、费用明细数据。
- 不提交 `config/database.local.json` 或真实数据库账号。
- 大模型不直接自由执行 SQL，只能走受控模板和安全校验。
- 输出是疑点线索，不自动认定违规。

更多说明：`docs/github_remote_test_guide.md`
