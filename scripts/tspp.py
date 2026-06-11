#!/usr/bin/env python3
"""TSPP single-command entry point.

This wrapper keeps the beginner-facing workflow stable while delegating the
actual work to the existing pipeline scripts.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

def _load_dotenv():
    """간이 .env 로더 — python-dotenv 미사용. 기존 환경변수는 덮어쓰지 않음."""
    p = ROOT / ".env"
    if not p.exists():
        return
    try:
        with p.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except OSError:
        pass

_load_dotenv()

SCRIPTS = ROOT / "scripts"
# 산출물 루트. 기본은 엔진 폴더(ROOT)지만, 호스트(Obsidian 플러그인 등)가
# TSPP_WORKSPACE 환경변수를 주입하면 output/input 루트가 그쪽으로 옮겨간다.
# 엔진 코드와 산출물(목회자 자산)을 분리하기 위한 surgical 훅. (DESIGN #6-1)
WORKSPACE = Path(os.environ.get("TSPP_WORKSPACE") or ROOT).resolve()
DEFAULT_ENGINES = "kci-api-searcher,nlk-ejournal-searcher,semantic-scholar,crossref-journal-searcher"


def run_dir(run: str) -> Path:
    return WORKSPACE / "output" / run


def input_dir(run: str) -> Path:
    # 사람이 주는 입력(묵상 씨앗·보이스)은 산출물과 분리해 input/<run>/ 아래 둔다.
    return WORKSPACE / "input" / run


def resource_dir(run: str) -> Path:
    return WORKSPACE / "input" / "resources" / run


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def call(args: list[str]) -> int:
    print("+ " + " ".join(args))
    proc = subprocess.run(args, cwd=str(ROOT))
    return proc.returncode


def cmd_init(args: argparse.Namespace) -> int:
    out = run_dir(args.run)
    inp = input_dir(args.run)
    res = resource_dir(args.run)
    out.mkdir(parents=True, exist_ok=True)
    inp.mkdir(parents=True, exist_ok=True)
    res.mkdir(parents=True, exist_ok=True)
    print(f"[tspp] run initialized: {args.run}")
    print(f"- output: {rel(out)}")
    print(f"- input: {rel(inp)}")
    print(f"- resources: {rel(res)}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    out = run_dir(args.run)
    inp = input_dir(args.run)
    res = resource_dir(args.run)
    paths = [
        ("run output", out),
        ("run input", inp),
        ("resource input", res),
        ("meditation seed", inp / "meditation_seed.json"),
        ("resolved voice", inp / "resolved_voice.json"),
        ("EvidencePack", out / "EvidencePack.json"),
        ("evidence list", out / "evidence_list.md"),
        ("resource manifest", out / "resource_manifest.json"),
        ("analysis packet", out / "resource_analysis_packet.md"),
        ("writing brief", out / "writing_brief.json"),
        ("scripture pack", out / "scripture_pack.json"),
        ("sermon outline", out / "sermon_outline.md"),
        ("scripture check (outline)", out / "scripture_check.json"),
        ("binding check", out / "binding_check.json"),
        ("full manuscript", out / "full_manuscript.md"),
        ("scripture check (manuscript)", out / "scripture_check_manuscript.json"),
        ("delivery pack", out / "delivery_pack.json"),
        ("homiletic audit (manuscript)", out / "homiletic_audit_manuscript.json"),
        ("review report", out / "sermon_review_report.md"),
        ("sermon retro", out / "sermon_retro.md"),
    ]
    print(f"[tspp] status: {args.run}")
    for label, path in paths:
        mark = "ok" if path.exists() else "missing"
        print(f"- {label}: {mark} ({rel(path)})")
    if res.exists():
        files = sorted(p for p in res.iterdir() if p.is_file())
        print(f"- resource files: {len(files)}")
        for p in files[:10]:
            print(f"  - {p.name}")
        if len(files) > 10:
            print(f"  - ... {len(files) - 10} more")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    out = run_dir(args.run)
    out.mkdir(parents=True, exist_ok=True)
    keywords_file = args.keywords_file or input_dir(args.run) / "meditation_seed.json"
    cmd = [
        sys.executable,
        str(SCRIPTS / "research_fanout.py"),
        args.query,
        "--engines",
        args.engines,
        "--per-keyword-limit",
        str(args.per_keyword_limit),
        "--out",
        rel(out / "EvidencePack.json"),
        "--report",
        rel(out / "research_fanout.md"),
    ]
    if keywords_file and Path(keywords_file).exists():
        cmd.extend(["--keywords-file", rel(Path(keywords_file))])
    if args.parallel:
        cmd.append("--parallel")
    if args.retries is not None:
        cmd.extend(["--retries", str(args.retries)])
    return call(cmd)


def cmd_list(args: argparse.Namespace) -> int:
    out = run_dir(args.run)
    evidence = args.evidence or out / "EvidencePack.json"
    target = args.out or out / "evidence_list.md"
    return call([
        sys.executable,
        str(SCRIPTS / "evidence_list.py"),
        "--evidence",
        str(evidence),
        "--out",
        str(target),
    ])


def cmd_ingest(args: argparse.Namespace) -> int:
    # resource_ingest.py는 run만 받으면 엔진 폴더 기준 output/input을 자체 계산한다.
    # 워크스페이스가 엔진 밖으로 옮겨졌을 수 있으므로 경로를 명시 전달한다.
    # (--manifest의 부모에서 resource_analysis_packet.md 위치가 파생됨)
    out = run_dir(args.run)
    res = resource_dir(args.run)
    cmd = [
        sys.executable,
        str(SCRIPTS / "resource_ingest.py"),
        args.run,
        "--pack",
        str(out / "EvidencePack.json"),
        "--resources",
        str(res),
        "--out",
        str(out / "resources"),
        "--manifest",
        str(out / "resource_manifest.json"),
    ]
    if args.backend:
        cmd.extend(["--backend", args.backend])
    return call(cmd)


def cmd_preflight(args: argparse.Namespace) -> int:
    out = run_dir(args.run)
    cmd = [
        sys.executable,
        str(SCRIPTS / "outline_preflight.py"),
        "--meditation-seed",
        str(args.meditation_seed),
        "--resolved-voice",
        str(args.resolved_voice),
        "--out",
        str(args.out or out / "writing_brief.json"),
    ]
    evidence = args.evidence or out / "EvidencePack.json"
    if evidence.exists():
        cmd.extend(["--evidence", str(evidence)])
    return call(cmd)


def cmd_fetch(args: argparse.Namespace) -> int:
    # OA PDF 자동 입수(S2 직링크 + Crossref/Unpaywall) → input/resources/<run>/.
    out = run_dir(args.run)
    res = resource_dir(args.run)
    res.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(SCRIPTS / "oa_fetch.py"),
        "--pack", str(out / "EvidencePack.json"),
        "--out", str(res),
        "--per-engine-limit", str(args.per_engine_limit),
    ]
    email = os.environ.get("CROSSREF_MAILTO", "").strip()
    if email:
        cmd.extend(["--email", email])
    return call(cmd)


def cmd_audit(args: argparse.Namespace) -> int:
    # 작성된 개요를 호밀레틱 계기판(비점수 worklist)으로 점검.
    out = run_dir(args.run)
    cmd = [
        sys.executable,
        str(SCRIPTS / "homiletic_audit.py"),
        "--draft", str(out / "sermon_outline.md"),
        "--out", str(out / "homiletic_audit.json"),
    ]
    rv = input_dir(args.run) / "resolved_voice.json"
    if rv.exists():
        cmd.extend(["--resolved", str(rv)])
    ledger = WORKSPACE / "output" / "sermon_ledger.json"
    if ledger.exists():
        cmd.extend(["--ledger", str(ledger), "--run", args.run])
    return call(cmd)


def cmd_voice(args: argparse.Namespace) -> int:
    # 보이스 3층 합성 → input/<run>/resolved_voice.json (preflight의 필수 입력).
    out = input_dir(args.run) / "resolved_voice.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(SCRIPTS / "voice_resolve.py"),
        "--genre", args.genre,
        "--tier", args.tier,
        "--out", str(out),
    ]
    if args.season:
        cmd.extend(["--season", args.season])
    if args.preacher_voice:
        cmd.extend(["--preacher-voice", str(args.preacher_voice)])
    if args.audience:
        cmd.extend(["--audience", str(args.audience)])
    return call(cmd)


def cmd_manuscript(args: argparse.Namespace) -> int:
    out = run_dir(args.run)
    outline_path = out / "sermon_outline.md"
    if not outline_path.is_file():
        print(f"[tspp] 설교 개요 파일이 없습니다: {rel(outline_path)}", file=sys.stderr)
        return 1

    # 간이 YAML frontmatter 파서
    approved = False
    try:
        with outline_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        in_frontmatter = False
        for line in lines:
            line_strip = line.strip()
            if line_strip == "---":
                if in_frontmatter:
                    break
                else:
                    in_frontmatter = True
                    continue
            if in_frontmatter:
                if ":" in line_strip:
                    k, v = line_strip.split(":", 1)
                    if k.strip() == "approved":
                        val = v.strip().lower()
                        if val in ("true", "yes", "1"):
                            approved = True
    except OSError as e:
        print(f"[tspp] 개요 파일을 읽는 중 오류 발생: {e}", file=sys.stderr)
        return 1

    if not approved:
        print(f"[tspp] 설교 개요가 승인(approved: true)되지 않았습니다: {rel(outline_path)}", file=sys.stderr)
        return 1

    print("[tspp] 설교 개요 승인 확인 완료.")

    manuscript_path = out / "full_manuscript.md"
    if manuscript_path.is_file() and not args.overwrite:
        print(f"[tspp] 이미 원고 파일이 존재합니다: {rel(manuscript_path)}")
        print("[tspp] 원고를 다시 초기화하려면 --overwrite 옵션을 사용하십시오.")
        return 0

    # sermon_outline.md의 H2 제목들을 추출하여 뼈대 생성
    h2_titles = []
    for line in lines:
        if line.startswith("## "):
            h2_titles.append(line.strip())

    content = [
        "---",
        "schema: tspp.full_manuscript/1",
        f"run: {args.run}",
        "approved: false",
        "---",
        "",
        "# 설교 원고 (구어체)",
        "",
        "> **머리말** · 구어체 설교 원고.",
        ""
    ]
    for h2 in h2_titles:
        content.append(h2)
        content.append("")
        content.append("*(여기에 구어체 설교 내용을 확장하여 작성하십시오)*")
        content.append("")

    try:
        manuscript_path.write_text("\n".join(content), encoding="utf-8")
        print(f"[tspp] 설교 원고 스켈레톤이 생성되었습니다: {rel(manuscript_path)}")
    except OSError as e:
        print(f"[tspp] 원고 파일 생성 중 오류 발생: {e}", file=sys.stderr)
        return 1

    return 0


def cmd_delivery(args: argparse.Namespace) -> int:
    out = run_dir(args.run)
    manuscript = out / "full_manuscript.md"
    if not manuscript.is_file():
        print(f"[tspp] 설교 원고 파일이 없습니다: {rel(manuscript)}", file=sys.stderr)
        return 1

    cmd_pack = [
        sys.executable,
        str(SCRIPTS / "delivery_pack.py"),
        "--manuscript", str(manuscript),
        "--out", str(out / "delivery_pack.json"),
    ]
    if args.target_min is not None:
        cmd_pack.extend(["--target-min", str(args.target_min)])
    if args.chars_per_min is not None:
        cmd_pack.extend(["--chars-per-min", str(args.chars_per_min)])

    print("[tspp] 전달 분석(delivery_pack.py) 실행 중...")
    rc = call(cmd_pack)
    if rc != 0:
        return rc

    cmd_audit = [
        sys.executable,
        str(SCRIPTS / "homiletic_audit.py"),
        "--draft", str(manuscript),
        "--out", str(out / "homiletic_audit_manuscript.json"),
    ]
    rv = input_dir(args.run) / "resolved_voice.json"
    if rv.exists():
        cmd_audit.extend(["--resolved", str(rv)])
    pv = input_dir(args.run) / "preacher_voice.json"
    if pv.exists():
        cmd_audit.extend(["--preacher-voice", str(pv)])
    ledger = WORKSPACE / "output" / "sermon_ledger.json"
    if ledger.exists():
        cmd_audit.extend(["--ledger", str(ledger), "--run", args.run])

    print("[tspp] 호밀레틱 감사(homiletic_audit.py) 실행 중...")
    return call(cmd_audit)


def cmd_review(args: argparse.Namespace) -> int:
    import json
    import time
    out = run_dir(args.run)
    brief_path = out / "writing_brief.json"
    outline_path = out / "sermon_outline.md"
    
    if not brief_path.is_file():
        print(f"[tspp] writing_brief.json 파일이 없습니다. preflight를 먼저 실행하십시오.", file=sys.stderr)
        return 1
    if not outline_path.is_file():
        print(f"[tspp] sermon_outline.md 파일이 없습니다. 개요를 먼저 작성하십시오.", file=sys.stderr)
        return 1

    # brief 정보 읽기
    try:
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
        passage = brief.get("passage", "미지정 본문")
        theme = brief.get("theme", "미지정 주제")
    except Exception as e:
        print(f"[tspp] writing_brief.json을 읽는 중 오류 발생: {e}", file=sys.stderr)
        passage, theme = "미지정 본문", "미지정 주제"

    report_path = out / "sermon_review_report.md"
    if report_path.is_file() and not args.overwrite:
        print(f"[tspp] 이미 리뷰 보고서 파일이 존재합니다: {rel(report_path)}")
        print("[tspp] 보고서를 다시 초기화하려면 --overwrite 옵션을 사용하십시오.")
        return 0

    # 템플릿 복사 및 치환
    tpl_path = ROOT / "skills" / "sermon-reviewer" / "templates" / "review_report.example.md"
    if not tpl_path.is_file():
        print(f"[tspp] 리뷰 템플릿 파일이 없습니다: {rel(tpl_path)}", file=sys.stderr)
        return 1

    try:
        tpl_content = tpl_path.read_text(encoding="utf-8")
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        content = tpl_content
        content = content.replace("${RUN_ID}", args.run)
        content = content.replace("${PASSAGE}", passage)
        content = content.replace("${THEME}", theme)
        content = content.replace("${TIMESTAMP}", timestamp)

        report_path.write_text(content, encoding="utf-8")
        print(f"[tspp] 설교 품질 검수 보고서 스켈레톤이 생성되었습니다: {rel(report_path)}")
        print("[tspp] 이제 에이전트(sermon-reviewer)를 구동하여 검수 보고서(산문)를 완성하십시오.")
    except OSError as e:
        print(f"[tspp] 보고서 파일 생성 중 오류 발생: {e}", file=sys.stderr)
        return 1

    return 0


RETRO_TEMPLATE = """---
schema: tspp.sermon_retro/1
run: {run}
preached_on:            # 설교일 YYYY-MM-DD (설교자 기입)
actual_minutes:         # 실제 전달 시간(분) — 기입하면 chars-per-min 보정 제안
---

# 설교 후 회고 — {run}

> ⚠️ **이 문서는 설교자가 기록한다. AI가 회고를 대필하지 않는다(§2).**
> 아래 항목은 비워 두어도 된다 — 기록된 것만 장부(ledger)와 다음 준비에 반영된다.

## 가닿은 것

*(어느 단락·어느 문장이 실제로 가닿았는가)*

## 걸린 것

*(전달 중 호흡이 걸리거나, 반응이 멀었거나, 스스로 멈칫한 지점)*

## 스스로 평가

*(본문 충실·보이스·긴장 보존 — 준비 단계의 의도가 강단에서 살았는가)*

## 보이스 메모

*(내 목소리답지 않았던 표현, 다음에 살리고 싶은 어법)*

## 다음에

*(이 본문/주제를 다시 다룬다면, 또는 다음 설교 준비에 넘길 것)*
"""


def cmd_retro(args: argparse.Namespace) -> int:
    # 설교 후 회고 루프(P2-7): 뼈대 생성(1회차) / 요약·보정 제안·장부 반영(2회차).
    import json
    out = run_dir(args.run)
    if not out.is_dir():
        print(f"[tspp] run 폴더가 없습니다: {rel(out)}", file=sys.stderr)
        return 1
    retro_path = out / "sermon_retro.md"

    if not retro_path.is_file() or args.overwrite:
        retro_path.write_text(RETRO_TEMPLATE.format(run=args.run), encoding="utf-8")
        print(f"[tspp] 회고 뼈대가 생성되었습니다: {rel(retro_path)}")
        print("[tspp] 내용은 설교자가 기록합니다 — 기록 후 같은 명령을 다시 실행하면 장부에 반영됩니다.")
        return 0

    # 2회차: frontmatter 읽기 → 보정 제안 → 장부 반영 → 보이스 갱신 신호
    fm = {}
    text = retro_path.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        for line in text[3:end].splitlines():
            if ":" in line and not line.strip().startswith("#"):
                k, v = line.split(":", 1)
                fm[k.strip()] = v.split("#", 1)[0].strip().strip('"')

    print(f"[tspp] 회고 요약: {args.run}")
    actual = fm.get("actual_minutes", "")
    try:
        actual_f = float(actual)
    except ValueError:
        actual_f = None
    if actual_f:
        dp = out / "delivery_pack.json"
        if dp.is_file():
            try:
                t = json.loads(dp.read_text(encoding="utf-8")).get("time", {})
                est = t.get("estimated_minutes")
                chars = t.get("chars_no_whitespace")
                if est:
                    print(f"- 전달 시간: 실측 {actual_f}분 / 추정 {est}분")
                if chars:
                    suggested = round(chars / actual_f)
                    print(f"- 다음 run의 속도 보정 제안: --chars-per-min {suggested}"
                          f" (현재 기본 {t.get('chars_per_min', 320)})")
            except (OSError, json.JSONDecodeError):
                pass
    else:
        print("- actual_minutes 미기입 — 기입하면 전달 속도 보정을 제안합니다.")

    # 장부 반영 (retro frontmatter는 ledger_update가 직접 읽는다)
    rc = call([sys.executable, str(SCRIPTS / "ledger_update.py"),
               "--run", args.run, "--workspace", str(WORKSPACE)])
    if rc != 0:
        return rc

    # 보이스 갱신 신호: 승인된 원고가 충분히 쌓였으면 voice_ingest 재실행 제안
    ledger_path = WORKSPACE / "output" / "sermon_ledger.json"
    try:
        entries = json.loads(ledger_path.read_text(encoding="utf-8")).get("entries", [])
        approved = [e for e in entries if e.get("outline_approved")]
        if len(approved) >= 5:
            print(f"[tspp] 신호: 승인된 설교가 {len(approved)}편 — 최근 원고를 "
                  "input/sermon_samples/에 모아 voice_ingest 재실행으로 preacher_voice "
                  "갱신을 고려하십시오(보이스는 살아 있는 지문, §5).")
    except (OSError, json.JSONDecodeError):
        pass
    return 0


def cmd_scripture(args: argparse.Namespace) -> int:
    # 성경 인용 정합 게이트(P0-1): pericope 팩 생성 + 개요/원고 인용 대조.
    out = run_dir(args.run)
    out.mkdir(parents=True, exist_ok=True)
    seed = input_dir(args.run) / "meditation_seed.json"
    pack = out / "scripture_pack.json"

    cmd = [sys.executable, str(SCRIPTS / "scripture_pack.py"), "--out", str(pack)]
    if args.passage:
        cmd.extend(["--passage", args.passage])
    elif seed.is_file():
        cmd.extend(["--seed", str(seed)])
    else:
        print("[tspp] meditation_seed.json이 없습니다 — --passage로 본문을 직접 지정하십시오.",
              file=sys.stderr)
        return 1
    translation = args.translation or os.environ.get("TSPP_TRANSLATION", "").strip()
    if translation:
        cmd.extend(["--translation", translation])
    if args.context is not None:
        cmd.extend(["--context", str(args.context)])
    rc = call(cmd)
    if rc != 0:
        return rc

    # 존재하는 draft를 모두 대조 (개요 → 원고 순)
    targets = [
        (out / "sermon_outline.md", out / "scripture_check.json"),
        (out / "full_manuscript.md", out / "scripture_check_manuscript.json"),
    ]
    worst = 0
    checked = 0
    for draft, check_out in targets:
        if not draft.is_file():
            continue
        checked += 1
        check_cmd = [
            sys.executable, str(SCRIPTS / "scripture_check.py"),
            "--draft", str(draft), "--pack", str(pack), "--out", str(check_out),
        ]
        if translation:
            check_cmd.extend(["--translation", translation])
        rc = call(check_cmd)
        worst = max(worst, rc)
    if checked == 0:
        print("[tspp] 대조할 draft(sermon_outline.md / full_manuscript.md)가 아직 없습니다 — 팩만 생성했습니다.")
    return worst


def cmd_binding(args: argparse.Namespace) -> int:
    # 본문 정합 구조 게이트(P0-2, 헌법 §3): 앵커 존재·범위·교차참조 선언 검증.
    out = run_dir(args.run)
    draft = args.draft or out / "sermon_outline.md"
    seed = input_dir(args.run) / "meditation_seed.json"
    if not Path(draft).is_file():
        print(f"[tspp] 개요 파일이 없습니다: {rel(Path(draft))}", file=sys.stderr)
        return 1
    if not seed.is_file():
        print(f"[tspp] meditation_seed.json이 없습니다: {rel(seed)}", file=sys.stderr)
        return 1
    cmd = [
        sys.executable, str(SCRIPTS / "binding_check.py"),
        "--draft", str(draft), "--seed", str(seed),
        "--out", str(out / "binding_check.json"),
    ]
    translation = getattr(args, "translation", None) or os.environ.get("TSPP_TRANSLATION", "").strip()
    if translation:
        cmd.extend(["--translation", translation])
    brief = out / "writing_brief.json"
    if brief.is_file():
        cmd.extend(["--brief", str(brief)])
    return call(cmd)


def cmd_report(args: argparse.Namespace) -> int:
    # 종합 현황판(P2-8): 기존 산출물 요약 수합만 — 신규 판단 없음(읽기 전용).
    import json

    def load(p: Path) -> dict:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    out = run_dir(args.run)
    if not out.is_dir():
        print(f"[tspp] run 폴더가 없습니다: {rel(out)}", file=sys.stderr)
        return 1
    print(f"[tspp] ═══ 종합 현황 — {args.run} ═══ (수합만 — 판단은 설교자)")

    # ① HITL 게이트 (writing_brief)
    brief = load(out / "writing_brief.json")
    if brief:
        g = brief.get("gates", {})
        print(f"  HITL 게이트: ready={g.get('ready')} "
              f"(seed={g.get('meditation_seed_approved')} voice={g.get('resolved_voice_approved')})")
        print(f"  본문: {brief.get('passage')} · 주제: {str(brief.get('theme'))[:40]}")
    else:
        print("  HITL 게이트: writing_brief 없음 (preflight 미실행)")

    # ② 본문 정합·인용 게이트
    b = load(out / "binding_check.json")
    print(f"  binding: {b.get('verdict', '미실행')}"
          + (f" — hard {len(b.get('hard', []))} · worklist {len(b.get('worklist', []))}" if b else ""))
    for name, f in (("scripture(개요)", "scripture_check.json"),
                    ("scripture(원고)", "scripture_check_manuscript.json")):
        s = load(out / f)
        if s:
            c = s.get("counts", {})
            print(f"  {name}: {s.get('verdict')} — hard {c.get('hard', 0)} · "
                  f"불일치 {c.get('worklist', 0)} · 인용 {c.get('quotes', 0)}건")

    # ③ 계기판
    for name, f in (("계기판(개요)", "homiletic_audit.json"),
                    ("계기판(원고)", "homiletic_audit_manuscript.json")):
        a = load(out / f)
        if a:
            kinds = [w.get("corruption", "").split(" (")[0] for w in a.get("worklist", [])]
            print(f"  {name}: {a.get('summary', '')}"
                  + (f" [{', '.join(kinds)}]" if kinds else ""))
            for t in a.get("trend", []):
                print(f"    ↗ {t.get('note')} — {t.get('corruption')}")

    # ④ 전달·흐름
    d = load(out / "delivery_pack.json")
    if d:
        t = d.get("time", {})
        print(f"  전달: 추정 {t.get('estimated_minutes')}분 "
              f"(목표 {t.get('target_minutes') or '미지정'})")
    sc = load(out / "series_check.json")
    if sc:
        print(f"  흐름(series): 신호 {len(sc.get('signals', []))}건"
              + ("".join(f"\n    · [{s['kind']}] {s['detail'][:60]}" for s in sc.get("signals", [])[:4])))

    # ⑤ 검수·회고
    review = out / "sermon_review_report.md"
    print(f"  정성 검수: {'있음' if review.is_file() else '없음'} ({rel(review)})")
    retro = out / "sermon_retro.md"
    print(f"  회고: {'있음' if retro.is_file() else '없음'}")

    # ⑥ 장부
    ledger = load(WORKSPACE / "output" / "sermon_ledger.json")
    entries = ledger.get("entries", [])
    if entries:
        mine = next((e for e in entries if e.get("run") == args.run), None)
        print(f"  장부: 총 {len(entries)}편 적립"
              + (" · 이 run 적립됨" if mine else " · 이 run 미적립 (ledger_update 실행)"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TSPP workflow helper")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="Create output and input resource folders for a run")
    p.add_argument("run")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("status", help="Show current run artifacts")
    p.add_argument("run")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("search", help="Run academic fan-out discovery")
    p.add_argument("run")
    p.add_argument("--query", required=True, help="Passage or topic query")
    p.add_argument("--keywords-file", type=Path, help="Optional meditation_seed.json or keyword JSON")
    p.add_argument("--engines", default=DEFAULT_ENGINES)
    p.add_argument("--per-keyword-limit", type=int, default=3)
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--parallel", action="store_true")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("list", help="Create evidence_list.md from EvidencePack.json")
    p.add_argument("run")
    p.add_argument("--evidence", type=Path)
    p.add_argument("--out", type=Path)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("ingest", help="Extract selected resources into citation-safe text")
    p.add_argument("run")
    p.add_argument("--backend", choices=["opendataloader", "pymupdf", "pdfplumber", "pypdf", "pdftotext"])
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("fetch", help="Download OA PDFs (S2 + Crossref/Unpaywall) into resources")
    p.add_argument("run")
    p.add_argument("--per-engine-limit", type=int, default=3)
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("audit", help="Homiletic voice worklist on sermon_outline.md (non-score)")
    p.add_argument("run")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("voice", help="Resolve preaching voice → resolved_voice.json")
    p.add_argument("run")
    p.add_argument("--genre", required=True, help="본문장르 키 (예: gospel_parable)")
    p.add_argument("--tier", required=True, help="설교 유형 키 (예: pastoral)")
    p.add_argument("--season", help="절기 키 (예: ordinary)")
    p.add_argument("--preacher-voice", type=Path, help="preacher_voice.json (L1-개인, opt-in)")
    p.add_argument("--audience", type=Path, help="audience_profile.json (목회자 작성)")
    p.set_defaults(func=cmd_voice)

    p = sub.add_parser("preflight", help="Build writing_brief.json after HITL approvals")
    p.add_argument("run")
    p.add_argument("--meditation-seed", type=Path, required=True)
    p.add_argument("--resolved-voice", type=Path, required=True)
    p.add_argument("--evidence", type=Path)
    p.add_argument("--out", type=Path)
    p.set_defaults(func=cmd_preflight)

    p = sub.add_parser("manuscript", help="Validate outline approval and initialize manuscript skeleton")
    p.add_argument("run")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing manuscript")
    p.set_defaults(func=cmd_manuscript)

    p = sub.add_parser("delivery", help="Run delivery analysis and homiletic audit on the manuscript")
    p.add_argument("run")
    p.add_argument("--target-min", type=float, help="Target sermon length in minutes")
    p.add_argument("--chars-per-min", type=float, help="Estimated speaking rate (characters per minute)")
    p.set_defaults(func=cmd_delivery)

    p = sub.add_parser("review", help="Initialize qualitative review report skeleton")
    p.add_argument("run")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing review report")
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("retro", help="Post-sermon retrospective skeleton + ledger update (P2-7)")
    p.add_argument("run")
    p.add_argument("--overwrite", action="store_true", help="회고 뼈대를 다시 생성")
    p.set_defaults(func=cmd_retro)

    p = sub.add_parser("scripture", help="Build pericope pack and verify scripture quotations (P0-1)")
    p.add_argument("run")
    p.add_argument("--passage", help='본문 직접 지정 (예: "마태복음 21:33-46")')
    p.add_argument("--translation",
                   help="번역본 키 (기본: $TSPP_TRANSLATION 또는 KorRV — 사용자 보유본은 input/scripture/)")
    p.add_argument("--context", type=int, help="전후 문맥 절 수 (기본 8)")
    p.set_defaults(func=cmd_scripture)

    p = sub.add_parser("binding", help="Structural text-binding gate on the outline (P0-2, §3)")
    p.add_argument("run")
    p.add_argument("--draft", type=Path, help="기본: output/<run>/sermon_outline.md")
    p.add_argument("--translation", help="번역본 키 (기본: $TSPP_TRANSLATION 또는 KorRV)")
    p.set_defaults(func=cmd_binding)

    p = sub.add_parser("report", help="Read-only aggregated dashboard for a run (P2-8)")
    p.add_argument("run")
    p.set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

