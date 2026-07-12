from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def contains(text: str, query: str) -> bool:
    return query.lower() in str(text or "").lower()


def score_text(query: str, values: list[Any]) -> int:
    score = 0
    for value in values:
        text = str(value or "")
        if not text:
            continue
        if text == query:
            score += 6
        elif contains(text, query):
            score += 2
    return score


def search_rule_items(rule_items: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
    hits = []
    for row in rule_items:
        score = score_text(query, [row.get("item_rule_id"), row.get("rule_type"), row.get("item_code"), row.get("item_name"), row.get("condition_text"), row.get("source_file")])
        if score:
            hits.append((score, row))
    hits.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "library": "rule_item",
            "score": score,
            "id": row.get("item_rule_id"),
            "title": row.get("item_name") or row.get("item_code"),
            "summary": row.get("condition_text"),
            "metadata": {
                "rule_type": row.get("rule_type"),
                "item_code": row.get("item_code"),
                "source_file": row.get("source_file"),
            },
        }
        for score, row in hits[:limit]
    ]


def search_policy_chunks(policy_chunks: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
    hits = []
    for row in policy_chunks:
        score = score_text(query, [row.get("document_id"), row.get("section_title"), row.get("content"), row.get("metadata_json")])
        if score:
            hits.append((score, row))
    hits.sort(key=lambda item: item[0], reverse=True)
    results = []
    for score, row in hits[:limit]:
        metadata = json.loads(row.get("metadata_json", "{}") or "{}")
        results.append(
            {
                "library": "policy_document",
                "score": score,
                "id": row.get("chunk_id"),
                "title": row.get("section_title") or row.get("document_id"),
                "summary": str(row.get("content") or "")[:240],
                "metadata": {"document_id": row.get("document_id"), "source_file": metadata.get("source_file")},
            }
        )
    return results


def search_source_assets(raw_assets: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
    hits = []
    for row in raw_assets:
        score = score_text(query, [row.get("asset_id"), row.get("file_name"), row.get("original_path"), row.get("category"), row.get("target_module"), row.get("parse_status")])
        if score:
            hits.append((score, row))
    hits.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "library": "source_asset",
            "score": score,
            "id": row.get("asset_id"),
            "title": row.get("file_name") or row.get("original_path"),
            "summary": row.get("original_path"),
            "metadata": {
                "category": row.get("category"),
                "target_module": row.get("target_module"),
                "source_package": row.get("source_package"),
                "parse_status": row.get("parse_status"),
            },
        }
        for score, row in hits[:limit]
    ]


def search_charge_assets(raw_assets: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
    charge_assets = [row for row in raw_assets if row.get("category") == "project_catalog_or_price"]
    results = search_source_assets(charge_assets, query, limit)
    for row in results:
        row["library"] = "charge_item_catalog"
    return results


def quick_search(root: Path, query: str, library: str = "all", limit: int = 8) -> dict[str, Any]:
    query = query.strip()
    if not query:
        return {"query": query, "library": library, "results": []}
    rule_items = load_jsonl(root / "database" / "seeds" / "linked_priority_rule_items_draft.jsonl")
    policy_chunks = load_jsonl(root / "database" / "seeds" / "policy_chunks_draft.jsonl")
    raw_assets = load_csv(root / "assets_manifest" / "raw_assets.csv")
    groups: list[dict[str, Any]] = []
    if library in {"all", "charge_item_catalog"}:
        groups.extend(search_charge_assets(raw_assets, query, limit))
    if library in {"all", "rule_item"}:
        groups.extend(search_rule_items(rule_items, query, limit))
    if library in {"all", "policy_document"}:
        groups.extend(search_policy_chunks(policy_chunks, query, limit))
    if library in {"all", "source_asset"}:
        groups.extend(search_source_assets(raw_assets, query, limit))
    groups.sort(key=lambda item: item["score"], reverse=True)
    return {"query": query, "library": library, "results": groups[:limit]}