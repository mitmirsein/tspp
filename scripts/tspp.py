#!/usr/bin/env python3
"""TSPP single-command entry point.

This wrapper keeps the beginner-facing workflow stable while delegating the
actual work to the existing pipeline scripts.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
DEFAULT_ENGINES = "kci-api-searcher,nlk-ejournal-searcher,semantic-scholar,crossref-journal-searcher"


def run_dir(run: str) -> Path:
    return ROOT / "output" / run


def resource_dir(run: str) -> Path:
    return ROOT / "input" / "resources" / run


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
    res = resource_dir(args.run)
    out.mkdir(parents=True, exist_ok=True)
    res.mkdir(parents=True, exist_ok=True)
    print(f"[tspp] run initialized: {args.run}")
    print(f"- output: {rel(out)}")
    print(f"- resources: {rel(res)}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    out = run_dir(args.run)
    res = resource_dir(args.run)
    paths = [
        ("run output", out),
        ("resource input", res),
        ("meditation seed", out / "meditation_seed.json"),
        ("EvidencePack", out / "EvidencePack.json"),
        ("evidence list", out / "evidence_list.md"),
        ("resource manifest", out / "resource_manifest.json"),
        ("analysis packet", out / "resource_analysis_packet.md"),
        ("resolved voice", out / "resolved_voice.json"),
        ("writing brief", out / "writing_brief.json"),
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
    keywords_file = args.keywords_file or out / "meditation_seed.json"
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
    cmd = [
        sys.executable,
        str(SCRIPTS / "resource_ingest.py"),
        args.run,
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

    p = sub.add_parser("preflight", help="Build writing_brief.json after HITL approvals")
    p.add_argument("run")
    p.add_argument("--meditation-seed", type=Path, required=True)
    p.add_argument("--resolved-voice", type=Path, required=True)
    p.add_argument("--evidence", type=Path)
    p.add_argument("--out", type=Path)
    p.set_defaults(func=cmd_preflight)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

