#!/usr/bin/env python3
"""series_check.py — 설교 흐름 연속성 신호 (P1-5).

새 run의 본문·주제를 장부(sermon_ledger.json)의 최근 설교들과 대조해
**비점수 worklist 신호**를 만든다. 품질은 한 편이 아니라 *흐름*에서 나온다.

신호 (모두 worklist — 판단은 설교자 §10):
- passage_repeat   같은 책·장(또는 절 겹침)을 최근에 설교함
- theme_overlap    주제 내용어 겹침(조잡한 키워드 매칭 — 의미 유사도가 *아니다*)
- tier_streak      같은 설교 유형(tier)이 직전 N편 연속
- illustration_reuse  최근 사용한 예화 카드의 재사용

회중 데이터가 아니라 설교자 자신의 산출 이력만 본다(§8). 순수 stdlib(§11).

사용:
    python scripts/series_check.py --run <run> [--last 12] \
        [--ledger output/sermon_ledger.json] [--workspace .] \
        [--out output/<run>/series_check.json]
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_WORD_RE = re.compile(r"[가-힣]{2,}")
_PASSAGE_RE = re.compile(r"(?P<book>[가-힣]+)\s*(?P<ch>\d{1,3})(?:\s*[:장]\s*(?P<v1>\d{1,3})(?:\s*[-~–]\s*(?P<v2>\d{1,3}))?)?")
TIER_STREAK_N = 3


def read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def parse_passage(s: str | None) -> dict | None:
    if not s:
        return None
    m = _PASSAGE_RE.search(s)
    if not m:
        return None
    v1 = int(m.group("v1")) if m.group("v1") else None
    v2 = int(m.group("v2")) if m.group("v2") else v1
    return {"book": m.group("book"), "chapter": int(m.group("ch")), "v1": v1, "v2": v2}


def keyword_overlap(a: str, b: str) -> tuple[float, list[str]]:
    wa, wb = set(_WORD_RE.findall(a or "")), set(_WORD_RE.findall(b or ""))
    if not wa or not wb:
        return 0.0, []
    common = wa & wb
    return len(common) / min(len(wa), len(wb)), sorted(common)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="설교 흐름 연속성 신호 — 비점수 worklist")
    ap.add_argument("--run", required=True, help="새 run (seed가 input/<run>/에 있어야 함)")
    ap.add_argument("--last", type=int, default=12, help="대조할 최근 설교 수 (기본 12)")
    ap.add_argument("--workspace", type=Path, default=ROOT)
    ap.add_argument("--ledger", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    ledger_path = args.ledger or args.workspace / "output" / "sermon_ledger.json"
    seed = (read_json(args.workspace / "input" / args.run / "meditation_seed.json")
            or read_json(args.workspace / "output" / args.run / "meditation_seed.json"))
    if not seed:
        print(f"[series] 새 run의 meditation_seed.json을 찾지 못했습니다: "
              f"input/{args.run}/", file=sys.stderr)
        return 2

    ledger = read_json(ledger_path)
    entries = [e for e in ledger.get("entries", []) if e.get("run") != args.run]
    recent = entries[-args.last:]

    new_passage = parse_passage(str(seed.get("passage", "")))
    new_theme = str(seed.get("theme", ""))
    kw = (seed.get("evidence", {}) or {}).get("keywords_used", {}) or {}
    new_kw_text = new_theme + " " + " ".join((kw.get("ko") or []))

    signals: list[dict] = []

    if not recent:
        print(f"[series] 장부에 대조할 과거 설교가 없습니다 ({ledger_path}) — 신호 없음.")
    for e in recent:
        when = e.get("preached_on") or e.get("recorded_at") or "?"
        # ① 본문 중복
        old = parse_passage(str(e.get("passage", "")))
        if new_passage and old and new_passage["book"] == old["book"] \
                and new_passage["chapter"] == old["chapter"]:
            verse_note = ""
            if new_passage["v1"] and old["v1"]:
                ovl = not (new_passage["v2"] < old["v1"] or old["v2"] < new_passage["v1"])
                verse_note = " — 절 범위 겹침" if ovl else " — 같은 장, 다른 절"
            signals.append({
                "kind": "passage_repeat", "run": e["run"], "when": when,
                "detail": f"{e.get('passage')} ({when}, {e['run']}){verse_note}"})
        # ② 주제 겹침
        ratio, common = keyword_overlap(new_kw_text, str(e.get("theme", "")))
        if ratio >= 0.4 and len(common) >= 2:
            signals.append({
                "kind": "theme_overlap", "run": e["run"], "when": when,
                "detail": (f"주제 내용어 겹침 {ratio:.0%} ({', '.join(common[:5])}) — "
                           f"'{str(e.get('theme'))[:40]}' ({when})")})
        # ③ 예화 재사용 — 새 run에서 쓰려는 카드가 아니라, 과거 카드의 존재만 알림 대상이
        #    아니므로 여기서는 새 run 산출물이 있을 때만 대조한다(아래 ④).

    # ③ tier 연속 편중
    tiers = [e.get("tier") for e in recent if e.get("tier")]
    if len(tiers) >= TIER_STREAK_N and len(set(tiers[-TIER_STREAK_N:])) == 1:
        signals.append({
            "kind": "tier_streak", "run": None, "when": None,
            "detail": (f"직전 {TIER_STREAK_N}편이 모두 tier={tiers[-1]} — "
                       "흐름 편중인지 의도한 시리즈인지 확인")})

    # ④ 예화 재사용 (새 run 개요/원고가 이미 있으면)
    used_now: set[str] = set()
    for doc in ("sermon_outline.md", "full_manuscript.md"):
        p = args.workspace / "output" / args.run / doc
        if p.is_file():
            used_now |= set(re.findall(r"\(예화금고:\s*([A-Za-z0-9_\-가-힣]+)\s*\)",
                                       p.read_text(encoding="utf-8")))
    if used_now:
        for e in recent:
            dup = used_now & set(e.get("illustrations") or [])
            for card in sorted(dup):
                signals.append({
                    "kind": "illustration_reuse", "run": e["run"],
                    "when": e.get("preached_on") or e.get("recorded_at"),
                    "detail": f"예화 '{card}' — {e['run']}에서 사용됨"})

    result = {
        "schema_version": 1,
        "_note": ("설교 흐름 연속성 신호(P1-5). 비점수 worklist — 키워드 겹침 수준의 "
                  "조잡한 매칭이며 의미 유사도가 아니다(정직한 한계). 판단은 설교자(§10). "
                  "신호이지 판정이 아니다."),
        "run": args.run,
        "passage": seed.get("passage"),
        "compared": len(recent),
        "signals": signals,
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
                        .strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out_path = args.out or args.workspace / "output" / args.run / "series_check.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[series] {args.run} ↔ 최근 {len(recent)}편 대조 → 신호 {len(signals)}건")
    for s in signals:
        print(f"  [{s['kind']}] {s['detail']}")
    print(f"  → {out_path} (신호이지 판정 아님 — 판단은 설교자)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
