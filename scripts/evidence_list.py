#!/usr/bin/env python3
"""evidence_list.py — EvidencePack.json → 사람이 읽는 선별 리스트(evidence_list.md).

research-workflow.md 1단계(정찰)의 HITL 화면: 설교자가 이 리스트를 보고 어떤 원문을
입수할지 선별한다(2단계). 초록이 있으면 선별에 도움, 없어도 버리지 않고 제목·출처·
원문링크로 남긴다(워크플로우 §3 소프트 원칙).

- 순수 stdlib. 산문을 짓지 않는다 — EvidencePack의 사실만 표 형태로 옮긴다.
- 초록 보유분을 위로 정렬(선별 우선순위), 엔진·연도 표기.

사용:
    python scripts/evidence_list.py --evidence output/<run>/EvidencePack.json \
        --out output/<run>/evidence_list.md [--abstract-chars 280]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ENGINE_LABEL = {
    "kci-api-searcher": "KCI",
    "nlk-ejournal-searcher": "NLK전자저널",
    "semantic-scholar": "S2",
    "crossref-journal-searcher": "Crossref",
}


def load_records(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("records") or data.get("evidence") or []


def fmt_record(i: int, r: dict, abstract_chars: int) -> str:
    eng = ENGINE_LABEL.get(r.get("engine", ""), r.get("engine", "?"))
    title = (r.get("title") or "(제목 없음)").strip()
    authors = (r.get("authors") or "").strip()
    year = str(r.get("year") or "").strip()
    venue = (r.get("venue") or "").strip()
    doi = (r.get("doi") or "").strip()
    url = (r.get("url") or "").strip()
    abstract = (r.get("abstract") or "").strip()

    head = f"### {i}. {title}"
    meta = " · ".join(x for x in [authors, year, venue, f"[{eng}]"] if x)
    lines = [head, f"- {meta}"]
    # 원문 입수 경로(2단계용)
    link = ""
    if doi:
        link = f"https://doi.org/{doi}" if not doi.startswith("http") else doi
    elif url:
        link = url
    if link:
        lines.append(f"- 입수: {link}")
    # 초록(있으면) — 선별 판단 재료
    if abstract:
        ab = abstract if len(abstract) <= abstract_chars else abstract[:abstract_chars].rstrip() + "…"
        lines.append(f"- 초록: {ab}")
    else:
        lines.append("- 초록: _(없음 — 제목·출처로 판단)_")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="EvidencePack → 선별 리스트(markdown)")
    ap.add_argument("--evidence", required=True, help="EvidencePack.json 경로")
    ap.add_argument("--out", required=True, help="산출 evidence_list.md 경로")
    ap.add_argument("--abstract-chars", type=int, default=280, help="초록 표시 길이")
    args = ap.parse_args()

    ev = Path(args.evidence)
    if not ev.exists():
        print(f"[evidence_list] 파일 없음: {ev}", file=sys.stderr)
        sys.exit(1)
    records = load_records(ev)
    if not records:
        print("[evidence_list] 레코드 0건", file=sys.stderr)
        sys.exit(1)

    # 초록 보유분 우선, 그다음 연도 내림차순(선별 편의)
    def _key(r: dict):
        has_ab = 1 if (r.get("abstract") or "").strip() else 0
        try:
            yr = int(str(r.get("year") or 0)[:4])
        except ValueError:
            yr = 0
        return (-has_ab, -yr)

    records_sorted = sorted(records, key=_key)
    n_ab = sum(1 for r in records if (r.get("abstract") or "").strip())

    # 엔진별 집계
    from collections import Counter
    by_eng = Counter(ENGINE_LABEL.get(r.get("engine", ""), r.get("engine", "?")) for r in records)
    eng_line = " · ".join(f"{k} {v}" for k, v in by_eng.items())

    head = [
        "# 학술 자료 정찰 리스트 (1차 — HITL 선별용)",
        "",
        f"> 총 {len(records)}건 · 초록 보유 {n_ab}건 · 엔진별: {eng_line}",
        "> 워크플로우: 이 리스트에서 입수할 원문을 골라 `input/resources/`에 배치(2단계) → LLM 본문 분석(3단계).",
        "> 초록은 *선별 재료*일 뿐, 없는 자료도 버리지 않았다(유령인용 차단은 원문 입수로).",
        "",
        "---",
        "",
    ]
    body = [fmt_record(i, r, args.abstract_chars) for i, r in enumerate(records_sorted, 1)]
    Path(args.out).write_text("\n".join(head) + "\n\n".join(body) + "\n", encoding="utf-8")
    print(f"📄 선별 리스트 생성: {args.out} | {len(records)}건(초록 {n_ab}) · {eng_line}")


if __name__ == "__main__":
    main()
