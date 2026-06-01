#!/usr/bin/env python3
"""resource_ingest.py — 2→3단계 다리: 입수 원문(PDF/텍스트) → 페이지 보존 텍스트 + 매니페스트.

3단계 워크플로우(`references/research-workflow.md`)의 2단계(HITL 원문 입수)와
3단계(LLM 본문 분석)를 잇는다. 설교자가 `input/resources/<run>/`에 직접 내려받아 둔
원문 파일을 읽어, **인용을 위해 원문 페이지 번호를 보존한** 텍스트로 추출하고,
각 파일을 EvidencePack 레코드(DOI 기준)에 매핑한 `resource_manifest.json`을 만든다.

헌법 §7(유령인용 금지)·§11(스크립트는 측정·구조 합성만): 이 스크립트는 **추출과
매핑만** 한다. 산문(요약·분석)을 짓지 않는다 — 그건 에이전트가 페이지 표시 텍스트를
읽고 한다. 추출 텍스트는 목회자 자산(§9)이므로 gitignore되는 `output/` 아래에 둔다.

페이지 보존: 추출 텍스트는 각 페이지를 다음 마커로 구분한다(인용 시 grep 가능):

    ===== p.3 =====

에이전트는 이 마커로 `(저자 연도, p.3)` 형태의 정확한 페이지 인용을 만들 수 있다.

백엔드(있는 것 자동 선택, 품질 우선순위):
    1. opendataloader   — MS_Dev .skills/pdf-extractor Core 엔진(구조 JSON/Markdown).
    2. pymupdf (fitz)   — 선택 설치(고품질). AGPL.
    3. pdfplumber       — 선택 설치.
    4. pypdf            — requirements.txt 기본(순수 파이썬·BSD, 시스템 의존 0).
    5. pdftotext        — poppler 설치 시 subprocess(\\f=페이지 구분).
    (텍스트 레이어가 없는 스캔본은 tesseract가 있으면 best-effort OCR 폴백.)

사용법:
    python3 scripts/resource_ingest.py <run>
        → pack=output/<run>/EvidencePack.json
          resources=input/resources/<run>/
          out=output/<run>/resources/  manifest=output/<run>/resource_manifest.json
    python3 scripts/resource_ingest.py --pack P --resources R --out O [--manifest M]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PAGE_MARKER = "===== p.{n} ====="
# 페이지당 추출 글자수가 이 값 미만이면 텍스트 레이어 부재로 간주(OCR 후보).
TEXT_LAYER_MIN_CHARS = 16
PDF_EXTS = {".pdf"}
TEXT_EXTS = {".txt", ".md", ".text"}


# ---------------------------------------------------------------- 식별자/매핑

def slugify_doi(doi: str) -> str:
    """DOI를 파일명 안전 슬러그로. 10.x/abc → 10.x_abc (슬래시만 치환)."""
    return (doi or "").strip().replace("/", "_")


def slug_title(title: str) -> str:
    """제목 → 짧은 슬러그(DOI 없는 레코드 폴백용)."""
    t = re.sub(r"\s+", "-", (title or "").strip())
    t = re.sub(r"[^0-9A-Za-z가-힣\-_.]", "", t)
    return t[:48] or "untitled"


def record_id(rec: dict) -> str:
    """레코드의 안정 ID — DOI 슬러그 우선, 없으면 citekey, 없으면 제목 슬러그."""
    doi = (rec.get("doi") or "").strip()
    if doi:
        return slugify_doi(doi)
    ck = (rec.get("citekey") or "").strip()
    return ck or slug_title(rec.get("title") or "")


def display_path(path: Path, root: Path) -> str:
    """프로젝트 내부면 상대경로, 외부 커스텀 경로면 절대경로로 안전하게 표시."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


_NORM_RE = re.compile(r"[^0-9a-z가-힣]+")


def _norm_tokens(s: str) -> set[str]:
    s = (s or "").lower()
    return {t for t in _NORM_RE.split(s) if len(t) > 1}


def match_record(stem: str, head_text: str, records: list[dict]) -> tuple[dict | None, str]:
    """파일(stem + 첫 페이지 텍스트) → 레코드. (record_or_None, method)."""
    s = stem.strip().lower()
    # 1) 파일명 stem == DOI 슬러그(권장 규칙)
    for r in records:
        doi = (r.get("doi") or "").strip().lower()
        if doi and slugify_doi(doi) == s:
            return r, "doi-exact"
    # 2) 파일명에 DOI가 부분 포함(설교자가 접두사 등을 붙인 경우)
    for r in records:
        doi = (r.get("doi") or "").strip().lower()
        if doi and (slugify_doi(doi) in s or doi in s):
            return r, "doi-partial"
    # 3) citekey 일치
    for r in records:
        ck = (r.get("citekey") or "").strip().lower()
        if ck and ck == s:
            return r, "citekey"
    # 4) 제목 토큰 자카드(파일명 + 첫 페이지 텍스트 vs 레코드 제목)
    probe = _norm_tokens(stem + " " + head_text[:600])
    best, best_score = None, 0.0
    for r in records:
        rt = _norm_tokens(r.get("title") or "")
        if not rt:
            continue
        inter = len(probe & rt)
        if not inter:
            continue
        score = inter / len(rt)  # 레코드 제목 토큰이 얼마나 덮였나
        if score > best_score:
            best, best_score = r, score
    if best is not None and best_score >= 0.5:
        return best, f"title~{best_score:.2f}"
    return None, "unmatched"


# ---------------------------------------------------------------- 백엔드

def _backend_available() -> str:
    if _opendataloader_available():
        return "opendataloader"
    for mod, name in (("fitz", "pymupdf"), ("pdfplumber", "pdfplumber"), ("pypdf", "pypdf")):
        try:
            __import__(mod)
            return name
        except ImportError:
            continue
    if shutil.which("pdftotext"):
        return "pdftotext"
    return ""


def _pdf_extractor_script() -> Path:
    dev_root = Path(__file__).resolve().parents[3]
    return dev_root / ".skills" / "pdf-extractor" / "scripts" / "extract_pdf.py"


def _opendataloader_available() -> bool:
    return bool(shutil.which("uv") and _pdf_extractor_script().is_file())


def _pages_opendataloader(path: Path) -> list[str]:
    """MS_Dev .skills/pdf-extractor의 opendataloader Core 엔진을 페이지별 텍스트로 변환."""
    script = _pdf_extractor_script()
    if not script.is_file():
        raise RuntimeError(f"pdf-extractor 스크립트 없음: {script}")
    dev_root = script.parents[3]
    with tempfile.TemporaryDirectory(prefix="tspp-opendataloader-") as td:
        out_dir = Path(td)
        cmd = ["uv", "run", "python", str(script), "--input", str(path), "--output", str(out_dir)]
        proc = subprocess.run(
            cmd,
            cwd=str(dev_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=240,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip().splitlines()
            raise RuntimeError(detail[-1] if detail else "opendataloader 추출 실패")

        json_files = sorted(out_dir.glob("*.json"))
        if json_files:
            data = json.loads(json_files[0].read_text(encoding="utf-8", errors="replace"))
            page_count = int(data.get("number of pages") or 0) if isinstance(data, dict) else 0
            pages: list[list[str]] = [[] for _ in range(max(1, page_count))]
            for kid in data.get("kids", []) if isinstance(data, dict) else []:
                if not isinstance(kid, dict):
                    continue
                content = str(kid.get("content") or "").strip()
                if not content:
                    continue
                page_no = kid.get("page number") or 1
                try:
                    idx = max(0, int(page_no) - 1)
                except (TypeError, ValueError):
                    idx = 0
                while idx >= len(pages):
                    pages.append([])
                pages[idx].append(content)
            if any(pages):
                return ["\n\n".join(parts).strip() for parts in pages]

        md_files = sorted(out_dir.glob("*.md"))
        if md_files:
            return [md_files[0].read_text(encoding="utf-8", errors="replace")]
    raise RuntimeError("opendataloader 출력 JSON/Markdown 없음")


def _pages_pymupdf(path: Path) -> list[str]:
    import fitz  # type: ignore
    doc = fitz.open(path)
    try:
        return [doc[i].get_text("text") for i in range(doc.page_count)]
    finally:
        doc.close()


def _pages_pdfplumber(path: Path) -> list[str]:
    import pdfplumber  # type: ignore
    with pdfplumber.open(str(path)) as pdf:
        return [(pg.extract_text() or "") for pg in pdf.pages]


def _pages_pypdf(path: Path) -> list[str]:
    from pypdf import PdfReader  # type: ignore
    reader = PdfReader(str(path))
    return [(pg.extract_text() or "") for pg in reader.pages]


def _pages_pdftotext(path: Path) -> list[str]:
    # -layout: 단(컬럼) 보존. \f(form feed)가 페이지 경계.
    # errors="replace": pdftotext가 비-UTF8 바이트(특수 글리프·합자 등)를 내도
    # 전체 디코드가 깨지지 않게 한다(실측: 한 PDF에서 0x89로 strict 디코드 실패).
    out = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "pdftotext 실패")
    pages = out.stdout.split("\f")
    while pages and not pages[-1].strip():
        pages.pop()
    return pages or [out.stdout]


_EXTRACTORS = {
    "opendataloader": _pages_opendataloader,
    "pymupdf": _pages_pymupdf,
    "pdfplumber": _pages_pdfplumber,
    "pypdf": _pages_pypdf,
    "pdftotext": _pages_pdftotext,
}


def _ocr_pages(path: Path) -> list[str] | None:
    """텍스트 레이어 부재 시 best-effort OCR(tesseract+pdftoppm 둘 다 있을 때만)."""
    if not (shutil.which("pdftoppm") and shutil.which("tesseract")):
        return None
    import tempfile
    # 사용 가능한 OCR 언어 선택: kor 데이터 없으면 eng만(없는 데이터 지정 시 tesseract 실패).
    langs = subprocess.run(["tesseract", "--list-langs"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace").stdout
    avail = {ln.strip() for ln in langs.splitlines()[1:]}
    lang = "kor+eng" if {"kor", "eng"} <= avail else ("eng" if "eng" in avail else None)
    if lang is None:
        return None
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        # capture_output + errors="replace": pdftoppm가 stdout에 바이너리(PNG)를 흘려도
        # 디코드 크래시를 막는다. 이미지는 prefix로 파일에 쓰인다.
        pp = subprocess.run(["pdftoppm", "-r", "300", "-png", str(path), str(tdp / "pg")],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=600)
        if pp.returncode != 0:
            return None
        pages = []
        for img in sorted(tdp.glob("pg*.png")):
            r = subprocess.run(["tesseract", str(img), "-", "-l", lang],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=300)
            pages.append(r.stdout if r.returncode == 0 else "")
        return pages or None


def extract_pages(path: Path, backend: str) -> tuple[list[str], str]:
    """원문 파일 → (페이지 텍스트 리스트, 사용 백엔드). 인덱스 i = p.(i+1)."""
    ext = path.suffix.lower()
    if ext in TEXT_EXTS:
        return [path.read_text(encoding="utf-8", errors="replace")], "text"
    if ext not in PDF_EXTS:
        raise ValueError(f"지원하지 않는 확장자: {ext}")
    pages = _EXTRACTORS[backend](path)
    # 텍스트 레이어 빈약 → OCR 폴백 시도(OCR 실패가 추출 전체를 막지 않게 격리).
    if sum(len(p.strip()) for p in pages) < TEXT_LAYER_MIN_CHARS * max(1, len(pages)):
        try:
            ocr = _ocr_pages(path)
        except Exception:  # noqa: BLE001 — OCR은 best-effort; 실패 시 원본 텍스트 유지
            ocr = None
        if ocr is not None and sum(len(p.strip()) for p in ocr) > sum(len(p.strip()) for p in pages):
            return ocr, backend + "+ocr"
    return pages, backend


# ---------------------------------------------------------------- 출력 합성

def render_text(rec: dict | None, src: Path, backend: str, pages: list[str]) -> str:
    """페이지 마커가 박힌 추출 텍스트(에이전트 분석 입력)."""
    head = ["<!-- TSPP resource_ingest — 페이지 마커 보존, 인용: (저자 연도, p.N) -->"]
    if rec:
        head.append(f"# {rec.get('title') or '(제목 없음)'}")
        au = rec.get("authors")
        au = ", ".join(au) if isinstance(au, list) else (au or "")
        meta = [x for x in (au, str(rec.get("year") or ""), rec.get("doi") or "") if x]
        if meta:
            head.append(" · ".join(meta))
    head.append(f"<!-- source: {src.name} · backend: {backend} · pages: {len(pages)} -->")
    body = []
    for i, txt in enumerate(pages, 1):
        body.append("\n" + PAGE_MARKER.format(n=i) + "\n")
        body.append((txt or "").rstrip())
    return "\n".join(head) + "\n" + "\n".join(body) + "\n"


def render_analysis_packet(run: str | None, manifest: list[dict], root: Path) -> str:
    """에이전트가 3단계 원문 분석에 바로 진입하도록 구조화한 작업 패킷."""
    extracted = [m for m in manifest if str(m.get("status", "")).startswith("extracted")]
    abstract_only = [m for m in manifest if m.get("status") == "abstract_only"]
    errors = [m for m in manifest if m.get("status") == "extract_error"]
    lines = [
        "# TSPP Resource Analysis Packet",
        "",
        f"- Run: `{run or '(custom)'}`",
        f"- Extracted full texts: {len(extracted)}",
        f"- Abstract-only fallbacks: {len(abstract_only)}",
        f"- Extraction errors: {len(errors)}",
        "",
        "## LLM Analysis Protocol",
        "",
        "1. Read the extracted text files listed below before making claims from a source.",
        "2. Cite full-text claims with the preserved `===== p.N =====` page marker, e.g. `(Author Year, p.N)`.",
        "3. Do not quote or cite abstract-only records as if full text was read.",
        "4. Separate what supports, challenges, or extends the sermon meditation.",
        "5. Keep academic insight subordinate to the biblical text and the preacher's original meditation.",
        "",
        "## Extracted Full Texts",
        "",
    ]
    if extracted:
        for i, m in enumerate(extracted, 1):
            title = m.get("matched_title") or m.get("source_file") or "(unmatched source)"
            path = m.get("out_text") or ""
            lines.extend([
                f"### {i}. {title}",
                f"- Text path: `{path}`",
                f"- Source file: `{m.get('source_file')}`",
                f"- DOI: `{m.get('matched_doi') or ''}`",
                f"- Pages: {m.get('pages')} · chars: {m.get('chars')} · backend: `{m.get('backend')}`",
                f"- Match: `{m.get('match_method')}` · status: `{m.get('status')}`",
                "",
            ])
    else:
        lines.append("_No full-text resources extracted yet._\n")

    lines.extend(["## Abstract-Only Fallbacks", ""])
    if abstract_only:
        for i, m in enumerate(abstract_only, 1):
            lines.append(f"{i}. {m.get('matched_title') or '(제목 없음)'} — DOI `{m.get('matched_doi') or ''}`")
    else:
        lines.append("_None._")
    lines.append("")

    if errors:
        lines.extend(["## Extraction Errors", ""])
        for i, m in enumerate(errors, 1):
            lines.append(f"{i}. `{m.get('source_file')}` — {m.get('error')}")
        lines.append("")

    lines.extend([
        "## Suggested Next Prompt",
        "",
        "Read this packet and the extracted full-text files, then produce a source-grounded analysis:",
        "",
        "- Key thesis and argument structure of each selected source",
        "- Page-grounded insights relevant to the sermon text",
        "- Where the source supports/challenges/extends the original meditation",
        "- Usable but non-showy homiletical implications",
        "- Citation-safe notes with page markers",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", nargs="?", help="실행 이름(output/<run>/ 규약). 미지정 시 --pack 필수")
    ap.add_argument("--pack", help="EvidencePack.json 경로")
    ap.add_argument("--resources", help="입수 원문 폴더(기본 input/resources/<run>/)")
    ap.add_argument("--out", help="추출 텍스트 출력 폴더(기본 output/<run>/resources/)")
    ap.add_argument("--manifest", help="매니페스트 경로(기본 output/<run>/resource_manifest.json)")
    ap.add_argument("--backend", choices=list(_EXTRACTORS), help="백엔드 강제(기본 자동)")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    if args.run:
        pack = Path(args.pack) if args.pack else root / "output" / args.run / "EvidencePack.json"
        res_dir = Path(args.resources) if args.resources else root / "input" / "resources" / args.run
        out_dir = Path(args.out) if args.out else root / "output" / args.run / "resources"
        man_path = Path(args.manifest) if args.manifest else root / "output" / args.run / "resource_manifest.json"
        packet_path = man_path.parent / "resource_analysis_packet.md"
    else:
        if not args.pack:
            ap.error("run 또는 --pack 중 하나는 필요합니다")
        pack = Path(args.pack)
        res_dir = Path(args.resources) if args.resources else pack.parent.parent.parent / "input" / "resources" / pack.parent.name
        out_dir = Path(args.out) if args.out else pack.parent / "resources"
        man_path = Path(args.manifest) if args.manifest else pack.parent / "resource_manifest.json"
        packet_path = man_path.parent / "resource_analysis_packet.md"

    if not pack.exists():
        print(f"[resource_ingest] EvidencePack 없음: {pack}", file=sys.stderr)
        return 1
    records = json.loads(pack.read_text(encoding="utf-8")).get("records", [])

    # 입수 폴더 없으면 만들고 안내(2단계 진입점)
    if not res_dir.exists():
        res_dir.mkdir(parents=True, exist_ok=True)
        print(f"[resource_ingest] 입수 폴더 생성: {res_dir}", file=sys.stderr)
        print("  → evidence_list.md의 '권장 파일명'으로 PDF를 이 폴더에 넣고 다시 실행하세요.", file=sys.stderr)

    backend = args.backend or _backend_available()
    src_files = sorted(p for p in res_dir.iterdir() if p.is_file()
                       and p.suffix.lower() in (PDF_EXTS | TEXT_EXTS)) if res_dir.exists() else []

    if src_files and not backend:
        print("[resource_ingest] PDF 백엔드 없음. requirements.txt 설치(pip install -r requirements.txt) "
              "또는 poppler(pdftotext) 설치가 필요합니다.", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest, matched_ids = [], set()
    for src in src_files:
        try:
            if src.suffix.lower() in PDF_EXTS:
                pages, used = extract_pages(src, backend)
            else:
                pages, used = [src.read_text(encoding="utf-8", errors="replace")], "text"
        except Exception as e:  # noqa: BLE001 — 한 파일 실패가 전체를 막지 않게
            manifest.append({"source_file": src.name, "status": "extract_error", "error": str(e)[:200]})
            print(f"[resource_ingest] 추출 실패 {src.name}: {e}", file=sys.stderr)
            continue
        head_text = pages[0] if pages else ""
        rec, method = match_record(src.stem, head_text, records)
        rid = record_id(rec) if rec else slug_title(src.stem)
        out_file = out_dir / (rid + ".txt")
        out_file.write_text(render_text(rec, src, used, pages), encoding="utf-8")
        if rec:
            matched_ids.add(record_id(rec))
        manifest.append({
            "source_file": src.name,
            "out_text": display_path(out_file, root),
            "backend": used,
            "pages": len(pages),
            "chars": sum(len(p) for p in pages),
            "match_method": method,
            "matched_doi": (rec.get("doi") if rec else None),
            "matched_title": (rec.get("title") if rec else None),
            "status": "extracted" if rec else "extracted_unmatched",
        })

    # 소프트 폴백(§3): 원문 미입수 레코드 → abstract_only 표시
    for r in records:
        if record_id(r) in matched_ids:
            continue
        manifest.append({
            "source_file": None,
            "matched_doi": r.get("doi"),
            "matched_title": r.get("title"),
            "has_abstract": bool((r.get("abstract") or "").strip()),
            "status": "abstract_only",
        })

    man_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(render_analysis_packet(args.run, manifest, root), encoding="utf-8")
    man_path.write_text(json.dumps(
        {"schema_version": 1, "backend_default": backend, "resources_dir": display_path(res_dir, root),
         "out_dir": display_path(out_dir, root), "total_records": len(records),
         "ingested": len(src_files), "analysis_packet": display_path(packet_path, root), "records": manifest},
        ensure_ascii=False, indent=2), encoding="utf-8")

    ext = sum(1 for m in manifest if m["status"].startswith("extracted"))
    ab = sum(1 for m in manifest if m["status"] == "abstract_only")
    print(f"[resource_ingest] 백엔드={backend or '없음'} · 입수추출 {ext}건 · 미입수(초록폴백) {ab}건")
    print(f"  텍스트 → {display_path(out_dir, root)}/  ·  매니페스트 → {display_path(man_path, root)}")
    print(f"  LLM 분석 패킷 → {display_path(packet_path, root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
