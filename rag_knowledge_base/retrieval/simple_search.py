from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def tokenize(text: str) -> set[str]:
    chinese_terms = set(re.findall(r"[\u4e00-\u9fa5]{2,}", text))
    ascii_terms = set(re.findall(r"[a-zA-Z0-9_\-]{2,}", text.lower()))
    return chinese_terms | ascii_terms


def score(query_terms: set[str], content: str) -> int:
    return sum(1 for term in query_terms if term and term in content)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks-jsonl", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    query_terms = tokenize(args.query)
    hits = []
    with Path(args.chunks_jsonl).open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            content = row["content"]
            item_score = score(query_terms, content + row.get("section_title", ""))
            if item_score > 0:
                hits.append((item_score, row))
    hits.sort(key=lambda item: item[0], reverse=True)
    for item_score, row in hits[: args.limit]:
        print(f"score={item_score} chunk_id={row['chunk_id']} document_id={row['document_id']} title={row['section_title']}")
        print(row["content"][:300].replace("\n", " "))
        print("---")


if __name__ == "__main__":
    main()
