#!/usr/bin/env python3
r"""outline_preflight.py — 설교 개요 작성 *직전* 게이트 검증 + writing brief 수합.

작성 단계 연결의 첫 고리(보이스 고정 원칙 Phase 5 진입 전). 상류 산출물을 하나의
writing_brief.json 으로 묶고, **HITL 게이트**(묵상 씨앗·보이스 둘 다 승인)를
검증한다. 산문(개요)은 짓지 않는다 — 그것은 sermon-outline 스킬(에이전트)의 몫.
(voice_ingest/voice_resolve와 동일한 정직성: 스크립트는 구조·게이트, 프로세는 에이전트.)

  meditation_seed.json (sermon-mentor 산출, HITL)   ┐
  resolved_voice.json  (voice_resolve 산출, HITL)   ├─→ writing_brief.json  →  [에이전트가 개요 작성]
  EvidencePack.json    (선택, 인용 근거)            ┘                          →  [homiletic_audit 점검]

- 순수 stdlib.
- 게이트: 두 상류의 hitl.approved 가 모두 true 라야 gates.ready=true. 아니면 차단 신호.
- 불변식 전달: origin_memo 불가침 · tensions disposition 보존 · 인용은 EvidencePack 실제
  레코드만(유령인용 금지) · 보이스 injection_block 은 작성 시작 의례에서 선언.

사용:
    python scripts/outline_preflight.py \
        --meditation-seed output/<run>/meditation_seed.json \
        --resolved-voice  output/<run>/resolved_voice.json \
        [--evidence output/<run>/EvidencePack.json] \
        --out output/<run>/writing_brief.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STRUCTURE_HINT = [
    "머리말(occasion: 교회·예배·절기)",
    "본문 · 제목",
    "도입 — 회중을 본문 안으로(보이스 §2 거주-전향대로)",
    "논점 3–5 — 각 논점은 본문에 뿌리(rooted_in_text); supporting_refs는 설교자 참고(인용 아님)",
    "예화 — 본문장르에 맞게(persona 어조 차용)",
    "적용 — 본문→오늘 이 회중(audience); 본문 왜곡 시 중단(eisegesis 차단)",
    "긴장 보존 — tensions 를 평탄화하지 않음(disposition 따라)",
    "결단·부름 — tier에 맞게(전도=초청·제조 금지 / 예언=‘우리’)",
    "기도·마무리",
]


def die(msg: str, code: int = 2) -> int:
    print(f"[outline_preflight] {msg}", file=sys.stderr)
    return code


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_brief(seed: dict, rv: dict, evidence_path: Path | None) -> dict:
    notes: list[str] = []

    seed_ok = bool((seed.get("hitl") or {}).get("approved"))
    voice_ok = bool((rv.get("hitl") or {}).get("approved"))
    if not seed_ok:
        notes.append("meditation_seed 미승인(hitl.approved=false) — 작성 전 sermon-mentor HITL 필요.")
    if not voice_ok:
        notes.append("resolved_voice 미승인(hitl.approved=false) — 작성 전 보이스 고정 HITL 필요.")
    ready = seed_ok and voice_ok

    med = seed.get("meditation") or {}
    developed = med.get("developed") or {}
    resolved = rv.get("resolved") or {}
    l2 = (rv.get("layers") or {}).get("l2_situational") or {}
    components = l2.get("components") or {}

    ev = seed.get("evidence") or {}
    evidence_pack_ref = ev.get("evidence_pack_ref")
    evidence_present = False
    if evidence_path and evidence_path.is_file():
        evidence_pack_ref = str(evidence_path)
        evidence_present = True
    elif evidence_pack_ref and Path(evidence_pack_ref).is_file():
        evidence_present = True
    if not evidence_present:
        notes.append("EvidencePack 미연결 — 인용 없이 진행 가능하나, 인용 시 실제 레코드 필수(유령인용 금지).")

    return {
        "schema": "tspp.writing_brief/1",
        "_note": ("개요 작성 브리프. 에이전트는 gates.ready=true 일 때만 작성에 들어가고, "
                  "보이스 injection_block 을 먼저 선언한다(강단 의례). 불변식: origin_memo "
                  "불가침 · 인용은 EvidencePack 실제 레코드만 · 긴장 평탄화 금지 · 적용이 "
                  "본문 왜곡 시 중단. 스크립트는 수합만 — 개요(산문)는 에이전트가 쓴다."),
        "passage": seed.get("passage"),
        "passage_ref": seed.get("passage_ref"),
        "theme": seed.get("theme"),
        "occasion": seed.get("occasion"),

        "gates": {
            "meditation_seed_approved": seed_ok,
            "resolved_voice_approved": voice_ok,
            "evidence_present": evidence_present,
            "ready": ready,
            "notes": notes,
        },

        "message": {
            "_note": "사용자와 함께 빚은 메시지 후보. eisegesis_risk·supporting_refs 보존. 개요는 이 중 확정 메시지를 축으로.",
            "candidates": [
                {k: c.get(k) for k in ("statement", "text_anchor", "audience_hook",
                                       "eisegesis_risk", "eisegesis_note", "supporting_refs")}
                for c in (seed.get("message_candidates") or [])
            ],
        },
        "meditation_core": {
            "_note": "origin_memo 는 설교자 원본 — 불가침(덮어쓰지 않는다).",
            "origin_memo": (med.get("origin_memo") or {}).get("raw"),
            "developed_summary": developed.get("summary"),
            "rooted_in_text": developed.get("rooted_in_text"),
            "affect": med.get("affect"),
        },
        "tensions": [
            {"tension": t.get("tension"), "disposition": t.get("disposition"),
             "resolution_path": t.get("resolution_path")}
            for t in (med.get("tensions") or [])
        ],

        "voice": {
            "injection_block": rv.get("injection_block"),
            "lexicon_avoid": resolved.get("lexicon_avoid", []),
            "watch": resolved.get("watch", []),
            "persona_ref": components.get("persona_ref"),
            "tone_affinity": components.get("tone_affinity", []),
            "degraded": resolved.get("degraded", []),
        },
        "audience_modulation": components.get("audience_modulation"),

        "evidence": {
            "_note": "인용은 EvidencePack 의 실제 레코드에만(유령인용 차단). 설교자가 보는 자료이지 본문 권위를 대체하지 않는다.",
            "evidence_pack_ref": evidence_pack_ref,
            "keywords_used": ev.get("keywords_used"),
            "present": evidence_present,
        },
        "terms": (seed.get("handoff") or {}).get("terms", []),

        "output_target": "sermon_outline.md",
        "structure_hint": STRUCTURE_HINT,
        "next": ("gates.ready=true → sermon-outline 스킬이 개요 작성 → homiletic_audit.py 로 점검 → HITL."
                 if ready else "차단: 위 gates.notes 해소 후 재실행."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="설교 개요 작성 게이트 + writing brief 수합")
    ap.add_argument("--meditation-seed", required=True, help="meditation_seed.json (sermon-mentor)")
    ap.add_argument("--resolved-voice", required=True, help="resolved_voice.json (voice_resolve)")
    ap.add_argument("--evidence", default=None, help="EvidencePack.json (선택)")
    ap.add_argument("--out", required=True, help="산출 writing_brief.json")
    args = ap.parse_args(argv)

    seed_p, rv_p = Path(args.meditation_seed), Path(args.resolved_voice)
    if not seed_p.is_file():
        return die(f"meditation_seed 없음: {seed_p}")
    if not rv_p.is_file():
        return die(f"resolved_voice 없음: {rv_p}")
    ev_p = Path(args.evidence) if args.evidence else None

    brief = build_brief(load(seed_p), load(rv_p), ev_p)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")

    g = brief["gates"]
    print(f"[outline_preflight] → {out}")
    print(f"  passage: {brief['passage']} · theme: {brief['theme']}")
    print(f"  gates: seed={g['meditation_seed_approved']} voice={g['resolved_voice_approved']} "
          f"evidence={g['evidence_present']} → {'✅ READY' if g['ready'] else '⛔ BLOCKED'}")
    for n in g["notes"]:
        print(f"    - {n}")
    print(f"  message 후보: {len(brief['message']['candidates'])} · 긴장: {len(brief['tensions'])} · "
          f"용어: {len(brief['terms'])}")
    print(f"  next: {brief['next']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
