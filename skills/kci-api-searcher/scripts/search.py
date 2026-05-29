#!/usr/bin/env python3
"""
KCI Portal OpenAPI Searcher — CLI Entry Point
==============================================
KCI(한국학술지인용색인) 공식 직접 OpenAPI(open.kci.go.kr)를 연동하여 논문을 검색하는 실행 스크립트.

사용법:
    uv run python scripts/search.py <query> [options]   # 스킬 디렉터리에서 실행

출력 형식:
    --output json      에이전트 파싱 최적화 (기본값)
    --output markdown  인간 가독 테이블 및 초록 요약
"""

import asyncio
import argparse
import json
import sys
import os
import re
import xml.etree.ElementTree as ET
from typing import Optional

import httpx

# 로컬 유틸리티
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from recon_utils import ForensicAudit, logger

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def load_env_file(env_path: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".env")):
    """TAWP 프로젝트 루트의 .env 파일에서 환경변수를 로드합니다(없으면 os.environ 폴백)."""
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    os.environ[key] = val


class KCIPortalScraper:
    """KCI 포털 직접 OpenAPI(open.kci.go.kr) 연동 클래스."""

    PORTAL_URL = "https://open.kci.go.kr/po/openapi/openApiSearch.kci"

    def __init__(self, api_key: str):
        self.api_key = api_key

    @staticmethod
    def _bare_doi(doi: str) -> str:
        doi = (doi or "").strip()
        return re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)

    @staticmethod
    def _split_author(text: str) -> tuple[str, str]:
        """'김진혁(횃불트리니티신학대학원대학교)' → ('김진혁', '횃불트리니티신학대학원대학교')"""
        text = (text or "").strip()
        m = re.match(r"^(.*?)\(([^)]*)\)\s*$", text)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        return text, ""

    async def _http_get(self, client, title: str, count: int, page: int = 1):
        params = {
            "key": self.api_key,
            "apiCode": "articleSearch",
            "title": title,
            "page": str(page),
            "displayCount": str(count),
        }
        return await client.get(self.PORTAL_URL, params=params, headers={"User-Agent": UA})

    async def _fetch(self, client, title: str, count: int) -> tuple[list[dict], int, Optional[str]]:
        """제목 검색 1회 → (레코드 목록, total_count, error). 감사(audit) 없음."""
        try:
            resp = await self._http_get(client, title, count)
        except httpx.TimeoutException:
            return [], 0, "포털 API 요청 타임아웃 (KCI 포털 응답 지연 가능)"
        if resp.status_code != 200:
            return [], 0, f"HTTP {resp.status_code}"
        if "등록되지 않은 key" in resp.text or "사용기간이 종료" in resp.text:
            return [], 0, "KCI 포털 키 오류/만료 (KCI_OPEN_API_KEY 확인)"
        try:
            return (*self._extract(resp.text), None)
        except ET.ParseError as e:
            return [], 0, f"XML 파싱 실패: {e}"

    @staticmethod
    def _contains(record: dict, token: str) -> bool:
        """레코드의 제목+초록+키워드에 토큰이 (공백무시) 포함되는지."""
        blob = " ".join([
            record.get("title", ""), record.get("title_eng", ""),
            record.get("abstract", ""), record.get("keywords", ""),
        ]).lower()
        t = token.lower()
        return t in blob or t.replace(" ", "") in blob.replace(" ", "")

    async def search(self, query: str, page: int = 1, limit: int = 10) -> tuple[list[dict], dict]:
        """하이브리드 검색.
        Phase 1: 전체 쿼리를 title=로 전송 (KCI 제목 토큰 매칭; 빠르고 정밀).
        Phase 2: 다중어인데 Phase 1이 빈약하면(< limit) → 가장 희귀한 토큰으로 넓게 받아
                 나머지 토큰을 제목+초록에서 로컬 AND 필터 (제목 분산형 쿼리 구제, 예: '톨스토이 무저항').
        """
        title = re.sub(r"-+", " ", query).strip()
        tokens = [t for t in title.split() if t]
        phase = "title"
        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                raw1, total1, err = await self._fetch(client, title, max(limit, 10))
                if err:
                    return [], {"error": err}
                pool = list(raw1)

                if len(tokens) > 1 and len(raw1) < limit:
                    # 각 토큰을 번갈아 앵커로 제목검색 → 나머지를 제목+초록에서 AND 필터 → union.
                    # (한 토큰이 제목, 다른 토큰이 초록에만 있는 논문도 포착: 예 '나도향의 톨스토이…'+초록 무저항)
                    seen = {r["artiId"] for r in pool}
                    for anchor in tokens:
                        others = [t for t in tokens if t != anchor]
                        raw_a, _, err_a = await self._fetch(client, anchor, 100)
                        if err_a or not raw_a:
                            continue
                        for r in raw_a:
                            if r["artiId"] in seen:
                                continue
                            if all(self._contains(r, o) for o in others):
                                pool.append(r)
                                seen.add(r["artiId"])
                    phase = "title+abstract (multi-anchor)"
        except httpx.TimeoutException:
            return [], {"error": "포털 API 요청 타임아웃 (KCI 포털 응답 지연 가능)"}
        except Exception as e:
            return [], {"error": str(e)}

        audit = {"total_fetched": len(pool), "total_count": total1, "phase": phase, "passed": 0, "rejected": 0}
        if not pool:
            audit["error"] = "검색 결과 없음"
            return [], audit
        verified, rejected = ForensicAudit.audit_results(query, pool)
        audit["passed"] = len(verified)
        audit["rejected"] = len(rejected)
        if not verified:
            audit["warning"] = "ForensicAudit 필터 전체 통과 실패 (검색 노이즈 처리됨)"
            return [], audit
        return verified[:limit], audit

    def _extract(self, xml_content: str) -> tuple[list[dict], int]:
        """XML → (레코드 목록, total_count). 감사 없는 순수 파싱."""
        root = ET.fromstring(xml_content.encode("utf-8"))
        total = root.findtext(".//result/total")
        total_count = int(total) if total and total.isdigit() else 0
        raw = []
        for rec in root.findall(".//record"):
            ji = rec.find("journalInfo")
            jget = (lambda tag: (ji.findtext(tag, default="") or "").strip()) if ji is not None else (lambda tag: "")
            ai = rec.find("articleInfo")
            if ai is None:
                continue
            arti_id = ai.get("article-id", "")

            title_orig = title_eng = ""
            tg = ai.find("title-group")
            if tg is not None:
                for at in tg.findall("article-title"):
                    lang = at.get("lang", "")
                    if lang == "original":
                        title_orig = (at.text or "").strip()
                    elif lang in ("english", "foreign") and not title_eng:
                        title_eng = (at.text or "").strip()

            authors, affiliations = [], []
            ag = ai.find("author-group")
            if ag is not None:
                for au in ag.findall("author"):
                    name, aff = self._split_author(au.text or "")
                    if name:
                        authors.append(name)
                    if aff and aff not in affiliations:
                        affiliations.append(aff)

            abstract = ""
            abg = ai.find("abstract-group")
            if abg is not None:
                for ab in abg.findall("abstract"):
                    if ab.get("lang") == "original" or not abstract:
                        abstract = (ab.text or "").strip()

            cc = ai.find("citation-count")
            cite_kci = cc.get("kci", "") if cc is not None else ""
            cite_wos = cc.get("wos", "") if cc is not None else ""

            raw.append({
                "title": title_orig or title_eng or "제목 없음",
                "title_eng": title_eng,
                "artiId": arti_id,
                "authors": authors,
                "affiliations": affiliations,
                "author_count": len(authors),
                "journal": jget("journal-name"),
                "publisher": jget("publisher-name"),
                "pub_year": jget("pub-year"),
                "pub_mon": jget("pub-mon"),
                "doi": self._bare_doi(ai.findtext("doi", default="")),
                "uci": (ai.findtext("uci", default="") or "").strip(),
                "citation_kci": cite_kci,
                "citation_wos": cite_wos,
                "keywords": "",
                "crossref_deposited": "",
                "abstract": abstract,
                "url": (ai.findtext("url", default="") or "").strip()
                       or f"https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId={arti_id}",
            })

        return raw, total_count


def format_json(query: str, results: list[dict], audit_stats: dict) -> str:
    output = {
        "query": query,
        "total": len(results),
        "results": [
            {
                "rank": i + 1,
                "title": r.get("title", ""),
                "title_eng": r.get("title_eng", ""),
                "artiId": r.get("artiId", ""),
                "authors": r.get("authors", []),
                "affiliations": r.get("affiliations", []),
                "author_count": r.get("author_count", 0),
                "journal": r.get("journal", ""),
                "publisher": r.get("publisher", ""),
                "pub_year": r.get("pub_year", ""),
                "pub_mon": r.get("pub_mon", ""),
                "doi": r.get("doi", ""),
                "uci": r.get("uci", ""),
                "citation_kci": r.get("citation_kci", ""),
                "citation_wos": r.get("citation_wos", ""),
                "abstract": r.get("abstract", ""),
                "url": r.get("url", ""),
            }
            for i, r in enumerate(results)
        ],
        "forensic_audit": audit_stats,
    }
    return json.dumps(output, ensure_ascii=False, indent=2)


def format_markdown(query: str, results: list[dict], audit_stats: dict) -> str:
    lines = [
        f"## KCI 포털 직접 OpenAPI 검색 결과: `{query}`",
        f"",
        f"- 검색 총량: {audit_stats.get('total_fetched', 0)}건",
        f"- ForensicAudit 통과: **{audit_stats.get('passed', 0)}건**",
        f"- 노이즈 제거: {audit_stats.get('rejected', 0)}건",
        f"",
    ]

    if not results:
        lines.append(f"> ⚠️ {audit_stats.get('warning', audit_stats.get('error', '결과 없음'))}")
        return "\n".join(lines)

    lines.append("| # | 제목 | 저자 | 발행 | DOI |")
    lines.append("|---|------|------|------|-----|")
    for i, r in enumerate(results):
        names = r.get("authors", [])
        if names:
            authors = ", ".join(names[:2]) + (" 외" if len(names) > 2 else "")
        elif r.get("affiliations"):
            affs = r["affiliations"]
            authors = f"({affs[0]}" + (f" 외 {len(affs)-1}" if len(affs) > 1 else "") + ")"
        else:
            authors = "-"
        doi = r.get("doi") or "-"
        pub = "-"
        if r.get("pub_year"):
            pub = r["pub_year"] + (f".{r['pub_mon']}" if r.get("pub_mon") else "")
        title = r.get("title", "")
        url = r.get("url", "")
        title_link = f"[{title}]({url})" if url else title
        lines.append(f"| {i+1} | {title_link} | {authors} | {pub} | `{doi}` |")

    lines.append("")
    for i, r in enumerate(results):
        abstract = r.get("abstract", "")
        affs = r.get("affiliations", [])
        journal = r.get("journal", "")
        if abstract or affs or journal:
            lines.append(f"### {i+1}. {r.get('title', '')}")
            if journal:
                lines.append(f"**학술지:** {journal}")
            if affs:
                lines.append(f"**소속기관:** {', '.join(affs)}")
            lines.append("")
            if abstract:
                lines.append(f"> {abstract[:400]}{'...' if len(abstract) > 400 else ''}")
            lines.append("")

    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(
        description="KCI 포털 직접 OpenAPI 논문 검색 CLI",
    )
    parser.add_argument("query", help="검색할 논문 제목(title) 키워드")
    parser.add_argument("--page", type=int, default=1, help="페이지 번호 (기본: 1)")
    parser.add_argument("--limit", type=int, default=10, help="출력 건수 (기본: 10, 최대: 100)")
    parser.add_argument("--output", default="json", choices=["json", "markdown"], help="출력 형식 (기본: json)")

    args = parser.parse_args()

    load_env_file()
    api_key = os.environ.get("KCI_OPEN_API_KEY")
    if not api_key:
        if args.output == "json":
            print(json.dumps({"error": "KCI_OPEN_API_KEY가 설정되지 않았습니다. dev 루트의 .env 파일을 확인해 주세요."}, ensure_ascii=False), file=sys.stderr)
        else:
            print("### ⚠️ 오류 발생\n- KCI_OPEN_API_KEY가 설정되지 않았습니다. dev 루트의 .env 파일을 확인해 주세요.", file=sys.stderr)
        sys.exit(1)

    scraper = KCIPortalScraper(api_key=api_key)
    results, audit_stats = await scraper.search(
        query=args.query,
        page=args.page,
        limit=args.limit,
    )

    if "error" in audit_stats and not results:
        if args.output == "json":
            print(json.dumps({"error": audit_stats["error"]}, ensure_ascii=False, indent=2))
        else:
            print(f"### ⚠️ KCI OpenAPI 오류 발생\n- {audit_stats['error']}")
        sys.exit(1)

    if args.output == "json":
        print(format_json(args.query, results, audit_stats))
    else:
        print(format_markdown(args.query, results, audit_stats))


if __name__ == "__main__":
    asyncio.run(main())
