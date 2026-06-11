#!/usr/bin/env python3
"""binding_check.py — 본문 정합(binding) 구조 게이트 (헌법 §3 hard gate 실체화, P0-2).

"적용이 본문을 왜곡하면 멈춘다"(§3)에서 기계가 보증할 수 있는 *구조* 부분을
검증한다 — 해석의 적절성은 기계가 판단할 수 없지만(판단은 설교자 §10),
*정착의 구조*(앵커 존재·범위)는 보증할 수 있다.

검증 (hard = BLOCKED):
1. 모든 논점·적용 섹션에 본문 앵커(`**본문 뿌리**: <장절>`)가 있는가.
2. 앵커가 pericope 안인가 — 밖이면 frontmatter `cross_refs`에 선언됐는가.
   (같은 장 안의 주변 문맥은 hard가 아니라 worklist — "pericope 확장 고려")
3. seed의 `eisegesis_risk: high` 메시지 후보가 개요 주제와 겹치면
   frontmatter `eisegesis_resolution`(재정착 기록)이 있는가.

개요 frontmatter 규격(선택 키):
    cross_refs: "막 12:1-12; 사 5:1-7"      # pericope 밖 의도적 교차 참조 선언
    eisegesis_resolution: "..."              # high 후보를 본문에 재정착한 기록

- 순수 stdlib. 측정·게이트만, 산문 없음(§11).
- sermon-outline 스킬 Phase 3(Foundation Gate)의 자율 점검을 이 스크립트가 대체.

사용:
    python scripts/binding_check.py --draft output/<run>/sermon_outline.md \
        --seed input/<run>/meditation_seed.json \
        [--brief output/<run>/writing_brief.json] \
        --out output/<run>/binding_check.json
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

# 앵커 의무 섹션(제목 키워드) — 본문에 뿌리내려야 하는 주장 단위
ANCHOR_REQUIRED = ("논점", "적용")
# 앵커 권장(없어도 hard 아님) — 본문 언급이 자연스러운 섹션
ANCHOR_OPTIONAL = ("도입", "긴장", "결단", "부름", "기도", "예화")

ANCHOR_LINE_RE = re.compile(r"\*{0,2}본문\s*뿌리\*{0,2}\s*[:：]\s*(?P<spec>[^\n]+)")
_WORD_RE = re.compile(r"[가-힣]{2,}")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """간이 flat YAML frontmatter 파서 (cmd_manuscript와 동일 수준)."""
    fm: dict[str, str] = {}
    if not text.startswith("---"):
        return fm, text
    end = text.find("\n---", 3)
    if end == -1:
        return fm, text
    for line in text[3:end].splitlines():
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, text[end + 4:]


def split_sections(body: str) -> list[dict]:
    """'## ' 단위 섹션 분해 → [{'title','text','line'}]."""
    sections = []
    cur = None
    for i, line in enumerate(body.splitlines(), start=1):
        if line.startswith("## "):
            if cur:
                sections.append(cur)
            cur = {"title": line[3:].strip(), "text": "", "line": i}
        elif cur:
            cur["text"] += line + "\n"
    if cur:
        sections.append(cur)
    return sections


def keyword_overlap(a: str, b: str) -> float:
    """조잡한 내용어 겹침 비율(0~1) — 의미 유사도가 아니다(정직한 한계)."""
    wa, wb = set(_WORD_RE.findall(a)), set(_WORD_RE.findall(b))
    if not wa:
        return 0.0
    return len(wa & wb) / len(wa)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="본문 정합(binding) 구조 게이트")
    ap.add_argument("--draft", type=Path, required=True, help="sermon_outline.md")
    ap.add_argument("--seed", type=Path, required=True, help="meditation_seed.json")
    ap.add_argument("--brief", type=Path, help="writing_brief.json (선택 — 메시지 후보 보강)")
    ap.add_argument("--translation", default=sl.DEFAULT_TRANSLATION,
                    help="번역본 코드 (기본 KorRV — input/scripture의 사용자 보유본이 우선)")
    ap.add_argument("--data", type=Path, default=None,
                    help="본문 데이터 루트 (기본: input/scripture → data/scripture 순 탐색)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    for p, name in ((args.draft, "draft"), (args.seed, "seed")):
        if not p.is_file():
            print(f"[binding_check] {name} 파일이 없습니다: {p}", file=sys.stderr)
            return 2
    try:
        tr = sl.load_translation(args.data, args.translation)
    except FileNotFoundError as e:
        print(f"[binding_check] 본문 데이터 로드 실패: {e}", file=sys.stderr)
        return 2

    seed = json.loads(args.seed.read_text(encoding="utf-8"))
    peri = sl.parse_passage(str(seed.get("passage", "")), tr)
    if peri is None or peri.book_n is None:
        print(f"[binding_check] seed.passage 해석 불가: '{seed.get('passage')}'", file=sys.stderr)
        return 2

    raw = args.draft.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(raw)

    # cross_refs 선언 파싱 → (book_n, chapter) 집합
    declared: set[tuple[int, int]] = set()
    declared_labels: list[str] = []
    for part in re.split(r"[;,，；]", fm.get("cross_refs", "")):
        part = part.strip()
        if not part:
            continue
        r = sl.parse_passage(part, tr)
        if r and r.book_n:
            declared.add((r.book_n, r.chapter))
            declared_labels.append(r.label())

    hard: list[dict] = []
    worklist: list[dict] = []
    section_rows: list[dict] = []

    # ── 1·2. 섹션별 앵커 존재·범위 ─────────────────────────────────────────
    for sec in split_sections(body):
        title = sec["title"]
        required = any(k in title for k in ANCHOR_REQUIRED)
        relevant = required or any(k in title for k in ANCHOR_OPTIONAL)
        if not relevant:
            continue
        m = ANCHOR_LINE_RE.search(sec["text"])
        anchors: list[sl.Ref] = []
        if m:
            anchors = sl.parse_refs(m.group("spec"), tr, default_book=peri.book_n)
        elif required:
            # 본문 뿌리 라인이 없으면 섹션 내 장절 표기를 차선 앵커로 수집
            anchors = sl.parse_refs(sec["text"], tr, default_book=peri.book_n)

        row = {"title": title, "required": required,
               "anchor_line": bool(m),
               "anchors": [a.label() for a in anchors], "zones": []}

        if required and not anchors:
            hard.append({"kind": "missing_anchor", "section": title,
                         "detail": "논점/적용 섹션에 본문 앵커가 없음 — `**본문 뿌리**: <장절>` 추가 필요"})
        for a in anchors:
            problems = sl.validate_ref(a, tr)
            if problems:
                hard.append({"kind": "invalid_anchor", "section": title,
                             "ref": a.label(), "detail": "; ".join(problems)})
                row["zones"].append("invalid")
                continue
            if a.book_n == peri.book_n and a.chapter == peri.chapter:
                in_peri = a.ranges and all(
                    any(pa <= x and y <= pb for pa, pb in peri.ranges)
                    for x, y in a.ranges)
                zone = "pericope" if in_peri else "chapter"
                if zone == "chapter" and required:
                    worklist.append({
                        "kind": "context_anchor", "section": title, "ref": a.label(),
                        "detail": (f"앵커가 선언된 pericope({peri.label()}) 밖, 같은 장 주변 문맥 — "
                                   "seed의 passage 범위 확장을 고려 (판단은 설교자)")})
            else:
                zone = "declared_cross_ref" if (a.book_n, a.chapter) in declared else "elsewhere"
                if zone == "elsewhere" and required:
                    hard.append({
                        "kind": "undeclared_cross_ref", "section": title, "ref": a.label(),
                        "detail": ("pericope 밖 본문을 앵커로 사용 — 의도적 교차 참조라면 "
                                   f"frontmatter `cross_refs`에 선언 (현재 선언: {declared_labels or '없음'})")})
            row["zones"].append(zone)
        section_rows.append(row)

    required_secs = [s for s in section_rows if s["required"]]
    if not required_secs:
        hard.append({"kind": "no_sections", "section": None,
                     "detail": "논점/적용 섹션을 찾지 못함 — 개요 구조(## 논점 N / ## 적용) 확인"})

    # ── 3. eisegesis high 후보 재정착 기록 ─────────────────────────────────
    candidates = list(seed.get("message_candidates", []))
    if args.brief and args.brief.is_file():
        brief = json.loads(args.brief.read_text(encoding="utf-8"))
        for mc in (brief.get("message", {}) or {}).get("candidates", []) or []:
            if isinstance(mc, dict) and mc not in candidates:
                candidates.append(mc)
    theme = " ".join([fm.get("theme", ""), str(seed.get("theme", "")),
                      body.split("\n", 1)[0]])
    eis_rows = []
    for mc in candidates:
        risk = str(mc.get("eisegesis_risk", "")).lower()
        if risk != "high":
            continue
        ov = keyword_overlap(str(mc.get("statement", "")), theme + " " + body[:2000])
        used_likely = ov >= 0.3
        eis_rows.append({"statement": mc.get("statement", ""), "overlap": round(ov, 2),
                         "used_likely": used_likely})
        if used_likely and not fm.get("eisegesis_resolution"):
            hard.append({
                "kind": "eisegesis_high_unresolved",
                "detail": (f"eisegesis_risk=high 후보가 개요에 사용된 정황(겹침 {ov:.0%}) — "
                           "본문 재정착 후 frontmatter `eisegesis_resolution`에 기록하거나 후보 제외(§3)")})
        elif not used_likely:
            worklist.append({
                "kind": "eisegesis_high_present",
                "detail": (f"seed에 eisegesis_risk=high 후보 존재(개요 사용 정황 낮음, 겹침 {ov:.0%}) — "
                           "사용했다면 재정착 기록 필요")})

    verdict = "blocked" if hard else "ok"
    result = {
        "schema_version": 1,
        "_note": ("본문 정합 구조 게이트(P0-2, 헌법 §3). hard=앵커 누락·범위 밖·미선언 교차참조·"
                  "high 후보 미재정착(구조 사실). worklist=주변 문맥 앵커 등(판단은 설교자 §10). "
                  "해석의 *적절성*은 이 게이트가 보증하지 않는다 — 그것은 설교자와 reviewer의 몫."),
        "draft": str(args.draft),
        "pericope": peri.label(),
        "cross_refs_declared": declared_labels,
        "verdict": verdict,
        "counts": {"sections_checked": len(section_rows),
                   "required_sections": len(required_secs),
                   "hard": len(hard), "worklist": len(worklist)},
        "hard": hard,
        "worklist": worklist,
        "sections": section_rows,
        "eisegesis_high": eis_rows,
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
                        .strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[binding_check] {args.draft.name} · pericope {peri.label()}"
          + (f" · cross_refs {declared_labels}" if declared_labels else ""))
    for s in section_rows:
        mark = "필수" if s["required"] else "권장"
        print(f"  [{mark}] {s['title'][:30]} → {s['anchors'] or '앵커 없음'} {s['zones']}")
    for h in hard:
        print(f"  [HARD] {h['kind']}: {h['detail']}")
    for w in worklist:
        print(f"  [worklist] {w['kind']}: {w['detail'][:70]}")
    print(f"  verdict: {verdict} → {args.out}")
    return 0 if verdict == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
