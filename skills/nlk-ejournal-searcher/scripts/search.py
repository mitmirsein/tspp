#!/usr/bin/env python3
"""nlk-ejournal-searcher — 국립중앙도서관 data.go.kr 전자저널 검색 (BookInformationService_v2).

기존 nlk-biblio-searcher(nl.go.kr 서지, 초록 없음)를 대체. data.go.kr 국가서지 LOD의
전자저널(학술논문) 서비스는 **초록·목차·ISSN·DBpia 원문링크**를 제공해 TSPP 1차 정찰의
한국어 학술 자료 공급원이 된다(references/research-workflow.md 1단계).

- 순수 stdlib (외부 패키지 0). XML 응답을 ElementTree로 파싱.
- 검색: label=<쿼리> (제목/저자 부분매칭). API 응답은 XML 전용(type=json 무시됨).
- 인증: 환경변수 NLK_DATA_GO_KR_KEY (data.go.kr 일반 인증키). 미설정 시 에러.
- 출력: evidence_collect/research_fanout이 소비하는 정규화 키(title·authors·year·
  venue·abstract·url·issn). raw LOD 30필드는 버린다(토큰 절약).

사용:
    python scripts/search.py "칭의" --limit 5 --output json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ENDPOINT = ("https://apis.data.go.kr/1371029/BookInformationService_v2"
            "/getElectronicJournalList_v2")
ENV_KEY = "NLK_DATA_GO_KR_KEY"

# 응답 XML 태그 → 정규화 키 (evidence_collect가 인식하는 이름으로)
def _text(item: ET.Element, tag: str) -> str:
    el = item.find(tag)
    return (el.text or "").strip() if el is not None and el.text else ""


def _all(item: ET.Element, tag: str) -> list[str]:
    return [(e.text or "").strip() for e in item.findall(tag) if e.text and e.text.strip()]


def normalize(item: ET.Element) -> dict:
    # 저자: DC_creator(복수 가능)
    authors = ", ".join(_all(item, "DC_creator"))
    # 발행연도: DCTERMS_issued(예 '20090930' 또는 '民國72[1983]') → 앞 4자리 숫자
    issued = _text(item, "DCTERMS_issued")
    year = ""
    for i in range(len(issued) - 3):
        chunk = issued[i:i + 4]
        if chunk.isdigit() and chunk.startswith(("18", "19", "20")):
            year = chunk
            break
    return {
        "title": _text(item, "DCTERMS_title") or _text(item, "RDFS_label") or "(제목 없음)",
        "authors": authors,
        "year": year,
        "venue": _text(item, "NLON_titleOfHostItem") or _text(item, "DC_publisher"),
        "abstract": _text(item, "DCTERMS_abstract"),
        "issn": _text(item, "BIBO_issn"),
        # 원문 입수 경로: DBpia 등 외부 식별자 우선, 없으면 NLK LOD URI
        "url": _text(item, "DCTERMS_identifier") or _text(item, "URI"),
        "control_number": _text(item, "BIBLIO_ID"),
        "toc": _text(item, "DCTERMS_tableOfContents"),
        "type": "전자저널 학술논문",
    }


def search(query: str, limit: int, key: str) -> dict:
    params = {
        "serviceKey": key,
        "pageNo": "1",
        "numOfRows": str(limit),
        "label": query,
    }
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "TSPP-NLK-ejournal/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", errors="replace")

    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        return {"error": f"XML 파싱 실패: {e}", "body_head": body[:200]}

    result_msg = root.findtext(".//resultMsg") or ""
    total = root.findtext(".//totalCount") or "0"
    if result_msg and result_msg not in ("NORMAL_CODE", "NORMAL SERVICE."):
        # 인증/서비스 오류는 결과 없음과 구분
        if "NODATA" not in result_msg:
            return {"error": f"API 오류: {result_msg}", "results": [], "total": 0}

    items = root.findall(".//item")
    results = [normalize(it) for it in items]
    return {"query": query, "total": int(total) if total.isdigit() else 0,
            "fetched": len(results), "results": results}


def main() -> None:
    ap = argparse.ArgumentParser(description="국립중앙도서관 data.go.kr 전자저널 검색 CLI")
    ap.add_argument("query", help="검색어(label — 제목/저자 부분매칭)")
    ap.add_argument("--limit", type=int, default=10, help="결과 수(numOfRows)")
    ap.add_argument("--output", choices=["json"], default="json", help="출력 형식(json)")
    args = ap.parse_args()

    key = os.environ.get(ENV_KEY)
    if not key:
        print(json.dumps({"error": f"{ENV_KEY} 미설정 — dev 루트 .env 확인"},
                         ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    try:
        out = search(args.query, args.limit, key)
    except Exception as e:  # 네트워크 등
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    if "error" in out and not out.get("results"):
        print(json.dumps(out, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
