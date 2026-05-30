#!/usr/bin/env python3
r"""voice_resolve.py — 보이스 3층을 합성해 *주입할 보이스*를 산출한다 (CONCEPT §4-5·§5).

추출(voice_ingest) → **주입(이 스크립트)** 의 연결 고리.

  L1 보편 (references/homiletic-voice.md)      ─ 모든 설교의 바닥(항상)
    + L1-개인 (preacher_voice.json)            ─ 이 설교자 지문 (opt-in; 없으면 degraded)
    + L2-상황 (homiletic_voice_palette.json)   ─ 본문장르×tier×절기×청중 4축 합성

이 스크립트는 *구조를 합성*한다 — 산문을 지어내지 않는다(voice_ingest와 동일한
정직성: 스크립트는 측정·합성, 산문 렌더는 에이전트의 강단 의례에서). 산출
resolved_voice.json + 사람이 읽는 injection_block 은 작성 에이전트가 개요(Phase 5)
진입 *전*에 선언할 보이스다(HITL 승인 후 주입).

- 순수 stdlib (외부 패키지 0 — MS_Dev 가드레일).
- 헌법 준수: 청중 축은 audience_profile.json 있을 때만 활성(AI 회중 추정 금지).
- L1 보편은 항상 바닥. preacher_voice 미제공/미승인은 degraded로 정직하게 표기.

사용:
    python scripts/voice_resolve.py \
        --genre psalm_lament --tier pastoral --season lent \
        --preacher-voice output/<run>/preacher_voice.json \   # 선택(opt-in)
        --audience input/audience_profile.json \               # 선택
        --out output/<run>/resolved_voice.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ── L1 보편 핵심 선언 (references/homiletic-voice.md §5 step 2 — 권위 원본은 그 헌장) ──
L1_CHARTER = "references/homiletic-voice.md"
L1_CORE = ("나는 본문 안에 서서 회중을 향해 돌아선 설교자다. "
           "나는 본문을 해설하지 않고 그 안에 선다. "
           "나는 회중을 채점하지 않는다 — 정죄는 '우리'로 향한다. "
           "나는 결단을 제조하지 않고 청한다.")

# ── conflict_rule 보조: 본문장르가 절기 색에 눌리면 안 되는 대표 충돌 ─────────
#    (palette resolution.conflict_rule = text_genre 우선)
SOMBER_GENRES = {"psalm_lament"}
CELEBRATORY_SEASONS = {"easter", "christmas", "pentecost"}

# ── 청중 조율: audience_profile.json 에서 읽을 키(있는 것만) ──────────────────
AUDIENCE_KEYS = {
    "affect": "정서", "정서": "정서",
    "faith_texture": "신앙색채", "신앙색채": "신앙색채",
    "situation": "상황", "상황": "상황",
    "liturgical_setting": "예전위치", "예전위치": "예전위치",
    "age": "연령", "연령": "연령",
}


def die(msg: str, code: int = 2) -> "int":
    print(f"[voice_resolve] {msg}", file=sys.stderr)
    return code


def lookup(axis_list: list, key: str):
    for item in axis_list:
        if item.get("key") == key:
            return item
    return None


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_l2(palette: dict, genre: str, tier: str, season: str | None,
               audience: dict | None) -> tuple[dict, list[str]]:
    """4축을 구조적으로 합성. 산문은 만들지 않고 *구성 요소*를 모은다."""
    axes = palette["axes"]
    notes: list[str] = []

    g = lookup(axes["text_genre"], genre)
    t = lookup(axes["tier"], tier)
    if g is None:
        raise KeyError(f"unknown genre '{genre}'. valid: "
                       f"{[x['key'] for x in axes['text_genre']]}")
    if t is None:
        raise KeyError(f"unknown tier '{tier}'. valid: "
                       f"{[x['key'] for x in axes['tier']]}")

    s = None
    if season and season != "ordinary":
        s = lookup(axes["season"], season)
        if s is None:
            raise KeyError(f"unknown season '{season}'. valid: "
                           f"{[x['key'] for x in axes['season']]}")
    elif season == "ordinary":
        notes.append("절기 색 없음(ordinary/연중) — 본문장르·tier가 register 주도.")

    # 청중 조율 (있을 때만 — 헌법: AI 추정 금지)
    audience_mod = None
    if audience:
        picked = {}
        for k, v in audience.items():
            label = AUDIENCE_KEYS.get(k)   # _comment·schema 등은 None → 자동 건너뜀
            if not label or not v:
                continue
            if isinstance(v, dict):        # {value, _comment} 형식 허용
                v = v.get("value") or v.get("summary") or v.get("note")
            if v:
                picked[label] = v
        if picked:
            audience_mod = picked
        else:
            notes.append("audience_profile 제공됐으나 인식 키 없음 — 청중 축 비활성.")
    else:
        notes.append("audience_profile 미제공 — 청중 축 비활성(보편 폴백, 회중 추정 금지).")

    # 충돌 점검 (conflict_rule = text_genre 우선)
    conflict = None
    if genre in SOMBER_GENRES and season in CELEBRATORY_SEASONS:
        conflict = (f"절기({season}, 선포·기쁨 색)와 본문장르({genre}, 탄식)이 충돌 → "
                    f"text_genre 우선: 탄식의 결을 죽이지 않고 그 안에서 소망을 연다"
                    f"(절기가 본문을 덮지 않음).")

    # lexicon_avoid 병합 (장르 + 절기 watch 유래는 watch로 분리)
    lex_avoid = list(g.get("lexicon_avoid", []))

    # watch(계기판 주시 신호) 병합 — homiletic-voice §6 연결
    watch = []
    if g.get("watch"):
        watch.append(g["watch"])
    if t.get("watch"):
        watch.append(t["watch"])
    if s and s.get("watch"):
        watch.append(s["watch"])

    l2 = {
        "inputs": {"genre": genre, "tier": tier,
                   "season": season or "ordinary",
                   "audience": "active" if audience_mod else "inactive"},
        "components": {
            "genre_native_register": g["native_register"],
            "genre_cadence": g["cadence"],
            "tier_tightens": t["tightens"],
            "season_color": (s["register_color"] if s else None),
            "audience_modulation": audience_mod,
            "persona_ref": t.get("persona_ref"),         # tier의 어조 차용원(음성 초상)
            "tone_affinity": g.get("tone_affinity", []),  # 장르가 빌리는 어조(persona keys)
        },
        "lexicon_avoid": lex_avoid,
        "watch": watch,
        "conflict_resolution": conflict,
        "render_hint": ("에이전트는 위 components 를 *한 문장 L2 stance* 로 렌더한다 "
                        "(text_genre 1차, tier 동선, season 색, audience 음높이 순). "
                        "스크립트는 산문을 짓지 않는다."),
    }
    return l2, notes


def build(palette_path: Path, genre: str, tier: str, season: str | None,
          preacher_voice_path: Path | None, audience_path: Path | None) -> dict:
    palette = load_json(palette_path)
    degraded: list[str] = []

    # ── L1 보편 (항상) ──
    l1_universal = {"charter_ref": L1_CHARTER, "core": L1_CORE, "active": True}

    # ── L1-개인 (opt-in) ──
    l1_personal = {"active": False, "source": None}
    if preacher_voice_path:
        pv = load_json(preacher_voice_path)
        approved = (pv.get("hitl") or {}).get("approved", False)
        l1_personal = {
            "active": True,
            "source": str(preacher_voice_path),
            "hitl_approved": approved,
            "stance": (pv.get("stance") or {}).get("text"),
            "cadence": (pv.get("cadence") or {}).get("summary"),
            "signature_terms": (pv.get("lexicon") or {}).get("signature_terms", []),
            "tends_to_avoid": (pv.get("lexicon") or {}).get("tends_to_avoid", []),
            "register": (pv.get("register") or {}).get("summary"),
            "closing": (pv.get("closing") or {}).get("decision_invitation"),
        }
        if not approved:
            degraded.append("preacher_voice 미승인(hitl.approved=false) — 주입 전 HITL 승인 필요.")
    else:
        degraded.append("L1-개인 미적용(opt-out) — L1 보편 + L2 상황만. 정상 degraded.")

    # ── L2-상황 ──
    audience = load_json(audience_path) if audience_path else None
    l2, l2_notes = resolve_l2(palette, genre, tier, season, audience)
    degraded.extend(l2_notes)

    # ── 병합 (lexicon_avoid: L2 + L1-개인 회피) ──
    merged_avoid = list(dict.fromkeys(
        l2["lexicon_avoid"] + (l1_personal.get("tends_to_avoid") or [])))

    resolved = {
        "stance_layers": [
            l1_universal["core"],
            l1_personal.get("stance") if l1_personal["active"] else None,
            "(L2 stance — 에이전트가 components 로 렌더)",
        ],
        "lexicon_avoid": merged_avoid,
        "watch": l2["watch"],
        "degraded": degraded,
    }

    # ── 사람이 읽는 주입 블록 (강단 의례 §5) ──
    lines = ["[강단에 서기 전 — 보이스 주입 선언]  (원고에는 남기지 않는다)",
             f"· L1 보편: {L1_CORE}",
             f"           (권위 원본: {L1_CHARTER})"]
    if l1_personal["active"] and l1_personal.get("stance"):
        flag = "" if l1_personal.get("hitl_approved") else "  ⚠️미승인"
        lines.append(f"· L1-개인{flag}: {l1_personal['stance']}")
        if l1_personal.get("signature_terms"):
            lines.append(f"           시그니처: {', '.join(l1_personal['signature_terms'])}")
    else:
        lines.append("· L1-개인: (미적용 — 보편 헌장만)")
    lines.append("· L2-상황 (에이전트가 한 문장으로 렌더):")
    c = l2["components"]
    lines.append(f"    - 본문장르: {c['genre_native_register']}")
    lines.append(f"    - tier 동선: {c['tier_tightens']}")
    if c["season_color"]:
        lines.append(f"    - 절기 색: {c['season_color']}")
    if c["audience_modulation"]:
        am = "; ".join(f"{k}={v}" for k, v in c["audience_modulation"].items())
        lines.append(f"    - 청중 조율: {am}")
    lines.append(f"    - cadence: {c['genre_cadence']}")
    if c.get("persona_ref"):
        aff = c.get("tone_affinity") or []
        affs = f" (+장르 어조 친화: {', '.join(aff)})" if aff else ""
        lines.append(f"    - 어조 차용원(persona): {c['persona_ref']}{affs}  ※어조만 차용, 견해 아님")
    if l2["conflict_resolution"]:
        lines.append(f"· ⚖️ 충돌해소: {l2['conflict_resolution']}")
    if merged_avoid:
        lines.append(f"· 피할 표현: {', '.join(merged_avoid)}")
    if l2["watch"]:
        lines.append("· 계기판 주시(homiletic-voice §6):")
        for w in l2["watch"]:
            lines.append(f"    - {w}")
    if degraded:
        lines.append("· degraded:")
        for d in degraded:
            lines.append(f"    - {d}")
    injection_block = "\n".join(lines)

    return {
        "schema": "tspp.resolved_voice/1",
        "_note": ("보이스 3층 합성 결과. 작성 에이전트가 개요(Phase 5) 진입 *전*에 "
                  "injection_block 을 선언하고 L2 stance 를 한 문장으로 렌더한다. "
                  "HITL 승인(hitl.approved) 전엔 주입하지 않는다. 스크립트는 구조만 "
                  "합성하고 산문은 짓지 않는다."),
        "layers": {
            "l1_universal": l1_universal,
            "l1_personal": l1_personal,
            "l2_situational": l2,
        },
        "resolved": resolved,
        "injection_block": injection_block,
        "hitl": {
            "approved": False,
            "approved_by": None,
            "approved_at": None,
            "notes": "보이스 고정은 개요 진입 전 HITL 승인. 승인 전 작성에 주입 금지.",
        },
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="보이스 3층 합성 → 주입할 보이스(resolved_voice.json)")
    ap.add_argument("--genre", required=True, help="본문장르 키 (예: psalm_lament)")
    ap.add_argument("--tier", required=True, help="설교 유형 키 (예: pastoral)")
    ap.add_argument("--season", default=None, help="절기 키 (예: lent; 생략=ordinary)")
    ap.add_argument("--preacher-voice", default=None,
                    help="preacher_voice.json (L1-개인, opt-in)")
    ap.add_argument("--audience", default=None,
                    help="audience_profile.json (청중, 목회자 작성)")
    ap.add_argument("--palette", default="data/homiletic_voice_palette.json",
                    help="L2 팔레트 경로")
    ap.add_argument("--out", required=True, help="산출 resolved_voice.json 경로")
    args = ap.parse_args(argv)

    palette_path = Path(args.palette)
    if not palette_path.is_file():
        return die(f"팔레트를 찾을 수 없음: {palette_path}")
    pv_path = Path(args.preacher_voice) if args.preacher_voice else None
    if pv_path and not pv_path.is_file():
        return die(f"preacher_voice 파일 없음: {pv_path}")
    aud_path = Path(args.audience) if args.audience else None
    if aud_path and not aud_path.is_file():
        return die(f"audience_profile 파일 없음: {aud_path}")

    try:
        result = build(palette_path, args.genre, args.tier, args.season,
                       pv_path, aud_path)
    except KeyError as e:
        return die(str(e).strip('"'))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[voice_resolve] → {out}")
    print()
    print(result["injection_block"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
