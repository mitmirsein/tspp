#!/usr/bin/env python3
"""scripture_import.py — 성경 본문 데이터를 TSPP 정본 레이아웃으로 변환 (vendoring 도구).

성경 인용 정합 게이트(QUALITY_UPGRADE P0-1)의 데이터 준비 단계.
공개(퍼블릭 도메인) 본문 JSON을 받아 `data/scripture/<translation>/`에
책별 파일 + index.json으로 변환한다. 한 번 변환해 커밋하면 런타임에는
scripture_pack.py / scripture_check.py 가 이 레이아웃만 읽는다.

지원 입력 포맷:
- scrollmapper: https://github.com/scrollmapper/bible_databases formats/json
  {"translation": "...", "books": [{"name": "...", "chapters": [{"chapter": N,
   "verses": [{"verse": N, "text": "..."}]}]}]}
- lines: 한 줄 = 한 절. 한국 성경 텍스트 덤프의 통용 형식.
      창1:1 태초에 하나님이 천지를 창조하시니라
      창세기 1:2 땅이 혼돈하고 ...        (책 이름·약칭, 공백 유무 모두 허용)
- tsv: 책<TAB>장<TAB>절<TAB>본문  (책 = 한글명/약칭/영문명/권 번호 1~66)

산출 레이아웃:
    <out>/index.json              번역본 메타 + 책 목록(한글명·약칭·장절 수)
    <out>/40_Matthew.json         {"eng","ko","chapters":{"21":{"38":"..."}}}

배치 규칙 (저작권):
- **퍼블릭 도메인 본문만** `data/scripture/`(커밋 영역)에 둔다 — KorRV가 여기 있다.
- **사용자 보유본(개역개정·새번역 등 저작권 본)은 `input/scripture/<code>/`**
  (gitignore, 로컬 전용 §9)에 둔다 — `--out` 생략 시 자동으로 여기에 변환된다.
  scripture_lib는 input/scripture를 *우선* 탐색하므로 변환만 해 두면
  `--translation <code>` 또는 `.env`의 `TSPP_TRANSLATION=<code>`로 즉시 쓸 수 있다.

사용:
    # 사용자 보유 개역개정 텍스트 → 로컬 전용 변환 (기본 출력: input/scripture/NKRV)
    python scripts/scripture_import.py --source ~/nkrv.txt --format lines \
        --translation NKRV --label "개역개정 (사용자 보유)" --license "사용자 사적 이용"

    # vendored 공개본 (커밋 영역 — 퍼블릭 도메인만)
    python scripts/scripture_import.py --source KorRV.json --format scrollmapper \
        --translation KorRV --label "개역한글판 (1961)" \
        --license "퍼블릭 도메인 (저작권 만료)" --out data/scripture/KorRV
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── 정경 66권 — 영문 정규명 · 한글명 · 표준 약칭 · 별칭 ─────────────────────
# (영문 별칭은 scrollmapper 류 소스의 "I Samuel"/"Revelation of John" 표기 흡수용)
BOOKS = [
    # (n, eng, ko, [abbr/aliases...])
    (1, "Genesis", "창세기", ["창"]),
    (2, "Exodus", "출애굽기", ["출"]),
    (3, "Leviticus", "레위기", ["레"]),
    (4, "Numbers", "민수기", ["민"]),
    (5, "Deuteronomy", "신명기", ["신"]),
    (6, "Joshua", "여호수아", ["수"]),
    (7, "Judges", "사사기", ["삿"]),
    (8, "Ruth", "룻기", ["룻"]),
    (9, "1 Samuel", "사무엘상", ["삼상", "I Samuel"]),
    (10, "2 Samuel", "사무엘하", ["삼하", "II Samuel"]),
    (11, "1 Kings", "열왕기상", ["왕상", "I Kings"]),
    (12, "2 Kings", "열왕기하", ["왕하", "II Kings"]),
    (13, "1 Chronicles", "역대상", ["대상", "I Chronicles"]),
    (14, "2 Chronicles", "역대하", ["대하", "II Chronicles"]),
    (15, "Ezra", "에스라", ["스"]),
    (16, "Nehemiah", "느헤미야", ["느"]),
    (17, "Esther", "에스더", ["에"]),
    (18, "Job", "욥기", ["욥"]),
    (19, "Psalms", "시편", ["시", "Psalm"]),
    (20, "Proverbs", "잠언", ["잠"]),
    (21, "Ecclesiastes", "전도서", ["전"]),
    (22, "Song of Solomon", "아가", ["아", "Song of Songs"]),
    (23, "Isaiah", "이사야", ["사"]),
    (24, "Jeremiah", "예레미야", ["렘"]),
    (25, "Lamentations", "예레미야애가", ["애", "애가"]),
    (26, "Ezekiel", "에스겔", ["겔"]),
    (27, "Daniel", "다니엘", ["단"]),
    (28, "Hosea", "호세아", ["호"]),
    (29, "Joel", "요엘", ["욜"]),
    (30, "Amos", "아모스", ["암"]),
    (31, "Obadiah", "오바댜", ["옵"]),
    (32, "Jonah", "요나", ["욘"]),
    (33, "Micah", "미가", ["미"]),
    (34, "Nahum", "나훔", ["나"]),
    (35, "Habakkuk", "하박국", ["합"]),
    (36, "Zephaniah", "스바냐", ["습"]),
    (37, "Haggai", "학개", ["학"]),
    (38, "Zechariah", "스가랴", ["슥"]),
    (39, "Malachi", "말라기", ["말"]),
    (40, "Matthew", "마태복음", ["마"]),
    (41, "Mark", "마가복음", ["막"]),
    (42, "Luke", "누가복음", ["눅"]),
    (43, "John", "요한복음", ["요"]),
    (44, "Acts", "사도행전", ["행"]),
    (45, "Romans", "로마서", ["롬"]),
    (46, "1 Corinthians", "고린도전서", ["고전", "I Corinthians"]),
    (47, "2 Corinthians", "고린도후서", ["고후", "II Corinthians"]),
    (48, "Galatians", "갈라디아서", ["갈"]),
    (49, "Ephesians", "에베소서", ["엡"]),
    (50, "Philippians", "빌립보서", ["빌"]),
    (51, "Colossians", "골로새서", ["골"]),
    (52, "1 Thessalonians", "데살로니가전서", ["살전", "I Thessalonians"]),
    (53, "2 Thessalonians", "데살로니가후서", ["살후", "II Thessalonians"]),
    (54, "1 Timothy", "디모데전서", ["딤전", "I Timothy"]),
    (55, "2 Timothy", "디모데후서", ["딤후", "II Timothy"]),
    (56, "Titus", "디도서", ["딛"]),
    (57, "Philemon", "빌레몬서", ["몬"]),
    (58, "Hebrews", "히브리서", ["히"]),
    (59, "James", "야고보서", ["약"]),
    (60, "1 Peter", "베드로전서", ["벧전", "I Peter"]),
    (61, "2 Peter", "베드로후서", ["벧후", "II Peter"]),
    (62, "1 John", "요한일서", ["요일", "I John"]),
    (63, "2 John", "요한이서", ["요이", "II John"]),
    (64, "3 John", "요한삼서", ["요삼", "III John"]),
    (65, "Jude", "유다서", ["유"]),
    (66, "Revelation", "요한계시록", ["계", "계시록", "Revelation of John"]),
]


def _lookup(name: str) -> tuple | None:
    """소스의 책 이름(영문 변형 포함)을 정경 테이블 항목으로 해석."""
    n = name.strip().lower()
    for row in BOOKS:
        cands = [row[1].lower(), row[2].lower()] + [a.lower() for a in row[3]]
        if n in cands:
            return row
    return None


def convert_scrollmapper(source: Path) -> dict[int, dict[int, dict[int, str]]]:
    """scrollmapper JSON → {book_n: {chapter: {verse: text}}}."""
    data = json.loads(source.read_text(encoding="utf-8"))
    out: dict[int, dict[int, dict[int, str]]] = {}
    for b in data.get("books", []):
        row = _lookup(str(b.get("name", "")))
        if row is None:
            print(f"[scripture_import] 미해석 책 이름 건너뜀: {b.get('name')}", file=sys.stderr)
            continue
        chapters: dict[int, dict[int, str]] = {}
        for ch in b.get("chapters", []):
            cn = int(ch.get("chapter", 0))
            verses = {int(v["verse"]): str(v.get("text", "")).strip()
                      for v in ch.get("verses", []) if v.get("verse")}
            if cn and verses:
                chapters[cn] = verses
        if chapters:
            out[row[0]] = chapters
    return out


_LINE_RE = re.compile(
    r"^\s*(?P<book>[가-힣A-Za-z][가-힣A-Za-z0-9 ]*?)\s*"
    r"(?P<ch>\d{1,3})\s*[:：]\s*(?P<v>\d{1,3})[\s.]+(?P<text>\S.*)$")


def convert_lines(source: Path) -> dict[int, dict[int, dict[int, str]]]:
    """lines 포맷('창1:1 본문' / '창세기 1:1 본문') → 표준 dict."""
    out: dict[int, dict[int, dict[int, str]]] = {}
    unknown: dict[str, int] = {}
    skipped = 0
    for raw in source.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip():
            continue
        m = _LINE_RE.match(raw)
        if not m:
            skipped += 1
            continue
        row = _lookup(m.group("book"))
        if row is None:
            unknown[m.group("book").strip()] = unknown.get(m.group("book").strip(), 0) + 1
            continue
        out.setdefault(row[0], {}).setdefault(int(m.group("ch")), {})[int(m.group("v"))] = \
            m.group("text").strip()
    if skipped:
        print(f"[scripture_import] 형식 불일치로 건너뛴 줄: {skipped}", file=sys.stderr)
    for name, n in sorted(unknown.items(), key=lambda x: -x[1])[:5]:
        print(f"[scripture_import] 미해석 책 이름 '{name}' ({n}줄) — BOOKS 별칭 확인",
              file=sys.stderr)
    return out


def convert_tsv(source: Path) -> dict[int, dict[int, dict[int, str]]]:
    """tsv 포맷(책\t장\t절\t본문) → 표준 dict. 책 = 이름/약칭/권번호."""
    out: dict[int, dict[int, dict[int, str]]] = {}
    skipped = 0
    for raw in source.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = raw.rstrip("\n").split("\t")
        if len(parts) < 4 or not parts[1].strip().isdigit():
            skipped += 1
            continue
        book_tok = parts[0].strip()
        if book_tok.isdigit() and 1 <= int(book_tok) <= 66:
            bn = int(book_tok)
        else:
            row = _lookup(book_tok)
            if row is None:
                skipped += 1
                continue
            bn = row[0]
        try:
            ch, v = int(parts[1]), int(parts[2])
        except ValueError:
            skipped += 1
            continue
        text = "\t".join(parts[3:]).strip()
        if text:
            out.setdefault(bn, {}).setdefault(ch, {})[v] = text
    if skipped:
        print(f"[scripture_import] 형식 불일치로 건너뛴 줄: {skipped}", file=sys.stderr)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="성경 본문 → TSPP 정본 레이아웃 변환")
    ap.add_argument("--source", type=Path, required=True, help="입력 본문 파일")
    ap.add_argument("--format", choices=["scrollmapper", "lines", "tsv"],
                    default="scrollmapper")
    ap.add_argument("--translation", required=True, help="번역본 키 (예: KorRV, NKRV)")
    ap.add_argument("--label", required=True, help="사람이 읽는 번역본 이름")
    ap.add_argument("--license", required=True, help="라이선스 표기 (배치 위치의 근거)")
    ap.add_argument("--source-url", default="", help="원 데이터 출처 URL")
    ap.add_argument("--out", type=Path, default=None,
                    help="산출 디렉터리 (기본: input/scripture/<translation> — 로컬 전용)")
    args = ap.parse_args(argv)

    if not args.source.is_file():
        print(f"[scripture_import] 입력 파일이 없습니다: {args.source}", file=sys.stderr)
        return 2

    if args.out is None:
        args.out = ROOT / "input" / "scripture" / args.translation
        print(f"[scripture_import] --out 생략 → 사용자 보유본 영역(input/scripture, "
              f"gitignore·로컬 전용)에 변환합니다: {args.out}")

    # 저작권 가드: 커밋 영역(data/scripture)에 비공개 라이선스 본문이 들어가는 것을 경고
    try:
        in_commit_area = (ROOT / "data" / "scripture") in args.out.resolve().parents \
            or args.out.resolve() == (ROOT / "data" / "scripture").resolve()
    except OSError:
        in_commit_area = False
    if in_commit_area and not re.search(r"퍼블릭|public|만료|CC[ -]?BY", args.license, re.I):
        print("[scripture_import] ⚠️ 경고: data/scripture/는 git 커밋 영역입니다. "
              f"라이선스 표기('{args.license}')가 공개 이용을 명시하지 않습니다 — "
              "저작권 본문은 input/scripture/에 두십시오(--out 생략).", file=sys.stderr)

    if args.format == "lines":
        books = convert_lines(args.source)
    elif args.format == "tsv":
        books = convert_tsv(args.source)
    else:
        books = convert_scrollmapper(args.source)
    if len(books) != 66:
        print(f"[scripture_import] 경고: 변환된 책 수 {len(books)} (정경 66권 미달 — 산출물 확인 필요)",
              file=sys.stderr)

    args.out.mkdir(parents=True, exist_ok=True)
    index_books = []
    total_verses = 0
    for n, eng, ko, aliases in BOOKS:
        chapters = books.get(n)
        if not chapters:
            continue
        fname = f"{n:02d}_{eng.replace(' ', '_')}.json"
        payload = {
            "eng": eng,
            "ko": ko,
            "chapters": {str(c): {str(v): t for v, t in sorted(vs.items())}
                         for c, vs in sorted(chapters.items())},
        }
        (args.out / fname).write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")
        verse_counts = {str(c): max(vs) for c, vs in sorted(chapters.items())}
        total_verses += sum(len(vs) for vs in chapters.values())
        index_books.append({
            "n": n, "eng": eng, "ko": ko,
            "abbr": [a for a in aliases if not a[0].isascii()] or aliases[:1],
            "aliases": aliases,
            "file": fname,
            "chapters": verse_counts,
        })

    index = {
        "schema_version": 1,
        "translation": args.translation,
        "label": args.label,
        "language": "ko",
        "license": args.license,
        "source_url": args.source_url,
        "imported_at": datetime.date.today().isoformat(),
        "total_books": len(index_books),
        "total_verses": total_verses,
        "_note": ("TSPP 성경 인용 정합 게이트(P0-1)의 정본 본문 데이터. "
                  "scripture_pack.py가 pericope를 추출하고 scripture_check.py가 인용을 대조한다. "
                  "저작권이 만료/허용된 본문만 커밋한다 — 출처·라이선스는 VENDOR.md 참조."),
        "books": index_books,
    }
    (args.out / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[scripture_import] 완료: {len(index_books)}권 {total_verses}절 → {args.out}")
    print(f"[scripture_import] index: {args.out / 'index.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
