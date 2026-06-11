#!/usr/bin/env python3
"""illustration_index.py — 예화 금고 인덱서 (P1-4).

날조 금지(§7) 아래에서 예화의 유일한 합법 공급원: **설교자 소유의 예화 카드**.
카드는 `input/illustrations/<id>.json`(설교자 자산, gitignore §9)에 설교자가
직접 기록하고, 에이전트는 이 스크립트로 *조회·사용 기록*만 한다 — 예화를
생성하지 않는다. 금고가 비면 예화 없이 쓰고 "예화 후보 찾기"를 설교자에게
worklist로 넘긴다.

카드 스키마: `data/illustration_card.example.json`

명령:
    list                          금고 전체 목록 + 위생 신호
    search --query "회개 열매"     내용어 매칭 검색 (+ --kind, --tag)
    use --id <id> --run <run>     사용 기록(used_in) 추가
    check                         금고 위생 점검(스키마·동의·익명화·재사용)

안전 신호 (§8 회중 익명성):
- kind=congregation 카드가 anonymized!=true 또는 consent!=true면 **사용 차단 권고**.
- 같은 카드의 최근 재사용은 신호로 표시(판단은 설교자 §10).

순수 stdlib · 측정·조회만, 산문 없음(§11).
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VAULT = ROOT / "input" / "illustrations"
_WORD_RE = re.compile(r"[가-힣a-zA-Z0-9]{2,}")

REQUIRED_FIELDS = ("id", "title", "body", "kind", "source")
KINDS = ("personal", "congregation", "history", "literature", "nature", "other")


def load_cards(vault: Path) -> list[dict]:
    cards = []
    if not vault.is_dir():
        return cards
    for p in sorted(vault.glob("*.json")):
        try:
            card = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"[illustration] 카드 파싱 실패(건너뜀): {p.name} — {e}", file=sys.stderr)
            continue
        card["_path"] = str(p)
        cards.append(card)
    return cards


def card_warnings(card: dict) -> list[str]:
    """카드 1장의 위생·안전 신호."""
    w = []
    for f in REQUIRED_FIELDS:
        if not card.get(f):
            w.append(f"필수 필드 누락: {f}")
    if card.get("kind") not in KINDS:
        w.append(f"알 수 없는 kind: {card.get('kind')!r} (유효: {', '.join(KINDS)})")
    if card.get("kind") == "congregation":
        if card.get("anonymized") is not True:
            w.append("회중 일화인데 anonymized!=true — **사용 차단 권고** (§8 익명성)")
        if card.get("consent") is not True:
            w.append("회중 일화인데 consent!=true — **사용 차단 권고** (§8 동의)")
    elif card.get("anonymized") is False:
        w.append("anonymized=false — 식별 가능 개인 포함 여부 확인")
    return w


def reuse_note(card: dict, recent: int = 5) -> str | None:
    used = card.get("used_in") or []
    if not used:
        return None
    last = used[-1]
    note = f"사용 {len(used)}회 · 최근 {last.get('date', '?')} ({last.get('run', '?')})"
    if len(used) >= 2:
        note += " — 반복 사용 신호"
    return note


def _print_card(card: dict, verbose: bool = False) -> None:
    warns = card_warnings(card)
    reuse = reuse_note(card)
    mark = "⛔" if any("차단" in w for w in warns) else ("⚠️" if warns else "·")
    print(f" {mark} [{card.get('id','?')}] {card.get('title','(제목 없음)')}"
          f"  kind={card.get('kind','?')} tags={','.join(card.get('tags') or [])}")
    if verbose:
        print(f"    source: {card.get('source','')}")
        body = str(card.get("body", ""))
        print(f"    body: {body[:120]}{'…' if len(body) > 120 else ''}")
    for w in warns:
        print(f"    ! {w}")
    if reuse:
        print(f"    ↻ {reuse}")


def cmd_list(args) -> int:
    cards = load_cards(args.vault)
    if not cards:
        print(f"[illustration] 금고가 비어 있습니다: {args.vault}")
        print("  → 예화 없이 쓰고, '예화 후보 찾기'를 설교자 worklist로 넘긴다(§7 — 지어내지 않는다).")
        return 0
    print(f"[illustration] 금고 {len(cards)}장 ({args.vault})")
    for c in cards:
        _print_card(c, verbose=args.verbose)
    return 0


def cmd_search(args) -> int:
    cards = load_cards(args.vault)
    if not cards:
        print(f"[illustration] 금고가 비어 있습니다: {args.vault} — 검색 결과 없음.")
        return 0
    qwords = set(_WORD_RE.findall(args.query or ""))
    results = []
    for c in cards:
        if args.kind and c.get("kind") != args.kind:
            continue
        if args.tag and args.tag not in (c.get("tags") or []):
            continue
        hay = " ".join([str(c.get("title", "")), str(c.get("body", "")),
                        " ".join(c.get("tags") or [])])
        # 조사 흡수를 위한 substring 매칭(끝 1글자 절단 폴백) — 의미 검색이 아닌 조잡한 매칭
        hits = 0
        for q in qwords:
            cands = {q} | ({q[:-1]} if len(q) >= 3 else set())
            if any(cand in hay for cand in cands):
                hits += 1
        if qwords and hits == 0:
            continue
        results.append((hits, c))
    results.sort(key=lambda x: -x[0])
    if not results:
        print(f"[illustration] 매치 없음 (query={args.query!r}, kind={args.kind}, tag={args.tag})")
        print("  → 지어내지 말 것. 예화 없이 쓰거나 설교자에게 카드 추가를 청한다.")
        return 0
    print(f"[illustration] {len(results)}건 매치 (내용어 겹침 순 — 의미 검색 아님)")
    for hits, c in results[: args.limit]:
        print(f"  ({hits}겹침)", end="")
        _print_card(c, verbose=True)
    return 0


def cmd_use(args) -> int:
    cards = load_cards(args.vault)
    target = next((c for c in cards if c.get("id") == args.id), None)
    if target is None:
        print(f"[illustration] 카드를 찾을 수 없습니다: {args.id}", file=sys.stderr)
        return 2
    warns = card_warnings(target)
    blocked = [w for w in warns if "차단" in w]
    if blocked and not args.force:
        for w in blocked:
            print(f"[illustration] ⛔ {w}", file=sys.stderr)
        print("[illustration] 사용 기록을 중단합니다. 카드의 동의·익명화를 먼저 해소하십시오"
              " (강행은 설교자 판단 하에 --force).", file=sys.stderr)
        return 1
    path = Path(target["_path"])
    card = json.loads(path.read_text(encoding="utf-8"))
    card.setdefault("used_in", []).append({
        "run": args.run,
        "date": datetime.date.today().isoformat(),
    })
    path.write_text(json.dumps(card, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[illustration] 사용 기록: {args.id} ← run {args.run}")
    note = reuse_note(card)
    if note:
        print(f"  ↻ {note}")
    print(f"  개요/원고 인용 표기: (예화금고: {args.id})")
    return 0


def cmd_check(args) -> int:
    cards = load_cards(args.vault)
    print(f"[illustration] 금고 위생 점검: {len(cards)}장 ({args.vault})")
    n_warn = n_block = 0
    ids = set()
    for c in cards:
        warns = card_warnings(c)
        cid = c.get("id")
        if cid in ids:
            warns.append(f"중복 id: {cid}")
        ids.add(cid)
        if warns:
            n_warn += 1
            n_block += any("차단" in w for w in warns)
            _print_card(c)
    print(f"  → 경고 {n_warn}장 (사용 차단 권고 {n_block}장) / 정상 {len(cards) - n_warn}장")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="예화 금고 인덱서 — 조회·기록만, 생성 없음")
    ap.add_argument("--vault", type=Path, default=DEFAULT_VAULT,
                    help=f"금고 경로 (기본 {DEFAULT_VAULT})")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="금고 전체 목록")
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("search", help="내용어 매칭 검색")
    p.add_argument("--query", default="", help="검색어 (내용어 겹침)")
    p.add_argument("--kind", choices=KINDS)
    p.add_argument("--tag")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("use", help="사용 기록(used_in) 추가")
    p.add_argument("--id", required=True)
    p.add_argument("--run", required=True)
    p.add_argument("--force", action="store_true",
                   help="차단 권고를 설교자 판단으로 강행(§10)")
    p.set_defaults(func=cmd_use)

    p = sub.add_parser("check", help="금고 위생 점검")
    p.set_defaults(func=cmd_check)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
