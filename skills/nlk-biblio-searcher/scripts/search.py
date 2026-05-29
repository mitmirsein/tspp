#!/usr/bin/env python3
"""
NLK Biblio Searcher (www.nl.go.kr 검색 OpenAPI 기반)
===================================================
국립중앙도서관 직접 검색 OpenAPI(www.nl.go.kr/NL/search/openApi/search.do)를
호출하여 제목/저자/ISBN 기반 자연어 서지 검색을 수행하고, nlk-interlinker로
넘길 제어번호(CNTS-…)를 추출한다.

기존 data.go.kr BookInformationService_v2 게이트웨이는 기관 백엔드 장애로
무응답이라 폐기하고, 국립중앙도서관 자체 검색 OpenAPI로 전환했다.
인증키: dev 루트 .env의 NLK_SEARCH_API_KEY (국중도 발급).

사용법:
    python search.py "톨스토이 무저항" --output markdown
    python search.py "본회퍼" --target title --limit 5 --output json
    python search.py --isbn 9788932817291 --output json
"""

import argparse
import asyncio
import json
import os
import re
import sys
from typing import Any, Optional

import httpx

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".env")
SEARCH_URL = "https://www.nl.go.kr/NL/search/openApi/search.do"
NL_BASE = "https://www.nl.go.kr"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# srchTarget 별칭 → API 값
TARGETS = {"total": "total", "title": "title", "author": "author", "publisher": "publisher"}

_TAG_RE = re.compile(r"<[^>]+>")
_CNTS_RE = re.compile(r"(CNTS-\d+)")


def load_env_file(env_path: str = ENV_PATH) -> None:
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")


def parse_extra_params(values: list[str]) -> dict[str, str]:
    params = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"--param 값은 key=value 형식이어야 합니다: {value}")
        k, v = value.split("=", 1)
        params[k.strip()] = v.strip()
    return params


def strip_tags(s: str) -> str:
    return _TAG_RE.sub("", s or "").strip()


def extract_cnts(*urls: str) -> str:
    """orgLink/detailLink에서 LOD-조회 가능한 제어번호(CNTS-…) 추출."""
    for u in urls:
        if not u:
            continue
        m = _CNTS_RE.search(u)
        if m:
            return m.group(1)
    return ""


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    org = item.get("orgLink", "") or ""
    detail = item.get("detailLink", "") or ""
    cnts = extract_cnts(org, detail)
    url = ""
    if detail:
        url = detail if detail.startswith("http") else NL_BASE + detail
    elif org:
        url = org
    return {
        "title": strip_tags(item.get("titleInfo", "")),
        "creator": (item.get("authorInfo", "") or "").strip(),
        "publisher": (item.get("pubInfo", "") or "").strip(),
        "issued": (item.get("pubYearInfo", "") or "").strip(),
        "isbn": (item.get("isbn", "") or "").strip(),
        "type": (item.get("typeName", "") or "").strip(),
        "kdc": (item.get("kdcName1s", "") or "").strip(),
        # nlk-interlinker 입력값: LOD resource/{CNTS-…}
        "control_number": cnts,
        "nl_control_no": (item.get("controlNo", "") or "").strip(),
        "place": (item.get("placeInfo", "") or "").strip(),
        "url": url,
        "raw": item,
    }


class NLKBiblioClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(
        self,
        query: Optional[str],
        target: str = "total",
        page: int = 1,
        limit: int = 10,
        isbn: Optional[str] = None,
        extra_params: Optional[dict[str, str]] = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        params = {
            "key": self.api_key,
            "apiType": "json",
            "pageNum": str(page),
            "pageSize": str(limit),
        }
        if isbn:
            # 상세검색 모드: ISBN 정확 조회
            params.update({"detailSearch": "true", "isbnOp": "isbn", "isbnCode": isbn})
        else:
            params.update({"srchTarget": TARGETS.get(target, "total"), "kwd": query or ""})
        if extra_params:
            params.update(extra_params)

        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(SEARCH_URL, params=params, headers={"User-Agent": UA})
        except httpx.TimeoutException:
            return [], {"error": "검색 OpenAPI 타임아웃 (www.nl.go.kr 응답 지연)"}
        except Exception as exc:
            return [], {"error": str(exc)}

        if resp.status_code != 200:
            return [], {"error": f"HTTP {resp.status_code}", "body": resp.text[:300]}

        text = resp.text.strip()
        if not text:
            return [], {"error": "빈 응답입니다."}
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # 키 오류 등은 XML/HTML로 올 수 있음
            if "errMsg" in text or "인증" in text or "key" in text.lower():
                return [], {"error": f"인증/요청 오류: {text[:200]}"}
            return [], {"error": f"JSON 파싱 실패: {text[:200]}"}

        raw_items = data.get("result", [])
        if not isinstance(raw_items, list):
            raw_items = []
        results = [normalize_item(it) for it in raw_items if isinstance(it, dict)]
        stats = {
            "total_count": int(data.get("total") or 0),
            "total_fetched": len(results),
            "page": data.get("pageNum", page),
            "page_size": data.get("pageSize", limit),
        }
        if not results:
            stats["error"] = "검색 결과 없음"
        return results, stats


def format_json(query: str, results: list[dict[str, Any]], stats: dict[str, Any]) -> str:
    return json.dumps({"query": query, "total": len(results), "results": results, "stats": stats}, ensure_ascii=False, indent=2)


def format_markdown(query: str, results: list[dict[str, Any]], stats: dict[str, Any]) -> str:
    lines = [
        f"## 국립중앙도서관 서지 검색: `{query}`",
        "",
        f"- 엔드포인트: `www.nl.go.kr/NL/search/openApi` (검색 OpenAPI)",
        f"- 전체 건수: {stats.get('total_count', 0)} / 현재 수집: **{len(results)}건**",
        "",
    ]
    if not results:
        lines.append(f"> {stats.get('error', '결과 없음')}")
        return "\n".join(lines)

    lines.append("| # | 제목 | 저자 | 발행 | 유형 | 제어번호(CNTS) |")
    lines.append("|---|------|------|------|------|----------------|")
    for i, it in enumerate(results, 1):
        title = it.get("title") or "-"
        url = it.get("url", "")
        title_cell = f"[{title}]({url})" if url else title
        lines.append(
            f"| {i} | {title_cell} | {it.get('creator') or '-'} | {it.get('issued') or '-'} | "
            f"{it.get('type') or '-'} | `{it.get('control_number') or '-'}` |"
        )
    lines.append("")
    lines.append("> 제어번호(CNTS-…)는 `nlk-interlinker`에 넘겨 글로벌 전거(owl:sameAs)를 보강할 수 있습니다.")
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="국립중앙도서관 검색 OpenAPI 서지 검색 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python scripts/search.py "톨스토이 무저항" --output markdown
  python scripts/search.py "본회퍼" --target title --limit 5 --output json
  python scripts/search.py --isbn 9788932817291 --output json
        """,
    )
    parser.add_argument("query", nargs="?", help="검색어(kwd)")
    parser.add_argument("--target", default="total", choices=sorted(TARGETS.keys()), help="검색 대상 (기본: total)")
    parser.add_argument("--isbn", help="ISBN 정확 조회 (이 경우 query 무시)")
    parser.add_argument("--page", type=int, default=1, help="페이지 번호")
    parser.add_argument("--limit", type=int, default=10, help="한 페이지 결과 수")
    parser.add_argument("--param", action="append", default=[], help="추가 요청 파라미터 key=value. 반복 가능.")
    parser.add_argument("--output", default="json", choices=["json", "markdown"], help="출력 형식")
    # 하위호환(무시): 과거 data.go.kr 시절 인자
    parser.add_argument("--endpoint", help=argparse.SUPPRESS)
    parser.add_argument("--label", help=argparse.SUPPRESS)
    parser.add_argument("--type", default="json", help=argparse.SUPPRESS)
    args = parser.parse_args()

    try:
        extra_params = parse_extra_params(args.param)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)

    query = args.query or args.label
    if not query and not args.isbn:
        parser.error("검색어 또는 --isbn 이 필요합니다.")

    load_env_file()
    api_key = os.environ.get("NLK_SEARCH_API_KEY")
    if not api_key:
        print(json.dumps({"error": "NLK_SEARCH_API_KEY가 설정되지 않았습니다. dev 루트 .env를 확인해 주세요."}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    client = NLKBiblioClient(api_key)
    results, stats = await client.search(
        query=query, target=args.target, page=args.page, limit=args.limit,
        isbn=args.isbn, extra_params=extra_params,
    )

    if "error" in stats and not results:
        print(json.dumps({"error": stats["error"], "stats": stats}, ensure_ascii=False, indent=2))
        sys.exit(1)

    label = args.isbn or query or "all"
    if args.output == "json":
        print(format_json(label, results, stats))
    else:
        print(format_markdown(label, results, stats))


if __name__ == "__main__":
    asyncio.run(main())
