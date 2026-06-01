#!/usr/bin/env python3
r"""delivery_pack.py — 설교 원고의 *전달 준비* 측정 (전달 준비 원칙·§6 delivery_pack).

manuscript-expander 의 보조: 전체 원고를 강단 전달 직전에 가늠한다 — ① 전체·섹션별
전달 시간 ② 낭독 보조(긴 문장 호흡·원어/외국어 발음·숫자 읽기·긴 어절). 산문(언어
조정 산문 delivery_pack.md)은 짓지 않는다 — 측정만(voice_ingest/voice_resolve와 동일).

⚠️ 시간은 *대략* 추정이다. 실제 속도는 설교자·여백·회중 반응에 따라 다르다(--chars-per-min 보정).

- 순수 stdlib + voice_ingest.strip_markup/split_sentences 재사용.

사용:
    python scripts/delivery_pack.py --manuscript output/<run>/full_manuscript.md \
        [--target-min 30] [--chars-per-min 320] [--out output/<run>/delivery_pack.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import voice_ingest as vi
except ImportError as e:  # pragma: no cover
    print(f"[delivery_pack] voice_ingest 임포트 실패: {e}", file=sys.stderr)
    raise SystemExit(2)

DEFAULT_CHARS_PER_MIN = 320   # 한국어 강단 전달 가늠치(여백 포함). 설교자별 보정 권장.
TOLERANCE = 0.15              # 목표 대비 ±15% 이내면 'on_target'
LONG_SENTENCE = 120           # 이보다 긴 문장 → 호흡/분할 후보
LONG_WORD = 12                # 이보다 긴 어절 → 발음 부담 후보
SECTION_HOG = 0.40            # 한 섹션이 전체의 이 비율 초과 → 분량 쏠림 신호

RE_H2 = re.compile(r"^##\s+(.*)$")
RE_GREEK = re.compile(r"[Ͱ-Ͽ]+")
RE_HEBREW = re.compile(r"[֐-׿]+")
RE_LATIN = re.compile(r"[A-Za-z][A-Za-z'’.-]{1,}")
RE_NUMBER = re.compile(r"\d[\d,.:%]*")


def chars_no_ws(text: str) -> int:
    return len(re.sub(r"\s", "", text))


def minutes(n_chars: int, rate: float) -> float:
    return round(n_chars / rate, 1) if rate else 0.0


def split_sections(raw: str) -> list[tuple[str, str]]:
    """H2(##) 단위로 (제목, 본문). 첫 ## 앞 = (머리말) preamble."""
    lines = raw.splitlines()
    sections: list[tuple[str, list[str]]] = []
    cur_title, cur_body = "(머리말)", []
    for ln in lines:
        m = RE_H2.match(ln.strip())
        if m:
            sections.append((cur_title, cur_body))
            cur_title, cur_body = m.group(1).strip(), []
        else:
            cur_body.append(ln)
    sections.append((cur_title, cur_body))
    return [(t, "\n".join(b)) for t, b in sections if "".join(b).strip()]


def read_aloud_flags(text: str) -> dict:
    """낭독 장애물 — 측정만(자동 강제 아님). 설교자가 발음·호흡 표지를 단다."""
    sents = vi.split_sentences(text)
    long_sents = [s for s in sents if len(s) > LONG_SENTENCE]
    greek = sorted(set(RE_GREEK.findall(text)))
    hebrew = sorted(set(RE_HEBREW.findall(text)))
    latin = sorted({w for w in RE_LATIN.findall(text) if len(w) >= 2})
    numbers = sorted(set(RE_NUMBER.findall(text)))[:20]
    long_words = sorted({w for w in re.findall(r"[가-힣]+", text) if len(w) > LONG_WORD})
    return {
        "long_sentences": {
            "_note": f"{LONG_SENTENCE}자 초과 — 호흡/분할 후보(읽다 숨찬 곳).",
            "count": len(long_sents),
            "samples": [s[:60] + "…" for s in long_sents[:5]],
        },
        "pronunciation_aids": {
            "_note": "원어·외국어 — 강단에서 어떻게 *소리 낼지* 미리 정해 둔다(발음/대체).",
            "greek": greek, "hebrew": hebrew, "latin": latin[:30],
        },
        "spoken_numbers": {
            "_note": "숫자·연대·퍼센트 — 소리 내 읽을 형태로(예: 5:3 → '다섯 장 셋절').",
            "samples": numbers,
        },
        "long_words": {
            "_note": f"{LONG_WORD}자 초과 어절 — 발음 부담 후보.",
            "samples": long_words[:15],
        },
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="설교 원고 전달 준비 측정(시간+낭독 보조)")
    ap.add_argument("--manuscript", required=True, help="full_manuscript.md (.md/.txt)")
    ap.add_argument("--target-min", type=float, default=None, help="목표 설교 시간(분)")
    ap.add_argument("--chars-per-min", type=float, default=DEFAULT_CHARS_PER_MIN,
                    help=f"분당 글자수 가늠치(기본 {DEFAULT_CHARS_PER_MIN}; 설교자 보정)")
    ap.add_argument("--out", default=None, help="(선택) delivery_pack.json 산출")
    args = ap.parse_args(argv)

    m = Path(args.manuscript)
    if not m.is_file():
        print(f"[delivery_pack] 원고 없음: {m}", file=sys.stderr)
        return 2
    raw = m.read_text(encoding="utf-8", errors="replace")
    rate = args.chars_per_min

    full_text = vi.strip_markup(raw)
    total_chars = chars_no_ws(full_text)
    total_min = minutes(total_chars, rate)

    # 섹션별 시간 배분
    sections = []
    for title, body in split_sections(raw):
        c = chars_no_ws(vi.strip_markup(body))
        sections.append({
            "section": title, "chars": c, "minutes": minutes(c, rate),
            "share": round(c / total_chars, 3) if total_chars else 0,
        })
    hog = max(sections, key=lambda s: s["share"]) if sections else None
    balance_note = (f"분량 쏠림: '{hog['section']}' 가 전체의 {int(hog['share']*100)}% "
                    f"(>{int(SECTION_HOG*100)}%) — 배분 점검."
                    if hog and hog["share"] > SECTION_HOG else "섹션 배분 균형 양호.")

    # 목표 대비
    status, note = "estimate_only", "목표 미지정 — 추정만."
    if args.target_min:
        lo, hi = args.target_min * (1 - TOLERANCE), args.target_min * (1 + TOLERANCE)
        if total_min < lo:
            status, note = "under", f"목표보다 짧음(±{int(TOLERANCE*100)}% 밖) — 전개 보강(개요 내)."
        elif total_min > hi:
            status, note = "over", f"목표보다 김(±{int(TOLERANCE*100)}% 밖) — 군더더기 절제."
        else:
            status, note = "on_target", f"목표 ±{int(TOLERANCE*100)}% 이내."

    flags = read_aloud_flags(full_text)
    result = {
        "schema": "tspp.delivery_pack/1",
        "_note": ("강단 전달 준비 측정 — 시간(대략) + 낭독 보조. 실제 속도는 설교자·여백에 "
                  "따라 다르다(분당 글자수 보정). 측정만 — 언어 조정 산문(delivery_pack.md)은 "
                  "에이전트가 이 신호로 쓴다. 낭독 보조는 강제 아닌 *점검* 신호."),
        "target": str(m),
        "time": {
            "chars_no_whitespace": total_chars,
            "chars_per_min": rate,
            "estimated_minutes": total_min,
            "target_minutes": args.target_min,
            "status": status, "note": note,
        },
        "sections": sections,
        "balance_note": balance_note,
        "read_aloud": flags,
    }

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[delivery_pack] {m.name}")
    print(f"  전체 ≈ {total_min}분 (@{rate}자/분, {total_chars}자)"
          + (f"  · 목표 {args.target_min}분 → {status}" if args.target_min else ""))
    for s in sections:
        print(f"    · {s['section']}: ≈{s['minutes']}분 ({int(s['share']*100)}%)")
    print(f"  {balance_note}")
    ra = flags
    print(f"  낭독 보조 — 긴문장 {ra['long_sentences']['count']} · "
          f"원어 그리스어 {len(ra['pronunciation_aids']['greek'])}·히브리어 {len(ra['pronunciation_aids']['hebrew'])}·"
          f"영문 {len(ra['pronunciation_aids']['latin'])} · 숫자 {len(ra['spoken_numbers']['samples'])} · "
          f"긴어절 {len(ra['long_words']['samples'])}")
    print(f"  ※ {note}  (시간은 대략 — 설교자 보정 / 낭독보조는 점검 신호)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
