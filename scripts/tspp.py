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
        ("sermon outline", out / "sermon_outline.md"),
        ("full manuscript", out / "full_manuscript.md"),
        ("delivery pack", out / "delivery_pack.json"),
        ("homiletic audit (manuscript)", out / "homiletic_audit_manuscript.json"),
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

    print("[tspp] 호밀레틱 감사(homiletic_audit.py) 실행 중...")
    return call(cmd_audit)


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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

