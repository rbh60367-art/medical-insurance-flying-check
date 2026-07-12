from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def load_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def make_node(node_id: str, label: str, node_type: str, properties: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": node_id, "label": label, "type": node_type, "properties": properties or {}}


def make_edge(source: str, target: str, relation: str) -> dict[str, str]:
    return {"source": source, "target": target, "relation": relation}


def find_source_asset(raw_assets: list[dict[str, Any]], source_file: str | None) -> dict[str, Any] | None:
    if not source_file:
        return None
    for row in raw_assets:
        if source_file in str(row.get("original_path") or "") or source_file in str(row.get("file_name") or ""):
            return row
    return None


def find_policy_hits(policy_chunks: list[dict[str, Any]], item_names: list[str], limit: int = 3) -> list[dict[str, Any]]:
    hits = []
    for row in policy_chunks:
        text = f"{row.get('section_title', '')}\n{row.get('content', '')}\n{row.get('metadata_json', '')}"
        score = sum(1 for name in item_names if name and name in text)
        if score:
            hits.append((score, row))
    hits.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in hits[:limit]]


def build_rule_evidence_graph(root: Path, rule_item: dict[str, Any], policy_hits: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    raw_assets = load_csv(root / "assets_manifest" / "raw_assets.csv")
    item_rule_id = str(rule_item.get("item_rule_id") or "UNKNOWN_RULE")
    rule_type = str(rule_item.get("rule_type") or "unknown")
    item_code = str(rule_item.get("item_code") or "")
    item_name = str(rule_item.get("item_name") or "")
    codes = [part.strip() for part in item_code.split("|") if part.strip()]
    names = [part.strip() for part in item_name.split("|") if part.strip()]

    nodes = [
        make_node(f"rule_item:{item_rule_id}", item_rule_id, "RuleItem", {"rule_type": rule_type, "condition": rule_item.get("condition_text")}),
        make_node(f"rule_definition:{rule_type}", rule_type, "RuleDefinition", {}),
    ]
    edges = [make_edge(f"rule_item:{item_rule_id}", f"rule_definition:{rule_type}", "belongs_to")]

    for index, code in enumerate(codes):
        name = names[index] if index < len(names) else code
        charge_id = f"charge_item:{code}"
        code_id = f"charge_code:{code}"
        nodes.append(make_node(charge_id, name, "ChargeItem", {"item_code": code}))
        nodes.append(make_node(code_id, code, "ChargeCode", {}))
        edges.append(make_edge(f"rule_item:{item_rule_id}", charge_id, "applies_to"))
        edges.append(make_edge(charge_id, code_id, "has_code"))

    source = find_source_asset(raw_assets, rule_item.get("source_file"))
    if source:
        asset_id = str(source.get("asset_id") or source.get("file_name"))
        nodes.append(make_node(f"source_asset:{asset_id}", str(source.get("file_name") or asset_id), "SourceAsset", {"path": source.get("original_path"), "category": source.get("category")}))
        edges.append(make_edge(f"rule_item:{item_rule_id}", f"source_asset:{asset_id}", "derived_from"))

    for hit in policy_hits or []:
        chunk_id = str(hit.get("chunk_id") or hit.get("id") or "policy")
        title = str(hit.get("section_title") or hit.get("title") or hit.get("document_id") or chunk_id)
        doc_id = str(hit.get("document_id") or hit.get("metadata", {}).get("document_id") or title)
        nodes.append(make_node(f"policy_document:{doc_id}", doc_id, "PolicyDocument", {}))
        nodes.append(make_node(f"policy_clause:{chunk_id}", title, "PolicyClause", {"preview": str(hit.get("content") or hit.get("content_preview") or hit.get("summary") or "")[:180]}))
        edges.append(make_edge(f"policy_clause:{chunk_id}", f"policy_document:{doc_id}", "part_of"))
        for code in codes:
            edges.append(make_edge(f"policy_clause:{chunk_id}", f"charge_item:{code}", "mentions"))

    return {
        "status": "draft_evidence_graph",
        "summary": "规则来源、收费项目、代码和政策依据的轻量证据链；当前为关系层草案，不是最终监管结论。",
        "nodes": dedupe_nodes(nodes),
        "edges": dedupe_edges(edges),
    }


def attach_findings_to_graph(graph: dict[str, Any], task_id: str, details: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = list(graph.get("nodes", []))
    edges = list(graph.get("edges", []))
    task_node = make_node(f"query_task:{task_id}", task_id, "QueryTask", {"finding_count": len(details)})
    nodes.append(task_node)
    for index, detail in enumerate(details[:10], start=1):
        finding_id = f"finding:{task_id}:{index}"
        nodes.append(make_node(finding_id, f"疑点{index}", "Finding", {"settlement_id": detail.get("settlement_id"), "amount": detail.get("amount") or detail.get("total_amount")}))
        edges.append(make_edge(f"query_task:{task_id}", finding_id, "has_finding"))
        rule_nodes = [node for node in graph.get("nodes", []) if node.get("type") == "RuleItem"]
        if rule_nodes:
            edges.append(make_edge(finding_id, rule_nodes[0]["id"], "triggered_by"))
    graph = dict(graph)
    graph["nodes"] = dedupe_nodes(nodes)
    graph["edges"] = dedupe_edges(edges)
    return graph


def dedupe_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for node in nodes:
        node_id = node.get("id")
        if node_id not in seen:
            seen.add(node_id)
            result.append(node)
    return result


def dedupe_edges(edges: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    result = []
    for edge in edges:
        key = (edge.get("source"), edge.get("target"), edge.get("relation"))
        if key not in seen:
            seen.add(key)
            result.append(edge)
    return result