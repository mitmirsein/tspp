#!/usr/bin/env python3
"""ledger_update.py — 설교 이력 장부 적립 (P1-5).

sign-off된 run의 산출물에서 **기존 필드만 복사**해 `output/sermon_ledger.json`에
한 줄(entry)로 적립한다. 스크립트는 요약을 *짓지 않는다* — seed/outline 등에
이미 있는 문장과 값만 옮긴다(§11).

장부는 회중 데이터가 아니라 **설교자 자신의 산출 이력**이다(§8 위반 아님 —
AI가 회중을 추정하는 게 아니라 설교자의 과거 설교를 비춰준다). 로컬 자산(§9,
output/은 gitignore).

수집 필드 (있는 것만):
- run · 적립일 · passage(seed) · theme(seed) · genre/tier/season(resolved_voice)
- outline 승인 여부 · 추정 전달 시간(delivery_pack) · 사용 예화 id(개요·원고의
  `(예화금고: id)` 표기) · retro의 실측 시간·설교일(sermon_retro.md frontmatter)

사용:
    python scripts/ledger_update.py --run <run> \
        [--ledger output/sermon_ledger.json] [--workspace .]
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ILLUST_RE = re.compile(r"\(예화금고:\s*([A-Za-z0-9_\-가-힣]+)\s*\)")


def read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_frontmatter(p: Path) -> dict:
    fm: dict[str, str] = {}
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return fm
    if not text.startswith("---"):
        return fm
    end = text.find("\n---", 3)
    if end == -1:
        return fm
    for line in text[3:end].splitlines():
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def collect_entry(run: str, workspace: Path) -> dict:
    out = workspace / "output" / run
    inp = workspace / "input" / run

    seed = read_json(inp / "meditation_seed.json") or read_json(out / "meditation_seed.json")
    rv = read_json(inp / "resolved_voice.json") or read_json(out / "resolved_voice.json")
    delivery = read_json(out / "delivery_pack.json")
    outline_fm = read_frontmatter(out / "sermon_outline.md")
    retro_fm = read_frontmatter(out / "sermon_retro.md")

    l2 = ((rv.get("layers") or {}).get("l2_situational") or {}).get("inputs") or {}

    illustrations: list[str] = []
    for doc in ("sermon_outline.md", "full_manuscript.md"):
        p = out / doc
        if p.is_file():
            for m in ILLUST_RE.finditer(p.read_text(encoding="utf-8")):
                if m.group(1) not in illustrations:
                    illustrations.append(m.group(1))

    # 계기판 부패 신호 이름 — homiletic_audit --ledger 추세 대조의 근거(P2-8)
    audit_signals: list[str] = []
    for doc in ("homiletic_audit.json", "homiletic_audit_manuscript.json"):
        for w in (read_json(out / doc).get("worklist") or []):
            name = w.get("corruption")
            if name and name not in audit_signals:
                audit_signals.append(name)

    entry = {
        "run": run,
        "recorded_at": datetime.date.today().isoformat(),
        "passage": seed.get("passage"),
        "theme": seed.get("theme") or outline_fm.get("theme"),
        "genre": l2.get("genre"),
        "tier": l2.get("tier"),
        "season": l2.get("season"),
        "outline_approved": str(outline_fm.get("approved", "")).lower() in ("true", "yes", "1"),
        "seed_approved": bool((seed.get("hitl") or {}).get("approved")),
        "estimated_minutes": ((delivery.get("time") or {}).get("estimated_minutes")),
        "illustrations": illustrations,
        "audit_signals": audit_signals,
        "preached_on": retro_fm.get("preached_on") or None,
        "actual_minutes": float(retro_fm["actual_minutes"])
        if str(retro_fm.get("actual_minutes", "")).replace(".", "", 1).isdigit() else None,
    }
    return entry


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="설교 이력 장부 적립 — 기존 필드 복사만")
    ap.add_argument("--run", required=True)
    ap.add_argument("--workspace", type=Path, default=ROOT)
    ap.add_argument("--ledger", type=Path, help="기본: <workspace>/output/sermon_ledger.json")
    args = ap.parse_args(argv)

    ledger_path = args.ledger or args.workspace / "output" / "sermon_ledger.json"
    out_dir = args.workspace / "output" / args.run
    if not out_dir.is_dir():
        print(f"[ledger] run 산출 폴더가 없습니다: {out_dir}", file=sys.stderr)
        return 2

    entry = collect_entry(args.run, args.workspace)

    ledger = read_json(ledger_path) or {
        "schema_version": 1,
        "_note": ("설교 이력 장부(P1-5). 설교자 자신의 산출 이력 — 회중 데이터가 아니다(§8). "
                  "로컬 자산(§9). series_check.py가 새 run과 대조해 흐름 신호를 만든다. "
                  "스크립트는 기존 필드만 복사한다 — 요약을 짓지 않는다(§11)."),
        "entries": [],
    }
    entries = ledger.setdefault("entries", [])
    existing = next((i for i, e in enumerate(entries) if e.get("run") == args.run), None)
    action = "갱신" if existing is not None else "적립"
    if existing is not None:
        entries[existing] = entry
    else:
        entries.append(entry)
    entries.sort(key=lambda e: (e.get("preached_on") or e.get("recorded_at") or ""))

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[ledger] {action}: {args.run} → {ledger_path} (총 {len(entries)}건)")
    print(f"  passage={entry['passage']} · theme={str(entry['theme'])[:40]}")
    print(f"  genre={entry['genre']} tier={entry['tier']} season={entry['season']}"
          f" · outline_approved={entry['outline_approved']}"
          f" · 예화 {len(entry['illustrations'])}건")
    if not entry["outline_approved"]:
        print("  ⚠️ 개요 미승인 상태로 적립됨 — sign-off 후 재실행하면 갱신된다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
