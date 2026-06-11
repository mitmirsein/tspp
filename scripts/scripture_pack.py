#!/usr/bin/env python3
"""scripture_pack.py — pericope 본문 팩 생성 (성경 인용 정합 게이트 P0-1 ①).

run의 본문(passage)을 정본 본문 데이터(`data/scripture/`)에서 추출해
`scripture_pack.json`을 만든다. 이후 에이전트는 **이 팩의 본문만** 성경
직접 인용의 원본으로 사용한다(유령인용 금지 §7의 성경 확장).

- 스크립트는 추출·구조화만 한다. 산문 생성 없음(§11).
- 입력: meditation_seed.json의 `passage`(우선) 또는 --passage 직접 지정.
- 산출: pericope 절 + 전후 문맥 절(기본 ±8, 같은 장 안) + 장 절수 메타.

사용:
    python scripts/scripture_pack.py --seed input/<run>/meditation_seed.json \
        --out output/<run>/scripture_pack.json
    python scripts/scripture_pack.py --passage "마태복음 21:33-46" --out ...
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scripture_lib as sl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="pericope 본문 팩 생성")
    ap.add_argument("--seed", type=Path, help="meditation_seed.json (passage 필드 사용)")
    ap.add_argument("--passage", help='본문 직접 지정 (예: "마태복음 21:33-46")')
    ap.add_argument("--translation", default=sl.DEFAULT_TRANSLATION,
                    help="번역본 코드 (기본 KorRV — input/scripture의 사용자 보유본이 우선)")
    ap.add_argument("--data", type=Path, default=None,
                    help="본문 데이터 루트 (기본: input/scripture → data/scripture 순 탐색)")
    ap.add_argument("--context", type=int, default=8, help="전후 문맥 절 수 (같은 장 안, 기본 8)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    passage = (args.passage or "").strip()
    if not passage and args.seed:
        if not args.seed.is_file():
            print(f"[scripture_pack] seed 파일이 없습니다: {args.seed}", file=sys.stderr)
            return 2
        seed = json.loads(args.seed.read_text(encoding="utf-8"))
        passage = str(seed.get("passage", "")).strip()
    if not passage:
        print("[scripture_pack] --passage 또는 passage가 있는 --seed가 필요합니다.", file=sys.stderr)
        return 2

    try:
        tr = sl.load_translation(args.data, args.translation)
    except FileNotFoundError as e:
        print(f"[scripture_pack] 본문 데이터 로드 실패: {e}", file=sys.stderr)
        return 2

    ref = sl.parse_passage(passage, tr)
    if ref is None or ref.book_n is None:
        print(f"[scripture_pack] 본문 표기를 해석할 수 없습니다: '{passage}'", file=sys.stderr)
        return 2
    problems = sl.validate_ref(ref, tr)
    if problems:
        for p in problems:
            print(f"[scripture_pack] 본문 오류: {p}", file=sys.stderr)
        return 2

    ranges = ref.ranges or [(1, tr.verse_count(ref.book_n, ref.chapter))]
    vc = tr.verse_count(ref.book_n, ref.chapter)
    pericope = []
    for a, b in ranges:
        pericope.extend(tr.get_range(ref.book_n, ref.chapter, a, b))
    v_lo = min(a for a, _ in ranges)
    v_hi = max(b for _, b in ranges)
    before = tr.get_range(ref.book_n, ref.chapter, max(1, v_lo - args.context), v_lo - 1)
    after = tr.get_range(ref.book_n, ref.chapter, v_hi + 1, min(vc, v_hi + args.context))

    meta = tr.book_meta(ref.book_n)
    pack = {
        "schema_version": 1,
        "_note": ("성경 인용 정합 게이트(P0-1) pericope 팩. 에이전트는 성경 직접 인용 시 "
                  "이 팩의 본문(번역본 명기)만 원본으로 사용한다 — 기억으로 인용하지 않는다(§7). "
                  "context_before/after는 문맥 파악용이며 pericope가 아니다."),
        "translation": {"code": tr.code, "label": tr.label, "license": tr.license},
        "passage": passage,
        "ref": {
            "book_n": ref.book_n, "book_ko": meta["ko"], "book_eng": meta["eng"],
            "chapter": ref.chapter, "ranges": [list(r) for r in ranges],
        },
        "chapter_verse_count": vc,
        "book_chapter_count": tr.chapter_count(ref.book_n),
        "pericope": pericope,
        "context_before": before,
        "context_after": after,
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
                        .strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(pack, ensure_ascii=False, indent=1), encoding="utf-8")

    rng_label = ",".join(f"{a}-{b}" if a != b else str(a) for a, b in ranges)
    print(f"[scripture_pack] {meta['ko']} {ref.chapter}:{rng_label} ({tr.label})")
    print(f"  pericope {len(pericope)}절 + 문맥 앞 {len(before)}절·뒤 {len(after)}절 → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
