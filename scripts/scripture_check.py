#!/usr/bin/env python3
"""scripture_check.py — 성경 인용 정합 대조 (성경 인용 정합 게이트 P0-1 ②).

개요/원고의 (a) 장절 표기와 (b) 직접 인용("...")을 정본 본문 데이터와 대조한다.
유령인용 금지(§7)를 성경 인용까지 확장하는 안전망.

신호 이원화 (QUALITY_UPGRADE §3 P0-1):
- **hard** (게이트성): 존재하지 않는 책/장/절 — 사실관계라 기계가 보증 가능.
- **worklist** (비점수): 인용 문자열이 본문과 다름(의역·다른 번역본 가능성 —
  의역은 정당하므로 판단은 설교자 §10), pericope 밖 장절(교차 참조 선언은
  binding_check 소관 — 여기서는 알림만).
- **info**: 본문과 매치되지 않은 인용(성경 인용이 아닐 수 있음 — 대사·일화 인용).

사용:
    python scripts/scripture_check.py --draft output/<run>/sermon_outline.md \
        [--pack output/<run>/scripture_pack.json] [--seed input/<run>/meditation_seed.json] \
        --out output/<run>/scripture_check.json
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scripture_lib as sl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

VERIFIED_T = 0.95     # 이상: 본문 일치(verified)
NEAR_T = 0.70         # 이상: 유사 — 의역/번역본 차이 가능(worklist)
QUOTE_RE = re.compile(r'[“"]([^”"]{6,300})[”"]')
MIN_QUOTE_NORM = 10   # 정규화 후 이 길이 미만 인용은 건너뜀(수사적 짧은 인용 소음 방지)


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:]
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="성경 인용 정합 대조")
    ap.add_argument("--draft", type=Path, required=True, help="sermon_outline.md 또는 full_manuscript.md")
    ap.add_argument("--pack", type=Path, help="scripture_pack.json (pericope 기준)")
    ap.add_argument("--seed", type=Path, help="meditation_seed.json (pack 없을 때 passage 폴백)")
    ap.add_argument("--translation", default=sl.DEFAULT_TRANSLATION,
                    help="번역본 코드 (기본 KorRV — input/scripture의 사용자 보유본이 우선)")
    ap.add_argument("--data", type=Path, default=None,
                    help="본문 데이터 루트 (기본: input/scripture → data/scripture 순 탐색)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    if not args.draft.is_file():
        print(f"[scripture_check] draft가 없습니다: {args.draft}", file=sys.stderr)
        return 2
    try:
        tr = sl.load_translation(args.data, args.translation)
    except FileNotFoundError as e:
        print(f"[scripture_check] 본문 데이터 로드 실패: {e}", file=sys.stderr)
        return 2

    # pericope 기준 — pack 우선, 없으면 seed의 passage
    peri_ref = None
    if args.pack and args.pack.is_file():
        pk = json.loads(args.pack.read_text(encoding="utf-8"))
        r = pk.get("ref", {})
        if r.get("book_n") and r.get("chapter"):
            peri_ref = sl.Ref(raw=pk.get("passage", ""), book_n=r["book_n"],
                              book_label=r.get("book_ko", ""), chapter=r["chapter"],
                              ranges=[tuple(x) for x in r.get("ranges", [])])
    if peri_ref is None and args.seed and args.seed.is_file():
        seed = json.loads(args.seed.read_text(encoding="utf-8"))
        peri_ref = sl.parse_passage(str(seed.get("passage", "")), tr)
    default_book = peri_ref.book_n if peri_ref else None

    text = _strip_frontmatter(args.draft.read_text(encoding="utf-8"))

    hard: list[dict] = []
    worklist: list[dict] = []
    info: list[dict] = []

    # ── (a) 장절 표기 검증 ───────────────────────────────────────────────
    refs = sl.parse_refs(text, tr, default_book=default_book)
    ref_rows = []
    for ref in refs:
        problems = sl.validate_ref(ref, tr)
        zone = "unknown"
        if peri_ref and ref.book_n == peri_ref.book_n and ref.chapter == peri_ref.chapter:
            in_peri = ref.ranges and all(
                any(pa <= a and b <= pb for pa, pb in peri_ref.ranges)
                for a, b in ref.ranges)
            zone = "pericope" if in_peri else "chapter"
        elif peri_ref:
            zone = "elsewhere"
        row = {"raw": ref.raw, "ref": ref.label(), "book_explicit": ref.book_explicit,
               "zone": zone, "problems": problems}
        ref_rows.append(row)
        if problems:
            hard.append({"kind": "nonexistent_ref", "ref": ref.label(), "raw": ref.raw,
                         "detail": "; ".join(problems)})
        elif zone == "elsewhere" and ref.book_explicit:
            worklist.append({"kind": "outside_pericope", "ref": ref.label(), "raw": ref.raw,
                             "detail": "pericope 밖 본문 참조 — 교차 참조라면 binding의 cross_refs로 선언"})

    # ── (b) 직접 인용 대조 ───────────────────────────────────────────────
    # 검색 공간: pericope 장 + draft가 참조한 모든 (책,장)
    chapters: list[tuple[int, int]] = []
    if peri_ref:
        chapters.append((peri_ref.book_n, peri_ref.chapter))
    for ref in refs:
        if ref.book_n and not sl.validate_ref(ref, tr):
            key = (ref.book_n, ref.chapter)
            if key not in chapters:
                chapters.append(key)

    quote_rows = []
    seen: set[tuple] = set()
    for m in QUOTE_RE.finditer(text):
        quote = m.group(1).strip()
        if len(sl.normalize_ko(quote)) < MIN_QUOTE_NORM:
            continue
        best = sl.best_verse_match(quote, tr, chapters) if chapters else None
        score = best["score"] if best else 0.0
        if score >= VERIFIED_T:
            status = "verified"
        elif score >= NEAR_T:
            status = "near_match"
        else:
            status = "unmatched"
        row = {"quote": quote, "status": status, "score": score,
               "best_ref": best["ref"] if best else None,
               "verse_text": best["verse_text"] if best and score >= NEAR_T else None}
        quote_rows.append(row)
        key = (status, quote, best["ref"] if best else None)
        if key in seen:
            continue  # 같은 인용 반복 — worklist에는 1회만
        seen.add(key)
        if status == "near_match":
            worklist.append({
                "kind": "quote_mismatch", "ref": best["ref"], "quote": quote,
                "verse_text": best["verse_text"],
                "detail": (f"인용이 {tr.label} 본문과 부분 불일치(score {score}). "
                           "의역이거나 다른 번역본일 수 있음 — 어느 번역본인지 명기하거나 본문대로 교정 (판단은 설교자)")})
        elif status == "verified" and best.get("blocks", 1) > 1:
            info.append({"kind": "quote_ellipsis", "ref": best["ref"], "quote": quote,
                         "detail": "본문과 일치하나 인용 내부에 생략 구간이 있음 — 의도한 중략인지 확인"})
        elif status == "unmatched":
            info.append({"kind": "quote_unmatched", "quote": quote,
                         "detail": ("검색 범위(pericope·참조 장) 내 본문과 매치되지 않음 — "
                                    "성경 인용이라면 장절 표기를 함께 적어 대조 범위에 넣고, 아니면 무시")})

    verdict = "blocked" if hard else "ok"
    result = {
        "schema_version": 1,
        "_note": ("성경 인용 정합 대조(P0-1). hard=존재하지 않는 장절(사실관계), "
                  "worklist=불일치·pericope 밖(판단은 설교자 §10), info=비성경 인용 가능. "
                  "의역·다른 번역본 사용은 정당하다 — 이 대조는 '다시 보라'는 신호다."),
        "draft": str(args.draft),
        "translation": {"code": tr.code, "label": tr.label},
        "pericope": peri_ref.label() if peri_ref else None,
        "verdict": verdict,
        "counts": {"refs": len(ref_rows), "quotes": len(quote_rows),
                   "hard": len(hard), "worklist": len(worklist), "info": len(info)},
        "hard": hard,
        "worklist": worklist,
        "info": info,
        "refs": ref_rows,
        "quotes": quote_rows,
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
                        .strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[scripture_check] {args.draft.name} ← {tr.label}"
          + (f" · pericope {peri_ref.label()}" if peri_ref else ""))
    print(f"  장절 {len(ref_rows)}건 · 인용 {len(quote_rows)}건 → "
          f"hard {len(hard)} · worklist {len(worklist)} · info {len(info)}")
    for h in hard:
        print(f"  [HARD] {h['detail']}")
    for w in worklist:
        print(f"  [worklist] {w['kind']}: {w.get('ref','')} — {w.get('quote', w.get('raw',''))[:40]}")
    print(f"  verdict: {verdict} → {args.out}")
    return 0 if verdict == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
