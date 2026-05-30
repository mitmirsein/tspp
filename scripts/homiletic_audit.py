#!/usr/bin/env python3
r"""homiletic_audit.py — 호밀레틱 보이스 계기판 (references/homiletic-voice.md §6).

학술 `tawp_audit §8`의 **전도판**. 학술 audit은 2인칭 호명·선포·당위를 *검출해
경고*하지만, 설교에서 그것은 *정당한 어법*이다 — 그래서 이 계기판은 그것들을
**잡지 않는다.** 정반대로 그것들의 *결핍*(강사화)과 *부패*(재판관화·선동)를 본다.

**비점수 HITL worklist다.** 점수·pass/fail·게이트가 아니라 "다시 읽어보라"는 신호다.
판단은 설교자가 한다(목회 윤리 헌법: 영적 권위는 목회자 귀속).

측정은 voice_ingest.py 를 재사용(DRY) — 같은 신호를 *호밀레틱으로 해석*만 한다.

- 순수 stdlib + voice_ingest 재사용.
- 잡지 않는 것: 직접 호명·케리그마 선포·권면·기도 종결(설교의 생명). 결핍이 경보다.
- 잡는 것: 강사화 · 재판관화 · 강단 상투구 · 논문체 전이 (+ 선택: 보이스 드리프트).

사용:
    python scripts/homiletic_audit.py --draft output/<run>/sermon_outline.md \
        [--resolved output/<run>/resolved_voice.json] \
        [--preacher-voice output/<run>/preacher_voice.json] \
        --out output/<run>/homiletic_audit.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# voice_ingest(같은 scripts/ 디렉터리) 재사용 — 측정 로직 중복 금지
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import voice_ingest as vi
except ImportError as e:  # pragma: no cover
    print(f"[homiletic_audit] voice_ingest 임포트 실패: {e}", file=sys.stderr)
    raise SystemExit(2)

# ── 부패 표지 (audit 고유 — voice_ingest의 *정당 어법* 표지와 별개) ──────────
LECTURE_MARKERS = [          # 강사화: 본문을 밖에서 *해설*하는 투
    "를 뜻하며", "라는 뜻", "을 의미합니다", "를 의미합니다", "의미합니다",
    "상징합니다", "당시", "학자들은", "헬라어", "히브리어", "원어로",
    "라고 볼 수 있습니다", "이 단어는", "어원", "문법적으로",
]
JUDGE_MARKERS = ["너희는", "너희가", "여러분은 반드시", "여러분의 믿음은",
                 "여러분은 회개", "여러분이 잘못", "당신들은"]  # 2인칭 정죄 경향
# 연대(§3-②의 해독제)는 *함의형* '우리'만 — 설교자도 그 말씀 아래 선다는 표지.
# "우리에게 은혜가" 같은 우발적 '우리'는 연대가 아니므로 제외(오인 방지).
SOLIDARITY_MARKERS = ["우리도", "우리 역시", "우리 자신", "우리 모두",
                      "우리 또한", "우리 안에", "우리 같은", "우리의 모습"]
DEAD_CLICHES = [             # 강단 상투구 (살아 있는 호명의 의례화)
    "은혜가 되시기 바랍니다", "은혜가 되시길", "은혜가 되시기를",
    "참 귀한", "줄로 믿습니다", "줄 믿습니다", "축원합니다",
    "되시기를 바랍니다", "되시기를 축원", "복 받으시기 바랍니다",
]
ACADEMIC_SYNTAX = [          # 논문체 전이 (TAWP authorial-voice §2.1 이식)
    "되어진다", "되어졌", "어질 수 있", "에 다름 아니다",
    "라고 말할 수 있을 것이다", "라고 할 수 있다", "하지 않으면 안 된다",
    "에 있어서", "필요성이 제기", "강조가 이루어", "아무리 강조해도 지나치",
    "본 설교는", "본고", "고찰하고자 한다", "살펴보고자 한다",
]


def count_markers(text: str, markers: list[str]) -> list[dict]:
    hits = [{"marker": m, "count": text.count(m)} for m in markers if m in text]
    return sorted(hits, key=lambda h: -h["count"])


def detect_lecturification(sig: dict, text: str) -> dict | None:
    """강사화 — 호명·질문이 사라지고 주석 밀도가 오르면 설교가 강의로 굳음.
    신호: scripture_ref_density↑ + address↓ + question↓ + hapnida↓(문어체)."""
    r, reg = sig["rhetoric"], sig["register"]
    subs = []
    if r["address_count"] == 0:
        subs.append("청중 호명 0 (여러분 등 전무)")
    if r["question_count"] == 0:
        subs.append("회중 질문 0")
    if reg["hapnida_ratio"] < 0.25:
        subs.append(f"문어체화 (hapnida_ratio={reg['hapnida_ratio']} < 0.25)")
    if r["scripture_ref_density"] > 3.0:
        subs.append(f"주석 밀도 높음 (ref_density={r['scripture_ref_density']} > 3.0)")
    lec = count_markers(text, LECTURE_MARKERS)
    lec_total = sum(h["count"] for h in lec)
    if lec_total >= 4:
        subs.append(f"강의투 표지 {lec_total}회")
    # 강사화: 생명 표지(호명·질문)가 결핍된 채 해설 신호가 있으면 점등
    if (("청중 호명 0 (여러분 등 전무)" in subs or "회중 질문 0" in subs)
            and (lec_total >= 4 or r["scripture_ref_density"] > 3.0
                 or reg["hapnida_ratio"] < 0.25)):
        return {"corruption": "강사화 (lecture-ification)",
                "fired_signals": subs, "markers": lec[:6],
                "reread": "homiletic-voice.md §3-① · §6 · 팔레트 tier.expository/catechetical.watch",
                "severity": "signal"}
    return None


def detect_judgeification(text: str) -> dict | None:
    """재판관화 — 권면·정죄가 '우리' 없이 회중 위에서 떨어짐."""
    judge = count_markers(text, JUDGE_MARKERS)
    judge_total = sum(h["count"] for h in judge)
    solidarity = sum(text.count(m) for m in SOLIDARITY_MARKERS)
    if judge_total >= 2 and solidarity == 0:
        return {"corruption": "재판관화 (judge-over-congregation)",
                "fired_signals": [f"2인칭 정죄 경향 {judge_total}회",
                                  "'우리'(연대) 0회 — 설교자가 면제된 자리"],
                "markers": judge[:6],
                "reread": "homiletic-voice.md §3-② · §6 · 팔레트 tier.prophetic.watch",
                "severity": "signal"}
    if judge_total >= 4 and solidarity < judge_total // 2:
        return {"corruption": "재판관화 (judge-over-congregation)",
                "fired_signals": [f"2인칭 정죄 {judge_total}회 vs '우리' {solidarity}회 (연대 부족)"],
                "markers": judge[:6],
                "reread": "homiletic-voice.md §3-② · §6",
                "severity": "signal"}
    return None


def detect_dead_cliches(text: str) -> dict | None:
    """강단 상투구 — 살아 있는 호명이 닳은 의례로."""
    hits = count_markers(text, DEAD_CLICHES)
    if hits:
        return {"corruption": "강단 상투구 (dead pulpit clichés)",
                "fired_signals": [f"죽은 관용구 {sum(h['count'] for h in hits)}회"],
                "markers": hits,
                "reread": "homiletic-voice.md §2.1 · §6",
                "severity": "signal"}
    return None


def detect_academic_syntax(text: str) -> dict | None:
    """논문체 전이 — 이중피동·과잉 명사화·직역 상투구."""
    hits = count_markers(text, ACADEMIC_SYNTAX)
    if hits:
        return {"corruption": "논문체 전이 (academic syntax)",
                "fired_signals": [f"논문체 표지 {sum(h['count'] for h in hits)}회"],
                "markers": hits,
                "reread": "homiletic-voice.md §2.1 (강단의 한국어)",
                "severity": "signal"}
    return None


def absence_warnings(sig: dict) -> list[str]:
    """생명 표지 결핍 — §6: '결핍이 경보이지 존재가 경보가 아니다.'"""
    r = sig["rhetoric"]
    out = []
    if r["address_count"] == 0:
        out.append("직접 호명 없음 — 회중을 향해 돌아서지 않았는가? (강사화 징후)")
    if r["question_count"] == 0:
        out.append("회중 질문 없음 — 회중과 함께 생각하는가, 통보하는가?")
    if r["prayer_marker_count"] == 0:
        out.append("기도·응답 종결 표지 없음 — 응답으로의 동선이 닫혔는가?")
    return out


def drift_check(sig: dict, text: str, pv: dict) -> list[dict]:
    """보이스 드리프트 — preacher_voice.json(L1-개인)에서 벗어났는가.
    preacher_voice.drift_check.watch 정신: 형식 점수 아님, 다시 읽어보라 신호."""
    out = []
    reg = sig["register"]
    card_hap = (pv.get("register") or {}).get("hapnida_ratio")
    if isinstance(card_hap, (int, float)) and reg["hapnida_ratio"] < card_hap - 0.2:
        out.append({"drift": "문어체화",
                    "basis": f"draft hapnida_ratio={reg['hapnida_ratio']} vs 카드 {card_hap} (급락)",
                    "reread": "preacher_voice.drift_check"})
    sig_terms = (pv.get("lexicon") or {}).get("signature_terms", [])
    if sig_terms:
        present = [t for t in sig_terms if t in text]
        if not present:
            out.append({"drift": "시그니처 표현 소실",
                        "basis": f"카드 signature_terms {sig_terms} 가 초안에 전무",
                        "reread": "preacher_voice.drift_check"})
    return out


def lexicon_avoid_hits(text: str, resolved: dict) -> list[dict]:
    """resolved_voice.json 의 lexicon_avoid 표현이 초안에 출현했는가."""
    avoid = (resolved.get("resolved") or {}).get("lexicon_avoid", [])
    out = []
    for a in avoid:
        # lexicon_avoid 항목은 "표현(설명)" 형태가 섞임 — 괄호 앞 핵심구만 본다
        core = a.split("(")[0].strip().rstrip("~").strip()
        if core and len(core) >= 2 and core in text:
            out.append({"avoid": a, "core": core, "count": text.count(core)})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="호밀레틱 보이스 계기판 (비점수 HITL worklist)")
    ap.add_argument("--draft", required=True, help="설교 개요/원고 (.md/.txt)")
    ap.add_argument("--resolved", default=None,
                    help="resolved_voice.json (lexicon_avoid 출현 점검)")
    ap.add_argument("--preacher-voice", default=None,
                    help="preacher_voice.json (보이스 드리프트 점검)")
    ap.add_argument("--out", required=True, help="산출 homiletic_audit.json")
    args = ap.parse_args(argv)

    draft = Path(args.draft)
    if not draft.is_file():
        print(f"[homiletic_audit] 초안 없음: {draft}", file=sys.stderr)
        return 2
    raw = draft.read_text(encoding="utf-8", errors="replace")
    text = vi.strip_markup(raw)
    sig = vi.analyze_one(draft.name, raw)  # voice_ingest 재사용

    worklist = []
    for det in (detect_lecturification(sig, text), detect_judgeification(text),
                detect_dead_cliches(text), detect_academic_syntax(text)):
        if det:
            worklist.append(det)

    absences = absence_warnings(sig)

    drift = []
    if args.preacher_voice:
        p = Path(args.preacher_voice)
        if p.is_file():
            drift = drift_check(sig, text, json.loads(p.read_text(encoding="utf-8")))

    avoid_hits = []
    if args.resolved:
        p = Path(args.resolved)
        if p.is_file():
            avoid_hits = lexicon_avoid_hits(text, json.loads(p.read_text(encoding="utf-8")))

    result = {
        "schema": "tspp.homiletic_audit/1",
        "_note": ("비점수 HITL worklist — '다시 읽어보라' 신호. pass/fail·게이트가 아니다. "
                  "판단은 설교자가 한다(영적 권위 귀속). 직접 호명·케리그마 선포·권면·기도 "
                  "종결은 *잡지 않는다*(설교의 생명) — 결핍이 경보다."),
        "target": str(draft),
        "guardrail": ("직접 호명/케리그마 선포/권면 당위/기도 종결 = 정당 어법, 검출 대상 아님. "
                      "학술 tawp_audit §8과 반대."),
        "measured": {
            "cadence": sig["cadence"], "rhetoric": sig["rhetoric"],
            "register": sig["register"],
        },
        "worklist": worklist,
        "absence_warnings": absences,
        "voice_drift": drift,
        "lexicon_avoid_hits": avoid_hits,
        "summary": (f"{len(worklist)} 부패 신호 · {len(absences)} 결핍 경보 · "
                    f"{len(drift)} 드리프트 · {len(avoid_hits)} 회피표현 출현 — 전부 HITL 판단"),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # 사람이 읽는 보고
    print(f"[homiletic_audit] {draft.name} → {out}")
    print(f"  {result['summary']}")
    print(f"  ※ {result['guardrail']}")
    for w in worklist:
        print(f"  ⚠️ {w['corruption']}")
        for s in w["fired_signals"]:
            print(f"       - {s}")
        print(f"       ↳ 재독: {w['reread']}")
    for a in absences:
        print(f"  ○ 결핍: {a}")
    for d in drift:
        print(f"  ↻ 드리프트: {d['drift']} — {d['basis']}")
    for h in avoid_hits:
        print(f"  ✗ 회피표현 출현: '{h['core']}' {h['count']}회 ({h['avoid']})")
    if not (worklist or absences or drift or avoid_hits):
        print("  ✓ 점등된 신호 없음 — 단, 계기판은 안전망이지 보이스의 원인이 아니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
