from __future__ import annotations

import argparse
import json
from pathlib import Path


def sql_string(value: str | None) -> str:
    if value is None or value == "":
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def jsonb_string(value: str | None) -> str:
    if not value:
        return "'{}'::jsonb"
    try:
        json.loads(value)
        normalized = value
    except json.JSONDecodeError:
        normalized = json.dumps({"raw": value}, ensure_ascii=False)
    return "'" + normalized.replace("'", "''") + "'::jsonb"


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents-jsonl", required=True)
    parser.add_argument("--chunks-jsonl", required=True)
    parser.add_argument("--output-sql", required=True)
    args = parser.parse_args()

    documents = load_jsonl(Path(args.documents_jsonl))
    chunks = load_jsonl(Path(args.chunks_jsonl))
    output = Path(args.output_sql)
    output.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "-- Generated policy RAG draft seed",
        "-- Import after database/migrations/001_core_assets_rules_rag.sql",
        "BEGIN;",
        "",
    ]

    lines.append("INSERT INTO policy_documents (document_id, asset_id, title, doc_no, issuer, publish_date, effective_date, region, source_file, content_hash, parse_status) VALUES")
    doc_values = []
    for doc in documents:
        doc_values.append(
            "    (" + ", ".join([
                sql_string(doc["document_id"]),
                sql_string(doc["asset_id"]),
                sql_string(doc["title"]),
                sql_string(doc["doc_no"]),
                sql_string(doc["issuer"]),
                sql_string(doc["publish_date"]),
                sql_string(doc["effective_date"]),
                sql_string(doc["region"]),
                sql_string(doc["source_file"]),
                sql_string(doc["content_hash"]),
                sql_string(doc["parse_status"]),
            ]) + ")"
        )
    lines.append(",\n".join(doc_values))
    lines.append("ON CONFLICT (document_id) DO UPDATE SET title = EXCLUDED.title, doc_no = EXCLUDED.doc_no, issuer = EXCLUDED.issuer, publish_date = EXCLUDED.publish_date, effective_date = EXCLUDED.effective_date, region = EXCLUDED.region, source_file = EXCLUDED.source_file, content_hash = EXCLUDED.content_hash, parse_status = EXCLUDED.parse_status, updated_at = now();")
    lines.append("")

    for start in range(0, len(chunks), 300):
        batch = chunks[start:start + 300]
        lines.append("INSERT INTO policy_chunks (chunk_id, document_id, chunk_index, section_title, content, page_no, metadata) VALUES")
        chunk_values = []
        for chunk in batch:
            chunk_values.append(
                "    (" + ", ".join([
                    sql_string(chunk["chunk_id"]),
                    sql_string(chunk["document_id"]),
                    str(chunk["chunk_index"]),
                    sql_string(chunk["section_title"]),
                    sql_string(chunk["content"]),
                    sql_string(chunk["page_no"]),
                    jsonb_string(chunk["metadata_json"]),
                ]) + ")"
            )
        lines.append(",\n".join(chunk_values))
        lines.append("ON CONFLICT (chunk_id) DO NOTHING;")
        lines.append("")

    lines.append("COMMIT;")
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"documents={len(documents)}")
    print(f"chunks={len(chunks)}")
    print(output)


if __name__ == "__main__":
    main()
