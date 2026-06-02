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
SCRIPTS = ROOT / "scripts"
WORKSPACE = Path(os.environ.get("TSPP_WORKSPACE") or ROOT).resolve()
DEFAULT_ENGINES = "kci-api-searcher,nlk-ejournal-searcher,semantic-scholar,crossref-journal-searcher"


def run_dir(run: str) -> Path:
    return WORKSPACE / "output" / run


def input_dir(run: str) -> Path:
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
        ("selected evidence", out / "selected_evidence.json"),
        ("resource manifest", out / "resource_manifest.json"),
        ("analysis packet", out / "resource_analysis_packet.md"),
        ("writing brief", out / "writing_brief.json"),
        ("outline draft", out / "sermon_outline_draft.md"),
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
    cmd = [
        sys.executable,
        str(SCRIPTS / "evidence_list.py"),
        "--evidence",
        str(evidence),
        "--out",
        str(target),
    ]
    keywords_file = args.keywords_file or input_dir(args.run) / "meditation_seed.json"
    if keywords_file and Path(keywords_file).exists():
        cmd.extend(["--keywords-file", str(keywords_file)])
    return call(cmd)


def cmd_ingest(args: argparse.Namespace) -> int:
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


def cmd_fetch(args: argparse.Namespace) -> int:
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


def cmd_voice(args: argparse.Namespace) -> int:
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


def cmd_preflight(args: argparse.Namespace) -> int:
    out = run_dir(args.run)
    meditation_seed = args.meditation_seed or input_dir(args.run) / "meditation_seed.json"
    resolved_voice = args.resolved_voice or input_dir(args.run) / "resolved_voice.json"
    cmd = [
        sys.executable,
        str(SCRIPTS / "outline_preflight.py"),
        "--meditation-seed",
        str(meditation_seed),
        "--resolved-voice",
        str(resolved_voice),
        "--out",
        str(args.out or out / "writing_brief.json"),
    ]
    evidence = args.evidence or out / "EvidencePack.json"
    if evidence.exists():
        cmd.extend(["--evidence", str(evidence)])
    return call(cmd)


def cmd_outline_draft(args: argparse.Namespace) -> int:
    out = run_dir(args.run)
    cmd = [
        sys.executable,
        str(SCRIPTS / "outline_draft.py"),
        "--brief",
        str(args.brief or out / "writing_brief.json"),
        "--out",
        str(args.out or out / "sermon_outline_draft.md"),
    ]
    return call(cmd)


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
    p.add_argument("--keywords-file", type=Path, help="Default: input/<run>/meditation_seed.json")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("ingest", help="Extract selected resources into citation-safe text")
    p.add_argument("run")
    p.add_argument("--backend", choices=["opendataloader", "pymupdf", "pdfplumber", "pypdf", "pdftotext"])
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("fetch", help="Download OA PDFs (S2 + Crossref/Unpaywall) into resources")
    p.add_argument("run")
    p.add_argument("--per-engine-limit", type=int, default=3)
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("voice", help="Resolve preaching voice into input/<run>/resolved_voice.json")
    p.add_argument("run")
    p.add_argument("--genre", required=True, help="본문장르 키 (예: gospel_parable)")
    p.add_argument("--tier", required=True, help="설교 유형 키 (예: pastoral)")
    p.add_argument("--season", help="절기 키 (예: ordinary)")
    p.add_argument("--preacher-voice", type=Path, help="preacher_voice.json (L1-개인, opt-in)")
    p.add_argument("--audience", type=Path, help="audience_profile.json (목회자 작성)")
    p.set_defaults(func=cmd_voice)

    p = sub.add_parser("preflight", help="Build writing_brief.json after HITL approvals")
    p.add_argument("run")
    p.add_argument("--meditation-seed", type=Path, help="Default: input/<run>/meditation_seed.json")
    p.add_argument("--resolved-voice", type=Path, help="Default: input/<run>/resolved_voice.json")
    p.add_argument("--evidence", type=Path)
    p.add_argument("--out", type=Path)
    p.set_defaults(func=cmd_preflight)

    p = sub.add_parser("outline-draft", help="Render writing_brief.json into a human-fillable outline draft")
    p.add_argument("run")
    p.add_argument("--brief", type=Path, help="Default: output/<run>/writing_brief.json")
    p.add_argument("--out", type=Path, help="Default: output/<run>/sermon_outline_draft.md")
    p.set_defaults(func=cmd_outline_draft)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
