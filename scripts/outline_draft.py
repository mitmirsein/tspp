#!/usr/bin/env python3
"""Render writing_brief.json into a human-fillable sermon outline draft.

This script does not ghostwrite a sermon. It turns the approved preflight brief
into a Markdown scaffold that keeps the original meditation, voice guidance,
message candidates, tensions, and evidence references visible for the preacher.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def arr(v: object) -> list[Any]:
    return v if isinstance(v, list) else []


def text(v: object) -> str:
    return v if isinstance(v, str) else ""


def build_outline_draft_md(brief: dict[str, Any]) -> str:
    lines: list[str] = []
    gates = brief.get("gates") or {}
    med = brief.get("meditation_core") or {}
    voice = brief.get("voice") or {}
    evidence = brief.get("evidence") or {}

    lines.append(f"# 설교 개요 초안 — {text(brief.get('passage')) or '(본문 미상)'}")
    lines.append("")
    lines.append("> 이 파일은 설교자가 직접 채우는 골격입니다. AI가 설교를 대필하지 않습니다.")
    lines.append(
        "> 게이트: 씨앗 "
        f"{'OK' if gates.get('meditation_seed_approved') else 'NO'} · 보이스 "
        f"{'OK' if gates.get('resolved_voice_approved') else 'NO'} · 근거 "
        f"{'OK' if gates.get('evidence_present') else 'NO'} -> "
        f"{'READY' if gates.get('ready') else 'BLOCKED'}"
    )
    lines.append("")
    if brief.get("theme"):
        lines.append(f"**주제**: {text(brief.get('theme'))}")
        lines.append("")

    lines.append("## 묵상 핵심 (불가침 — 처음 생각)")
    origin = med.get("origin_memo")
    raw = origin.get("raw") if isinstance(origin, dict) else origin
    if raw:
        lines.append("> " + "\n> ".join(text(raw).split("\n")))
    if med.get("developed_summary"):
        lines.append(f"- 발전: {text(med.get('developed_summary'))}")
    if med.get("rooted_in_text"):
        lines.append(f"- 본문 정착: {text(med.get('rooted_in_text'))}")
    if med.get("affect"):
        lines.append(f"- 정서: {text(med.get('affect'))}")
    lines.append("")

    lines.append("## 보이스 (강단 어법 가이드 — 원고엔 남기지 않음)")
    if voice.get("injection_block"):
        lines.append("```")
        lines.append(text(voice.get("injection_block")))
        lines.append("```")
    if arr(voice.get("lexicon_avoid")):
        lines.append(f"- 피할 표현: {' · '.join(str(x) for x in arr(voice.get('lexicon_avoid')))}")
    if arr(voice.get("watch")):
        lines.append(f"- 주의: {' · '.join(str(x) for x in arr(voice.get('watch')))}")
    lines.append("")

    lines.append("## 메시지 후보 (택일·재정착)")
    candidates = arr((brief.get("message") or {}).get("candidates"))
    if candidates:
        for c in candidates:
            if not isinstance(c, dict):
                continue
            lines.append(f"- **{text(c.get('statement'))}**")
            if c.get("text_anchor"):
                lines.append(f"  - 본문 정착: {text(c.get('text_anchor'))}")
            if c.get("eisegesis_risk"):
                note = f" — {text(c.get('eisegesis_note'))}" if c.get("eisegesis_note") else ""
                lines.append(f"  - eisegesis 위험: {text(c.get('eisegesis_risk'))}{note}")
    else:
        lines.append("- (씨앗에 message_candidates 없음 — 설교자가 본문에서 직접 도출)")
    lines.append("")

    tensions = arr(brief.get("tensions"))
    if tensions:
        lines.append("## 긴장 (봉합 금지)")
        for t in tensions:
            if isinstance(t, dict):
                lines.append(f"- {text(t.get('tension'))} [{text(t.get('disposition'))}]")
        lines.append("")

    lines.append("## 개요 (아래 골격을 채우세요)")
    hints = arr(brief.get("structure_hint"))
    if hints:
        for h in hints:
            lines.append(f"### {text(h)}")
            lines.append("")
    else:
        for h in ["도입", "본문 전개", "적용", "결론"]:
            lines.append(f"### {h}")
            lines.append("")

    lines.append("## 근거 메모")
    keywords = evidence.get("keywords_used") if isinstance(evidence, dict) else {}
    if isinstance(keywords, dict):
        kws = [*arr(keywords.get("ko")), *arr(keywords.get("en"))]
        if kws:
            lines.append(f"- 키워드: {', '.join(str(x) for x in kws)}")
    if isinstance(evidence, dict) and evidence.get("evidence_pack_ref"):
        lines.append(f"- EvidencePack: {text(evidence.get('evidence_pack_ref'))} · evidence_list.md 참조")
    terms = arr(brief.get("terms"))
    if terms:
        lines.append("- 용어:")
        for t in terms:
            if isinstance(t, dict):
                ko = text(t.get("canonical_ko") or t.get("concept"))
                en = text(t.get("en"))
                grc = text(t.get("grc"))
                tail = " · ".join(x for x in [en, grc] if x)
                lines.append(f"  - {ko}{f' ({tail})' if tail else ''}")
    lines.append("")
    lines.append("---")
    lines.append("*초안 골격 — TSPP writing_brief에서 생성. 최종 sign-off는 설교자의 것입니다.*")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--brief", required=True, help="writing_brief.json")
    ap.add_argument("--out", required=True, help="sermon_outline_draft.md")
    args = ap.parse_args()

    brief_path = Path(args.brief)
    if not brief_path.is_file():
        print(f"[outline_draft] writing_brief 없음: {brief_path}")
        return 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    out.write_text(build_outline_draft_md(brief), encoding="utf-8")
    print(f"[outline_draft] -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
