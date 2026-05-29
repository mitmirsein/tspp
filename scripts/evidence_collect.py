#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""evidence_collect.py — 검색기 출력 정규화 + EvidencePack.json 생성기 (TAWP Phase 2)

TAWP의 각 검색 스킬(kci-api-searcher, nlk-*, semantic-scholar, crossref-journal-searcher,
google-scholar-* 등)은 서로 다른 JSON 형태(results / data / items / 단순 list / error)와
필드명(title / title_eng / title_kor, authors / author, doi / DOI, year / pub_year ...)을
반환한다. 본 도구는 이질적 출력을 단일 EvidencePack 레코드 스키마로 정규화하여 합치고,
claim-ledger·forensic_gate가 소비하는 표준 EvidencePack.json을 생성한다.

사용법:
    python scripts/evidence_collect.py merge \
        --out output/EvidencePack.json \
        --input crossref:output/crossref_raw.json \
        --input kci:output/kci_raw.json
    # 또는 stdin 1건:
    some_searcher ... | python scripts/evidence_collect.py merge --engine s2 --stdin --out EP.json

정규화 EvidencePack 레코드 스키마:
    source_id, engine, title, authors[], year, venue, doi, isbn, url,
    abstract, verification_status(identifier_present|no_identifier)
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone

DOI_RE = re.compile(r'10\.\d{4,9}/[^\s,();\]]+', re.I)

# 검색기별 결과 배열이 담기는 키 후보
LIST_KEYS = ("results", "data", "items", "records", "abstracts", "hits", "docs")
# 필드 별칭 매핑
TITLE_KEYS = ("title", "title_eng", "title_kor", "preferred_label", "name")
AUTHOR_KEYS = ("authors", "author", "creators", "author_names")
YEAR_KEYS = ("year", "pub_year", "published", "pub_date", "date")
VENUE_KEYS = ("venue", "journal", "publisher", "container_title", "source")
DOI_KEYS = ("doi", "DOI")
ISBN_KEYS = ("isbn", "ISBN")
URL_KEYS = ("url", "URL", "link", "uri")
ABSTRACT_KEYS = ("abstract", "summary", "scope_note")
CITEKEY_KEYS = ("citekey", "citationKey", "bbt_citekey")
LOCAL_PDF_KEYS = ("local_pdf", "localPdf", "pdf_path")


def _first(d: dict, keys) -> str:
    for k in keys:
        v = d.get(k)
        if v:
            return v if isinstance(v, str) else v
    return ""


def _authors(d: dict) -> list:
    raw = None
    for k in AUTHOR_KEYS:
        if d.get(k):
            raw = d[k]
            break
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    out = []
    for a in raw:
        if isinstance(a, dict):
            out.append(a.get("name") or a.get("family") or a.get("literal") or "")
        else:
            out.append(str(a))
    return [a for a in out if a]


def _year(d: dict) -> str:
    v = _first(d, YEAR_KEYS)
    if not v:
        return ""
    m = re.search(r'\b(1[5-9]\d{2}|20\d{2})\b', str(v))
    return m.group(1) if m else str(v)[:10]


def extract_records(payload):
    """검색기 페이로드에서 레코드 리스트를 끌어낸다(이질적 형태 흡수)."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if "error" in payload and not any(k in payload for k in LIST_KEYS):
            return []  # 에러 응답
        for k in LIST_KEYS:
            v = payload.get(k)
            if isinstance(v, list):
                return v
    return []


def normalize_record(raw: dict, engine: str) -> dict:
    title = _first(raw, TITLE_KEYS) or "(제목 없음)"
    doi = (_first(raw, DOI_KEYS) or "").strip()
    if not doi:
        m = DOI_RE.search(json.dumps(raw, ensure_ascii=False))
        if m:
            doi = m.group(0).rstrip('.')
    isbn = _first(raw, ISBN_KEYS)
    url = _first(raw, URL_KEYS)
    citekey = (_first(raw, CITEKEY_KEYS) or "").strip()
    local_pdf = (_first(raw, LOCAL_PDF_KEYS) or "").strip()
    lod = raw.get("lod") if isinstance(raw.get("lod"), dict) else {}
    has_id = bool(doi or isbn or url)
    rec = {
        "engine": engine,
        "title": title.strip() if isinstance(title, str) else str(title),
        "authors": _authors(raw),
        "year": _year(raw),
        "venue": _first(raw, VENUE_KEYS),
        "doi": doi,
        "isbn": isbn,
        "url": url,
        "abstract": (_first(raw, ABSTRACT_KEYS) or "")[:500],
        "verification_status": "identifier_present" if has_id else "no_identifier",
    }
    if citekey:
        rec["citekey"] = citekey
    if local_pdf:
        rec["local_pdf"] = local_pdf
    if lod:
        rec["lod"] = lod
    return rec


def _dedup_key(rec: dict) -> str:
    if rec["doi"]:
        return "doi:" + rec["doi"].lower()
    if rec.get("citekey"):
        return "ck:" + rec["citekey"].lower()
    return "ttl:" + re.sub(r'\s+', ' ', rec["title"].lower()).strip()[:80]


ENGINE_PRIORITY = {
    "zotero-local": 0,
    "crossref-journal-searcher": 10,
    "kci-api-searcher": 11,
    "nlk-biblio-searcher": 11,
    "nlk-subject-searcher": 12,
    "ixtheo-searcher": 12,
    "semantic-scholar": 13,
    "google-scholar-quick": 20,
    "google-scholar-semantic": 20,
}


def _priority(engine: str) -> int:
    return ENGINE_PRIORITY.get(engine, 50)


def _merge_supplemental(into: dict, extra: dict) -> None:
    """dedup으로 흡수된 후속 레코드의 보조 정보를 1차 레코드에 보강한다.
    winner의 풍부한 필드는 건드리지 않고, winner가 비워 둔 칸만 채운다."""
    for k in ("local_pdf", "citekey", "abstract", "venue", "year", "isbn", "url"):
        if not into.get(k) and extra.get(k):
            into[k] = extra[k]
    if not into.get("authors") and extra.get("authors"):
        into["authors"] = extra["authors"]
    if extra.get("lod"):
        merged = dict(into.get("lod") or {})
        for k, v in extra["lod"].items():
            merged.setdefault(k, v)
        into["lod"] = merged


def merge(inputs: list, out_path: str) -> dict:
    """엔진 우선순위 dedup. zotero-local 등 권위 소스가 winner를 유지하며,
    외부 엔진은 winner가 비워 둔 필드만 보강한다."""
    seen: dict[str, dict] = {}
    records: list[dict] = []
    for engine, payload in inputs:
        for raw in extract_records(payload):
            if not isinstance(raw, dict):
                continue
            rec = normalize_record(raw, engine)
            key = _dedup_key(rec)
            if key in seen:
                existing = seen[key]
                if _priority(rec["engine"]) < _priority(existing["engine"]):
                    # 새 레코드가 더 권위 있음 — swap
                    _merge_supplemental(rec, existing)
                    idx = records.index(existing)
                    records[idx] = rec
                    seen[key] = rec
                else:
                    _merge_supplemental(existing, rec)
                continue
            seen[key] = rec
            records.append(rec)
    for i, rec in enumerate(records, start=1):
        rec["source_id"] = rec.get("citekey") or f"SRC-{i:03d}"
    pack = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engines": sorted({e for e, _ in inputs}),
        "total": len(records),
        "records": records,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, indent=2)
    return pack


def main():
    ap = argparse.ArgumentParser(description="TAWP EvidencePack 정규화 수집기")
    sub = ap.add_subparsers(dest="command", required=True)
    m = sub.add_parser("merge", help="검색기 출력들을 EvidencePack.json으로 정규화·병합")
    m.add_argument("--out", required=True, help="출력 EvidencePack.json 경로")
    m.add_argument("--input", action="append", default=[], help="engine:파일경로 (반복 가능)")
    m.add_argument("--engine", help="--stdin 사용 시 엔진명")
    m.add_argument("--stdin", action="store_true", help="표준입력에서 단일 검색기 JSON 읽기")
    args = ap.parse_args()

    inputs = []
    for spec in args.input:
        if ":" not in spec:
            print(f"[!] --input 형식은 engine:경로 여야 합니다: {spec}", file=sys.stderr)
            sys.exit(2)
        engine, path = spec.split(":", 1)
        try:
            with open(path, encoding="utf-8") as f:
                inputs.append((engine, json.load(f)))
        except Exception as e:
            print(f"[!] {path} 로드 실패: {e}", file=sys.stderr)
    if args.stdin:
        data = sys.stdin.read().strip()
        if data:
            inputs.append((args.engine or "stdin", json.loads(data)))

    if not inputs:
        print("[!] 입력이 없습니다.", file=sys.stderr)
        sys.exit(2)

    pack = merge(inputs, args.out)
    id_present = sum(1 for r in pack["records"] if r["verification_status"] == "identifier_present")
    print(f"✅ EvidencePack 생성: {args.out} | 레코드 {pack['total']}건 "
          f"(식별자 보유 {id_present} / 미보유 {pack['total'] - id_present}) | 엔진 {pack['engines']}")


if __name__ == "__main__":
    main()
