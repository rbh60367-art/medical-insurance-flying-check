from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree


SUPPORTED_TEXT_EXT = {".md", ".docx", ".xlsx", ".xls"}
PDF_STATUS = "parsed"


@dataclass
class PolicyDocument:
    document_id: str
    asset_id: str
    title: str
    doc_no: str
    issuer: str
    publish_date: str
    effective_date: str
    region: str
    source_file: str
    content_hash: str
    parse_status: str


@dataclass
class PolicyChunk:
    chunk_id: str
    document_id: str
    chunk_index: int
    section_title: str
    content: str
    page_no: str
    metadata_json: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def infer_title(file_name: str) -> str:
    stem = Path(file_name).stem
    stem = re.sub(r"^\d+(\.\d+)?", "", stem)
    stem = re.sub(r"^\d{6,8}", "", stem)
    return stem.strip(" ._-（）()") or Path(file_name).stem


def infer_doc_no(text: str) -> str:
    patterns = [
        r"[青][\u4e00-\u9fa5]{0,8}(?:医保|医疗保障)[\u4e00-\u9fa5]{0,8}[办局]?发〔\d{4}〕\d+号",
        r"青医保[\u4e00-\u9fa5]{0,4}〔\d{4}〕\d+号",
        r"青医保[\u4e00-\u9fa5]{0,4}\s*\d{4}\s*\d+号",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return normalize_text(match.group(0))
    return ""


def infer_year_date(text: str) -> str:
    match = re.search(r"(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})", text)
    if not match:
        return ""
    year, month, day = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def xml_text(element) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()



def extract_pdf_text(data: bytes, max_pages: int = 15) -> str:
    texts: list[str] = []
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        for page in reader.pages[:max_pages]:
            text = page.extract_text() or ""
            text = normalize_text(text)
            if text:
                texts.append(text)
        if texts:
            return "\n".join(texts)
    except Exception:
        pass

    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages[:max_pages]:
                text = page.extract_text() or ""
                text = normalize_text(text)
                if text:
                    texts.append(text)
    except Exception:
        pass

    return "\n".join(texts)

def extract_docx_text(data: bytes) -> str:
    texts: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in ["word/document.xml"]:
            try:
                root = ElementTree.fromstring(zf.read(name))
            except KeyError:
                continue
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            for para in root.findall(".//w:p", ns):
                text = "".join(node.text or "" for node in para.findall(".//w:t", ns))
                text = normalize_text(text)
                if text:
                    texts.append(text)
    return "\n".join(texts)


def read_shared_strings(xlsx: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(xlsx.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    return [xml_text(item) for item in root.findall("m:si", ns)]


def read_xlsx_text(data: bytes, max_rows_per_sheet: int = 80) -> str:
    lines: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as xlsx:
        shared = read_shared_strings(xlsx)
        sheet_names = sorted(name for name in xlsx.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml", name))
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        for sheet_name in sheet_names[:5]:
            root = ElementTree.fromstring(xlsx.read(sheet_name))
            lines.append(f"[{sheet_name}]")
            row_count = 0
            for row in root.findall("m:sheetData/m:row", ns):
                values: list[str] = []
                for cell in row.findall("m:c", ns):
                    value_node = cell.find("m:v", ns)
                    value = ""
                    if cell.attrib.get("t") == "s" and value_node is not None:
                        idx = int(value_node.text or "0")
                        value = shared[idx] if idx < len(shared) else ""
                    elif value_node is not None:
                        value = value_node.text or ""
                    if value:
                        values.append(normalize_text(value))
                if values:
                    lines.append(" | ".join(values))
                    row_count += 1
                if row_count >= max_rows_per_sheet:
                    break
    return "\n".join(lines)


def chunk_text(text: str, max_chars: int = 900) -> list[str]:
    text = text.strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 1 <= max_chars:
            current = (current + "\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            current = para[:max_chars]
    if current:
        chunks.append(current)
    return chunks


def source_bytes(row: dict[str, str], province_zip: Path, national_zip: Path, architecture_md: Path) -> bytes:
    if row["source_package"] == "single_file":
        return architecture_md.read_bytes()
    package = row["source_package"]
    zip_path = national_zip if "国家医保智能监管两库" in package else province_zip
    with zipfile.ZipFile(zip_path) as zf:
        return zf.read(row["original_path"])


def extract_text(row: dict[str, str], data: bytes) -> tuple[str, str]:
    ext = row["file_ext"].lower()
    if ext == ".md":
        return data.decode("utf-8", errors="ignore"), "parsed"
    if ext == ".docx":
        return extract_docx_text(data), "parsed"
    if ext == ".xlsx":
        return read_xlsx_text(data), "parsed"
    if ext == ".xls":
        return "", "needs_xls_converter"
    if ext == ".pdf":
        text = extract_pdf_text(data)
        if text:
            return text, "parsed"
        return infer_title(row["file_name"]), "needs_pdf_text_extractor"
    return "", "unsupported"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rag-source-csv", required=True)
    parser.add_argument("--province-zip", required=True)
    parser.add_argument("--national-rules-zip", required=True)
    parser.add_argument("--architecture-md", required=True)
    parser.add_argument("--output-documents-jsonl", required=True)
    parser.add_argument("--output-chunks-jsonl", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    rag_rows = list(csv.DictReader(Path(args.rag_source_csv).open("r", encoding="utf-8-sig")))
    province_zip = Path(args.province_zip)
    national_zip = Path(args.national_rules_zip)
    architecture_md = Path(args.architecture_md)

    documents: list[PolicyDocument] = []
    chunks: list[PolicyChunk] = []
    stats: dict[str, int] = {}

    for index, row in enumerate(rag_rows, start=1):
        data = source_bytes(row, province_zip, national_zip, architecture_md)
        text, status = extract_text(row, data)
        title = infer_title(row["file_name"])
        combined_for_meta = f"{row['file_name']}\n{text[:2000]}"
        document_id = f"PDOC-{index:06d}"
        doc = PolicyDocument(
            document_id=document_id,
            asset_id=row["asset_id"],
            title=title,
            doc_no=infer_doc_no(combined_for_meta),
            issuer="青海省医疗保障局" if "青海" in combined_for_meta or "青医保" in combined_for_meta else "",
            publish_date=infer_year_date(combined_for_meta),
            effective_date="",
            region="青海省" if "青海" in combined_for_meta or "青医保" in combined_for_meta else "",
            source_file=row["original_path"],
            content_hash=sha256_bytes(data),
            parse_status=status,
        )
        documents.append(doc)
        stats[status] = stats.get(status, 0) + 1

        for chunk_index, chunk in enumerate(chunk_text(text), start=1):
            chunks.append(
                PolicyChunk(
                    chunk_id=f"PCHK-{len(chunks) + 1:08d}",
                    document_id=document_id,
                    chunk_index=chunk_index,
                    section_title=title,
                    content=chunk,
                    page_no="",
                    metadata_json=json.dumps(
                        {
                            "asset_id": row["asset_id"],
                            "source_file": row["original_path"],
                            "file_ext": row["file_ext"],
                            "parse_status": status,
                        },
                        ensure_ascii=False,
                    ),
                )
            )

    doc_path = Path(args.output_documents_jsonl)
    chunk_path = Path(args.output_chunks_jsonl)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    chunk_path.parent.mkdir(parents=True, exist_ok=True)
    with doc_path.open("w", encoding="utf-8") as f:
        for doc in documents:
            f.write(json.dumps(doc.__dict__, ensure_ascii=False) + "\n")
    with chunk_path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk.__dict__, ensure_ascii=False) + "\n")

    lines = [
        "# 医保 RAG 第一批文档草案导出报告",
        "",
        f"文档数量：{len(documents)}",
        f"chunk 数量：{len(chunks)}",
        "",
        "## 解析状态",
        "",
        "| 状态 | 数量 |",
        "|---|---:|",
    ]
    for key, value in sorted(stats.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## 样例文档", "", "| document_id | title | doc_no | parse_status |", "|---|---|---|---|"])
    for doc in documents[:30]:
        lines.append(f"| {doc.document_id} | {doc.title} | {doc.doc_no} | {doc.parse_status} |")
    Path(args.output_md).write_text("\n".join(lines), encoding="utf-8")

    print(f"documents={len(documents)}")
    print(f"chunks={len(chunks)}")
    print(args.output_md)


if __name__ == "__main__":
    main()
