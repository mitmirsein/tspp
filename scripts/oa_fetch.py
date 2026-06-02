#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""oa_fetch.py — EvidencePack의 OA(open access) PDF를 input/resources/<run>/에 내려받는다.

- semantic-scholar: 레코드의 pdf_url(openAccessPdf.url)을 직접 받음.
- crossref-journal-searcher: DOI를 Unpaywall(api.unpaywall.org)로 조회해 OA면 받음.
- 엔진별 건수 제한(--per-engine-limit, 기본 3) — 대량 다운로드 방지.
- 순수 stdlib(urllib). 한국어 엔진(KCI/NLK)은 OA 직링크가 없어 건너뛴다(수동 입수).
- 파일명은 DOI 슬러그 → resource_ingest의 'stem==DOI 슬러그' 규칙으로 자동 매칭.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

PDF_MAGIC = b"%PDF-"
MAX_BYTES = 25_000_000
OA_ENGINES = {"semantic-scholar", "crossref-journal-searcher"}


def log(s: str) -> None:
    sys.stdout.write(s)
    sys.stdout.flush()


def slug(s: str, fallback: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", s or "").strip("-")
    return (s or fallback)[:80]


def http_get(url: str, email: str, timeout: int, accept: str):
    req = urllib.request.Request(url, headers={
        "User-Agent": f"TSPP-OAFetch/1.0 (sermon prep; mailto:{email})",
        "Accept": accept,
    })
    return urllib.request.urlopen(req, timeout=timeout)


def download_pdf(url: str, dest: Path, email: str) -> bool:
    try:
        with http_get(url, email, 90, "application/pdf,*/*") as r:
            ctype = (r.headers.get("Content-Type") or "").lower()
            data = r.read(MAX_BYTES)
    except Exception as e:  # noqa: BLE001
        log(f"  x 다운로드 실패: {e}\n")
        return False
    if not (data[:5] == PDF_MAGIC or "pdf" in ctype):
        log(f"  x PDF 아님(Content-Type={ctype or '?'})\n")
        return False
    dest.write_bytes(data)
    log(f"  ok {dest.name} ({len(data) // 1024} KB)\n")
    return True


def unpaywall_pdf(doi: str, email: str) -> str | None:
    u = f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?email={urllib.parse.quote(email)}"
    try:
        with http_get(u, email, 30, "application/json") as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        log(f"  x Unpaywall 조회 실패({doi}): {e}\n")
        return None
    loc = d.get("best_oa_location") or {}
    return loc.get("url_for_pdf") or None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", required=True, help="EvidencePack.json")
    ap.add_argument("--out", required=True, help="저장 폴더(input/resources/<run>)")
    ap.add_argument("--email", default="", help="Unpaywall/polite 연락 이메일")
    ap.add_argument("--per-engine-limit", type=int, default=3, help="엔진당 최대 다운로드 수")
    args = ap.parse_args()

    email = args.email.strip() or "anonymous@example.com"
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pack = Path(args.pack)
    if not pack.is_file():
        log(f"[oa_fetch] EvidencePack 없음: {pack}\n")
        return 1
    records = json.loads(pack.read_text(encoding="utf-8")).get("records", [])

    counts: dict[str, int] = {}
    got = 0
    for i, r in enumerate(records):
        eng = r.get("engine", "")
        if eng not in OA_ENGINES:
            continue
        if counts.get(eng, 0) >= args.per_engine_limit:
            continue
        doi = (r.get("doi") or "").strip()
        sid = r.get("source_id") or ""
        dest = out / (slug(doi or sid, f"rec{i}") + ".pdf")
        if dest.exists():
            log(f"- 이미 있음, 건너뜀: {dest.name}\n")
            continue

        url = None
        if eng == "semantic-scholar":
            url = (r.get("pdf_url") or "").strip() or None
        elif eng == "crossref-journal-searcher" and doi:
            log(f"- Unpaywall 조회: {doi}\n")
            url = unpaywall_pdf(doi, email)
        if not url:
            continue

        log(f"- [{eng}] {r.get('title', '')[:50]}\n")
        if download_pdf(url, dest, email):
            counts[eng] = counts.get(eng, 0) + 1
            got += 1
        time.sleep(1)

    log(f"\n[oa_fetch] 완료: {got}건 -> {out}\n")
    for e, c in counts.items():
        log(f"  {e}: {c}건\n")
    if got == 0:
        log("  (OA 직링크/Unpaywall OA가 없어 받은 게 없습니다. 한국어 자료는 수동 입수하세요.)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
