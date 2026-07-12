from __future__ import annotations

import csv
import io
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.sql_safety import load_field_mapping, validate_sql
from backend.app.core.evidence_graph import attach_findings_to_graph, build_rule_evidence_graph
from backend.app.core.quick_query import quick_search
from backend.app.core.db_executor import DatabaseNotConfiguredError, database_status, execute_readonly_query
from backend.app.core.mock_executor import execute_mock
CHUNKS_JSONL = ROOT / "database" / "seeds" / "policy_chunks_draft.jsonl"
RULE_ITEMS_JSONL = ROOT / "database" / "seeds" / "linked_priority_rule_items_draft.jsonl"
RULE_DEFS_JSONL = ROOT / "database" / "seeds" / "national_rule_definitions_draft.jsonl"
FIELD_MAPPING_JSON = ROOT / "config" / "field_mapping.json"
FRONTEND_DIR = ROOT / "frontend"
TASKS_JSONL = ROOT / "backend" / "runtime" / "task_runs.jsonl"
TASK_STORE: dict[str, dict] = {}


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


POLICY_CHUNKS = load_jsonl(CHUNKS_JSONL)
RULE_ITEMS = load_jsonl(RULE_ITEMS_JSONL)
RULE_DEFS = load_jsonl(RULE_DEFS_JSONL)
FIELD_MAPPING = load_field_mapping(FIELD_MAPPING_JSON)
RULE_ITEM_BY_ID = {row.get("item_rule_id"): row for row in RULE_ITEMS}


def tokenize(text: str) -> set[str]:
    terms = set(re.findall(r"[\u4e00-\u9fa5]{2,}", text))
    terms |= set(re.findall(r"[a-zA-Z0-9_\-]{2,}", text.lower()))
    return terms


def score_terms(query_terms: set[str], text: str) -> int:
    return sum(1 for term in query_terms if term and term in text)


def search_policy(query: str, limit: int = 5) -> list[dict]:
    terms = tokenize(query)
    hits = []
    for row in POLICY_CHUNKS:
        text = f"{row.get('section_title', '')}\n{row.get('content', '')}"
        score = score_terms(terms, text)
        if score:
            hits.append((score, row))
    hits.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "score": score,
            "chunk_id": row.get("chunk_id"),
            "document_id": row.get("document_id"),
            "title": row.get("section_title"),
            "content_preview": row.get("content", "")[:500],
            "metadata": json.loads(row.get("metadata_json", "{}")),
        }
        for score, row in hits[:limit]
    ]


def infer_rule_types(query: str) -> list[str]:
    pairs = [
        ("duplicate_charge", r"重复|同时收费|重复收费|项目共现|互斥"),
        ("gender_limit", r"性别|男|女|男性|女性"),
        ("age_limit", r"儿童|年龄|岁|老人|未成年"),
        ("frequency_limit", r"频次|次数|超次|周期"),
        ("institution_level_limit", r"机构级别|医院级别|基层|三级|二级"),
        ("treatment_course_limit", r"疗程|支付疗程"),
        ("indication_limit", r"适应症|诊断"),
    ]
    return [rule_type for rule_type, pattern in pairs if re.search(pattern, query)] or []


def search_rules(query: str, limit: int = 10) -> list[dict]:
    terms = tokenize(query)
    preferred_types = set(infer_rule_types(query))
    hits = []
    for row in RULE_ITEMS:
        text = "\n".join(
            [
                row.get("rule_type", ""),
                row.get("item_code", ""),
                row.get("item_name", ""),
                row.get("condition_text", ""),
                row.get("gender_limit", ""),
                row.get("age_limit", ""),
            ]
        )
        score = score_terms(terms, text)
        if row.get("rule_type") in preferred_types:
            score += 3
        if score:
            hits.append((score, row))
    hits.sort(key=lambda item: item[0], reverse=True)
    return [format_rule_hit(score, row) for score, row in hits[:limit]]


def format_rule_hit(score: int, row: dict) -> dict:
    return {
        "score": score,
        "item_rule_id": row.get("item_rule_id"),
        "rule_type": row.get("rule_type"),
        "item_code": row.get("item_code"),
        "item_name": row.get("item_name"),
        "condition_text": row.get("condition_text"),
        "link_status": row.get("link_status"),
        "source_file": row.get("source_file"),
    }


def build_preview(question: str) -> dict:
    rule_types = infer_rule_types(question)
    return {
        "question": question,
        "understanding": {
            "candidate_rule_types": rule_types,
            "execution_mode": "expert_confirmation_required",
            "sql_generation": "disabled_until_confirmed",
        },
        "policy_hits": search_policy(question, limit=5),
        "rule_hits": search_rules(question, limit=10),
        "next_step": "专家确认项目、规则、时间范围和口径后，再调用规则执行器生成受控 SQL。",
    }




def build_retrieval_conditions(query: str, rule_hits: list[dict]) -> dict:
    top_rule = rule_hits[0] if rule_hits else {}
    return {
        "source": "llm_or_rule_grounded_planner",
        "query_text": query,
        "candidate_item_rule_id": top_rule.get("item_rule_id"),
        "candidate_rule_type": top_rule.get("rule_type"),
        "candidate_item_code": top_rule.get("item_code"),
        "candidate_item_name": top_rule.get("item_name"),
        "date_start": "2025-01-01",
        "date_end": "2026-01-01",
        "execution_mode": "confirm_then_readonly_database_search",
        "requires_expert_confirmation": True,
        "next_api": "/api/v1/query/confirm -> /api/v1/query/execute",
    }
def build_assistant_reply(message: str, history: list[dict] | None = None) -> dict:
    query = message.strip()
    if not query:
        raise ValueError("message is required")

    rule_hits = search_rules(query, limit=3)
    policy_hits = search_policy(query, limit=3)
    quick_hits = quick_search(ROOT, query, library="all", limit=5).get("results", [])
    generated_conditions = build_retrieval_conditions(query, rule_hits)
    evidence_graph = None
    if rule_hits:
        rule_item = RULE_ITEM_BY_ID.get(rule_hits[0].get("item_rule_id"))
        if rule_item:
            evidence_graph = build_rule_evidence_graph(ROOT, rule_item, policy_hits)

    if rule_hits:
        top_rule = rule_hits[0]
        lines = [
            f"我先按医保飞检规则库检索到：{top_rule.get('item_name') or top_rule.get('item_code')}。",
            f"规则类型：{top_rule.get('rule_type')}；判断条件：{top_rule.get('condition_text') or '需专家确认'}。",
        ]
        if policy_hits:
            lines.append(f"同时找到 {len(policy_hits)} 条政策依据片段，可在右侧政策依据区查看。")
        lines.append("我已生成候选检索条件，仍需专家确认后才能生成 SQL 并查询数据库。")
        intent = "rule_consultation"
    elif policy_hits:
        top_policy = policy_hits[0]
        lines = [
            f"我在政策依据库里找到了相关内容：{top_policy.get('title') or top_policy.get('document_id')}。",
            f"摘要：{top_policy.get('content_preview', '')[:160]}",
            "如果要继续核查，可以补充收费项目名称、医保编码或规则类型。",
        ]
        intent = "policy_consultation"
    elif quick_hits:
        top_hit = quick_hits[0]
        lines = [
            f"我在四类库快速查询中找到：{top_hit.get('title') or top_hit.get('id')}。",
            f"所属库：{top_hit.get('library')}；摘要：{top_hit.get('summary') or '暂无摘要'}。",
        ]
        intent = "quick_lookup"
    else:
        lines = [
            "我暂时没有在规则库、政策库或原始资料台账中找到明确匹配。",
            "可以换成收费项目名称、医保编码、规则关键词，比如“重复收费”“性别限制”“年龄限制”。",
        ]
        intent = "clarification"

    return {
        "intent": intent,
        "message": query,
        "reply": "\n".join(lines),
        "rule_hits": rule_hits,
        "policy_hits": policy_hits,
        "quick_results": quick_hits,
        "generated_conditions": generated_conditions,
        "evidence_graph": evidence_graph,
        "actions": [
            {"label": "解析预览", "type": "preview", "question": query},
            {"label": "快速查询", "type": "quick_search", "query": query},
        ],
        "voice_supported_hint": "前端语音使用浏览器 Web Speech API；识别后仍走同一个文字聊天接口。",
    }
def require_date_range(payload: dict) -> tuple[str, str]:
    date_start = str(payload.get("date_start", "")).strip()
    date_end = str(payload.get("date_end", "")).strip()
    if not date_start or not date_end:
        raise ValueError("date_start and date_end are required")
    return date_start, date_end


def build_duplicate_charge_sql(rule_item: dict, payload: dict) -> dict:
    date_start, date_end = require_date_range(payload)
    codes = str(rule_item.get("item_code", "")).split("|")
    names = str(rule_item.get("item_name", "")).split("|")
    if len(codes) != 2:
        raise ValueError("duplicate_charge item_code must be 项目A代码|项目B代码")
    sql = """
SELECT
  sm.fixmedins_code AS institution_code,
  md5(sm.psn_no) AS patient_id_masked,
  sm.mdtrt_id AS encounter_id,
  sm.setl_id AS settlement_id,
  :item_code_a AS item_code_a,
  :item_name_a AS item_name_a,
  :item_code_b AS item_code_b,
  :item_name_b AS item_name_b,
  SUM(fa.det_item_fee_sumamt) AS item_a_amount,
  SUM(fb.det_item_fee_sumamt) AS item_b_amount,
  SUM(fa.det_item_fee_sumamt + fb.det_item_fee_sumamt) AS total_amount
FROM settlement_main sm
JOIN fee_detail fa ON sm.setl_id = fa.setl_id
JOIN fee_detail fb ON sm.setl_id = fb.setl_id
WHERE fa.hilist_code = :item_code_a
  AND fb.hilist_code = :item_code_b
  AND fa.fee_ocur_time >= :date_start
  AND fa.fee_ocur_time < :date_end
  AND fb.fee_ocur_time >= :date_start
  AND fb.fee_ocur_time < :date_end
GROUP BY sm.fixmedins_code, sm.psn_no, sm.mdtrt_id, sm.setl_id
""".strip()
    return {
        "sql_template_id": "duplicate_charge_pair_v1",
        "sql": sql,
        "parameters": {
            "item_code_a": codes[0],
            "item_name_a": names[0] if len(names) > 0 else "",
            "item_code_b": codes[1],
            "item_name_b": names[1] if len(names) > 1 else "",
            "date_start": date_start,
            "date_end": date_end,
        },
        "output_columns": [
            "institution_code",
            "patient_id_masked",
            "encounter_id",
            "settlement_id",
            "item_code_a",
            "item_name_a",
            "item_code_b",
            "item_name_b",
            "item_a_amount",
            "item_b_amount",
            "total_amount",
        ],
    }


def build_gender_limit_sql(rule_item: dict, payload: dict) -> dict:
    date_start, date_end = require_date_range(payload)
    params = payload.get("parameters", {}) or {}
    allowed_gender = params.get("allowed_gender") or rule_item.get("gender_limit") or "需专家确认"
    sql = """
SELECT
  sm.fixmedins_code AS institution_code,
  md5(sm.psn_no) AS patient_id_masked,
  sm.mdtrt_id AS encounter_id,
  fd.hilist_code AS item_code,
  fd.hilist_name AS item_name,
  sm.gend AS patient_gender,
  SUM(fd.det_item_fee_sumamt) AS amount
FROM settlement_main sm
JOIN fee_detail fd ON sm.setl_id = fd.setl_id
WHERE fd.hilist_code = :item_code
  AND fd.fee_ocur_time >= :date_start
  AND fd.fee_ocur_time < :date_end
  AND sm.gend <> :allowed_gender
GROUP BY sm.fixmedins_code, sm.psn_no, sm.mdtrt_id, fd.hilist_code, fd.hilist_name, sm.gend
""".strip()
    return {
        "sql_template_id": "gender_limit_v1",
        "sql": sql,
        "parameters": {
            "item_code": rule_item.get("item_code"),
            "date_start": date_start,
            "date_end": date_end,
            "allowed_gender": allowed_gender,
        },
        "output_columns": ["institution_code", "patient_id_masked", "encounter_id", "item_code", "item_name", "patient_gender", "amount"],
    }


def build_age_limit_sql(rule_item: dict, payload: dict) -> dict:
    date_start, date_end = require_date_range(payload)
    params = payload.get("parameters", {}) or {}
    min_age = params.get("min_age")
    max_age = params.get("max_age")
    sql = """
SELECT
  sm.fixmedins_code AS institution_code,
  md5(sm.psn_no) AS patient_id_masked,
  sm.mdtrt_id AS encounter_id,
  fd.hilist_code AS item_code,
  fd.hilist_name AS item_name,
  sm.age AS patient_age,
  SUM(fd.det_item_fee_sumamt) AS amount
FROM settlement_main sm
JOIN fee_detail fd ON sm.setl_id = fd.setl_id
WHERE fd.hilist_code = :item_code
  AND fd.fee_ocur_time >= :date_start
  AND fd.fee_ocur_time < :date_end
  AND (:min_age IS NULL OR sm.age >= :min_age)
  AND (:max_age IS NULL OR sm.age <= :max_age)
GROUP BY sm.fixmedins_code, sm.psn_no, sm.mdtrt_id, fd.hilist_code, fd.hilist_name, sm.age
""".strip()
    return {
        "sql_template_id": "age_limit_v1",
        "sql": sql,
        "parameters": {
            "item_code": rule_item.get("item_code"),
            "date_start": date_start,
            "date_end": date_end,
            "min_age": min_age,
            "max_age": max_age,
        },
        "output_columns": ["institution_code", "patient_id_masked", "encounter_id", "item_code", "item_name", "patient_age", "amount"],
    }


def confirm_query(payload: dict) -> dict:
    item_rule_id = str(payload.get("item_rule_id", "")).strip()
    if not item_rule_id:
        raise ValueError("item_rule_id is required")
    rule_item = RULE_ITEM_BY_ID.get(item_rule_id)
    if not rule_item:
        raise ValueError(f"unknown item_rule_id: {item_rule_id}")

    rule_type = rule_item.get("rule_type")
    if rule_type == "duplicate_charge":
        sql_result = build_duplicate_charge_sql(rule_item, payload)
    elif rule_type == "gender_limit":
        sql_result = build_gender_limit_sql(rule_item, payload)
    elif rule_type == "age_limit":
        sql_result = build_age_limit_sql(rule_item, payload)
    else:
        raise ValueError(f"rule_type not supported for SQL generation yet: {rule_type}")

    validation = validate_sql(sql_result["sql"], sql_result["parameters"], FIELD_MAPPING)
    evidence_graph = build_rule_evidence_graph(ROOT, rule_item, [])

    return {
        "status": "sql_generated_not_executed",
        "rule_item": {
            "item_rule_id": item_rule_id,
            "rule_type": rule_type,
            "item_code": rule_item.get("item_code"),
            "item_name": rule_item.get("item_name"),
            "condition_text": rule_item.get("condition_text"),
            "source_file": rule_item.get("source_file"),
        },
        "sql_result": sql_result,
        "sql_validation": {
            "valid": validation.valid,
            "errors": validation.errors,
            "warnings": validation.warnings,
            "tables": validation.tables,
            "fields": validation.fields,
        },
        "safety": {
            "only_select": True,
            "uses_template": True,
            "requires_readonly_connection": True,
            "requires_expert_confirmation": True,
            "executes_sql": False,
        },
        "evidence_graph": evidence_graph,
    }



def validate_sql_payload(payload: dict) -> dict:
    sql = str(payload.get("sql", "")).strip()
    parameters = payload.get("parameters", {}) or {}
    if not sql:
        raise ValueError("sql is required")
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be an object")
    result = validate_sql(sql, parameters, FIELD_MAPPING)
    return {
        "valid": result.valid,
        "errors": result.errors,
        "warnings": result.warnings,
        "tables": result.tables,
        "fields": result.fields,
    }


def persist_task(task: dict) -> None:
    TASK_STORE[task["task_id"]] = task
    TASKS_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with TASKS_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(task, ensure_ascii=False) + "\n")


def get_task(task_id: str) -> dict | None:
    if task_id in TASK_STORE:
        return TASK_STORE[task_id]
    if not TASKS_JSONL.exists():
        return None
    with TASKS_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("task_id") == task_id:
                TASK_STORE[task_id] = row
                return row
    return None


def build_task_payload(result, confirmed: dict) -> dict:
    evidence_graph = confirmed.get("evidence_graph") or build_rule_evidence_graph(ROOT, confirmed["rule_item"], [])
    evidence_graph = attach_findings_to_graph(evidence_graph, result.task_id, result.details)
    return {
        "task_id": result.task_id,
        "status": result.status,
        "summary": result.summary,
        "charts": result.charts,
        "details": result.details,
        "export": result.export,
        "execution": result.execution,
        "sql_result": confirmed["sql_result"],
        "sql_validation": confirmed["sql_validation"],
        "rule_item": confirmed["rule_item"],
        "evidence_graph": evidence_graph,
    }


def mock_execute_query(payload: dict) -> dict:
    item_rule_id = str(payload.get("item_rule_id", "")).strip()
    if not item_rule_id:
        raise ValueError("item_rule_id is required")
    rule_item = RULE_ITEM_BY_ID.get(item_rule_id)
    if not rule_item:
        raise ValueError(f"unknown item_rule_id: {item_rule_id}")
    confirmed = confirm_query(payload)
    validation = confirmed.get("sql_validation", {})
    if not validation.get("valid"):
        raise ValueError("SQL validation failed: " + "; ".join(validation.get("errors", [])))
    result = execute_mock(confirmed["rule_item"], confirmed["sql_result"])
    task = build_task_payload(result, confirmed)
    persist_task(task)
    return task

def execute_query(payload: dict) -> dict:
    item_rule_id = str(payload.get("item_rule_id", "")).strip()
    if not item_rule_id:
        raise ValueError("item_rule_id is required")
    rule_item = RULE_ITEM_BY_ID.get(item_rule_id)
    if not rule_item:
        raise ValueError(f"unknown item_rule_id: {item_rule_id}")
    confirmed = confirm_query(payload)
    validation = confirmed.get("sql_validation", {})
    if not validation.get("valid"):
        raise ValueError("SQL validation failed: " + "; ".join(validation.get("errors", [])))
    result = execute_readonly_query(ROOT, confirmed["rule_item"], confirmed["sql_result"])
    task = build_task_payload(result, confirmed)
    persist_task(task)
    return task


def task_to_csv(task: dict) -> bytes:
    output = io.StringIO()
    fieldnames = [
        "row_no",
        "institution_code",
        "institution_name",
        "patient_id_masked",
        "encounter_id",
        "settlement_id",
        "rule_type",
        "item_code",
        "item_name",
        "amount",
        "reason",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in task.get("details", []):
        writer.writerow(row)
    return ("\ufeff" + output.getvalue()).encode("utf-8")

class Handler(BaseHTTPRequestHandler):
    def send_text_file(self, path: Path, content_type: str = "text/html; charset=utf-8") -> None:
        if not path.exists():
            self.send_json({"error": "not found"}, status=404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, body: bytes, content_type: str, filename: str | None = None, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if parsed.path in {"/", "/h5", "/h5/"}:
            self.send_text_file(FRONTEND_DIR / "index.html")
            return
        if parsed.path == "/health":
            self.send_json({"status": "ok", "service": "medical-insurance-flying-check-api"})
            return
        if parsed.path == "/api/v1/stats":
            self.send_json({"policy_chunks": len(POLICY_CHUNKS), "rule_items": len(RULE_ITEMS), "rule_definitions": len(RULE_DEFS)})
            return
        if parsed.path == "/api/v1/database/status":
            try:
                self.send_json(database_status(ROOT))
            except DatabaseNotConfiguredError as exc:
                self.send_json({"configured": False, "error": str(exc), "code": "database_not_configured"})
            return
        if parsed.path == "/api/v1/quick-search":
            query = params.get("query", [""])[0]
            library = params.get("library", ["all"])[0]
            limit = int(params.get("limit", ["8"])[0])
            self.send_json(quick_search(ROOT, query, library=library, limit=limit))
            return
        if parsed.path == "/api/v1/evidence/graph":
            item_rule_id = params.get("item_rule_id", [""])[0]
            rule_item = RULE_ITEM_BY_ID.get(item_rule_id)
            if not rule_item:
                self.send_json({"error": "rule item not found"}, status=404)
                return
            self.send_json(build_rule_evidence_graph(ROOT, rule_item, []))
            return
        if parsed.path == "/api/v1/policy/search":
            query = params.get("query", [""])[0]
            self.send_json({"query": query, "hits": search_policy(query)})
            return
        task_match = re.fullmatch(r"/api/v1/tasks/([^/]+)(/export)?", parsed.path)
        if task_match:
            task_id = task_match.group(1)
            task = get_task(task_id)
            if not task:
                self.send_json({"error": "task not found"}, status=404)
                return
            if task_match.group(2):
                self.send_bytes(task_to_csv(task), "text/csv; charset=utf-8", f"{task_id}.csv")
                return
            self.send_json(task)
            return
        if parsed.path == "/api/v1/rules/search":
            query = params.get("query", [""])[0]
            self.send_json({"query": query, "hits": search_rules(query)})
            return
        self.send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({"error": "invalid json"}, status=400)
            return
        try:
            if parsed.path == "/api/v1/assistant/chat":
                message = str(payload.get("message", "")).strip()
                history = payload.get("history", [])
                if not message:
                    self.send_json({"error": "message is required"}, status=400)
                    return
                self.send_json(build_assistant_reply(message, history if isinstance(history, list) else []))
                return
            if parsed.path == "/api/v1/query/preview":
                question = str(payload.get("question", "")).strip()
                if not question:
                    self.send_json({"error": "question is required"}, status=400)
                    return
                self.send_json(build_preview(question))
                return
            if parsed.path == "/api/v1/query/confirm":
                self.send_json(confirm_query(payload))
                return
            if parsed.path == "/api/v1/sql/validate":
                self.send_json(validate_sql_payload(payload))
                return
            if parsed.path == "/api/v1/query/mock-execute":
                self.send_json(mock_execute_query(payload))
                return
            if parsed.path == "/api/v1/query/execute":
                self.send_json(execute_query(payload))
                return
        except DatabaseNotConfiguredError as exc:
            self.send_json({"error": str(exc), "code": "database_not_configured"}, status=400)
            return
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=400)
            return
        self.send_json({"error": "not found"}, status=404)

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8010), Handler)
    print("Medical insurance flying-check API listening on http://127.0.0.1:8010")
    server.serve_forever()


if __name__ == "__main__":
    main()

