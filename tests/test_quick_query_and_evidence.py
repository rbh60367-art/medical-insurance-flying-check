from pathlib import Path

from backend.app.core.evidence_graph import attach_findings_to_graph, build_rule_evidence_graph
from backend.app.core.quick_query import quick_search

ROOT = Path(__file__).resolve().parents[1]


def sample_rule_item() -> dict:
    return {
        "item_rule_id": "NLRI-010871",
        "rule_type": "duplicate_charge",
        "item_code": "001103000010000|001102000030000",
        "item_name": "急诊监护费|急诊诊查费",
        "condition_text": "项目A和项目B同时收费",
        "source_file": "国家医保智能监管两库_官方公开附件_截至2026-07-10/第七批_医疗服务项目重复收费.xlsx",
    }


def test_quick_search_returns_rule_and_asset_hits() -> None:
    rule_result = quick_search(ROOT, "急诊监护费", library="rule_item", limit=5)
    assert rule_result["results"]
    assert rule_result["results"][0]["library"] == "rule_item"

    asset_result = quick_search(ROOT, "医疗服务价格", library="charge_item_catalog", limit=5)
    assert asset_result["results"]
    assert asset_result["results"][0]["library"] == "charge_item_catalog"


def test_evidence_graph_links_rule_items_charge_items_and_source_assets() -> None:
    graph = build_rule_evidence_graph(ROOT, sample_rule_item(), [])
    node_types = {node["type"] for node in graph["nodes"]}
    relations = {edge["relation"] for edge in graph["edges"]}

    assert "RuleItem" in node_types
    assert "ChargeItem" in node_types
    assert "ChargeCode" in node_types
    assert "SourceAsset" in node_types
    assert "applies_to" in relations
    assert "derived_from" in relations


def test_evidence_graph_can_attach_findings() -> None:
    graph = build_rule_evidence_graph(ROOT, sample_rule_item(), [])
    graph = attach_findings_to_graph(graph, "TASK-1", [{"settlement_id": "S001", "amount": 150}])
    node_types = {node["type"] for node in graph["nodes"]}
    relations = {edge["relation"] for edge in graph["edges"]}

    assert "QueryTask" in node_types
    assert "Finding" in node_types
    assert "triggered_by" in relations