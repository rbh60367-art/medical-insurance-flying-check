# AGENTS.md

## Scope

医保飞检智能检索 H5 MVP：政策 RAG、规则代码化、专家确认、受控 SQL、安全校验、任务结果导出。

## Rules

- Do not commit real patient, settlement, claim, or fee-detail data.
- Do not commit `config/database.local.json` or real database credentials.
- Do not execute arbitrary model-generated SQL.
- SQL execution must use controlled templates and safety checks.
- Patient identifiers must be masked.
- Results are review leads, not automatic violation conclusions.

## Verify

```powershell
python tests/run_minimal_tests.py
python backend/app/server.py
```

Open:

```text
http://127.0.0.1:8010/h5
```
