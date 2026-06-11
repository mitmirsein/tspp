#!/usr/bin/env python3
"""scripture_lib.py — 성경 본문 로딩·장절 참조 파싱·인용 대조 공용 라이브러리.

성경 인용 정합 게이트(QUALITY_UPGRADE P0-1)의 공용 부품.
scripture_pack.py(pericope 추출)와 scripture_check.py(인용 대조)가 임포트한다.
homiletic_audit가 voice_ingest를 재사용하는 것과 같은 패턴(측정 로직 중복 금지).

데이터 레이아웃은 scripture_import.py가 만든 `data/scripture/<translation>/`:
    index.json               번역본 메타 + 책 목록(한글명·약칭·장별 절수)
    NN_Book.json             {"eng","ko","chapters":{"21":{"38":"본문"}}}

- 순수 stdlib.
- 이 모듈은 *측정·조회*만 한다. 산문 생성 없음(§11).
"""
from __future__ import annotations

import difflib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_TRANSLATION = "KorRV"
_PKG_ROOT = Path(__file__).resolve().parent.parent


# ── 번역본 로더 ───────────────────────────────────────────────────────────────

class Translation:
    """한 번역본의 index + 책 본문 lazy 로더."""

    def __init__(self, root: Path):
        self.root = Path(root)
        idx_path = self.root / "index.json"
        if not idx_path.is_file():
            raise FileNotFoundError(f"index.json이 없습니다: {idx_path}")
        self.index = json.loads(idx_path.read_text(encoding="utf-8"))
        self.code = self.index.get("translation", self.root.name)
        self.label = self.index.get("label", self.code)
        self.license = self.index.get("license", "")
        self._by_n: dict[int, dict] = {b["n"]: b for b in self.index["books"]}
        self._name_map: dict[str, int] = {}
        for b in self.index["books"]:
            for nm in [b["ko"], b["eng"]] + b.get("aliases", []) + b.get("abbr", []):
                self._name_map[nm.strip().lower().replace(" ", "")] = b["n"]
        self._book_cache: dict[int, dict] = {}

    def book_meta(self, n: int) -> dict | None:
        return self._by_n.get(n)

    def resolve_book(self, name: str) -> int | None:
        return self._name_map.get(name.strip().lower().replace(" ", ""))

    def chapter_count(self, n: int) -> int:
        meta = self._by_n.get(n)
        return max(int(c) for c in meta["chapters"]) if meta else 0

    def verse_count(self, n: int, chapter: int) -> int:
        meta = self._by_n.get(n)
        if not meta:
            return 0
        return int(meta["chapters"].get(str(chapter), 0))

    def _load_book(self, n: int) -> dict:
        if n not in self._book_cache:
            meta = self._by_n[n]
            self._book_cache[n] = json.loads(
                (self.root / meta["file"]).read_text(encoding="utf-8"))
        return self._book_cache[n]

    def verse_text(self, n: int, chapter: int, verse: int) -> str | None:
        try:
            return self._load_book(n)["chapters"][str(chapter)][str(verse)]
        except KeyError:
            return None

    def get_range(self, n: int, chapter: int, v1: int, v2: int) -> list[dict]:
        """[{'v': N, 'text': ...}] — 존재하는 절만 (범위 검증은 호출자 몫)."""
        out = []
        for v in range(v1, v2 + 1):
            t = self.verse_text(n, chapter, v)
            if t is not None:
                out.append({"v": v, "text": t})
        return out


def translation_roots(data_dir: Path | None = None) -> list[Path]:
    """번역본 탐색 루트 (우선순위 순).

    1. --data 명시 경로 (있으면 최우선)
    2. <TSPP_WORKSPACE>/input/scripture — 워크스페이스 사용자 보유본
    3. <repo>/input/scripture — **사용자 보유본**(개역개정·새번역 등 저작권 본 —
       gitignore 영역, 로컬 전용 §9)
    4. <repo>/data/scripture — vendored 공개본(KorRV, 커밋됨)

    같은 코드가 여러 곳에 있으면 사용자 보유본이 vendored 본을 가린다(override).
    """
    roots: list[Path] = []
    if data_dir:
        roots.append(Path(data_dir))
    ws = os.environ.get("TSPP_WORKSPACE", "").strip()
    if ws:
        roots.append(Path(ws) / "input" / "scripture")
    roots.append(_PKG_ROOT / "input" / "scripture")
    roots.append(_PKG_ROOT / "data" / "scripture")
    # 중복 제거(순서 보존)
    seen, uniq = set(), []
    for r in roots:
        rp = r.resolve() if r.exists() else r
        if rp not in seen:
            seen.add(rp)
            uniq.append(r)
    return uniq


def load_translation(data_dir: Path | None = None,
                     code: str = DEFAULT_TRANSLATION) -> Translation:
    """번역본 로드 — translation_roots() 순서로 탐색."""
    searched = []
    for root in translation_roots(data_dir):
        cand = root / code
        if (cand / "index.json").is_file():
            return Translation(cand)
        searched.append(str(cand))
    raise FileNotFoundError(
        f"번역본 '{code}'를 찾지 못했습니다. 탐색 경로: {searched}. "
        "사용자 보유본은 scripture_import.py로 변환해 input/scripture/<code>/에 두십시오.")


def list_translations(data_dir: Path | None = None) -> list[dict]:
    """탐색 루트의 가용 번역본 목록 — [{'code','label','license','root'}]."""
    out, seen = [], set()
    for root in translation_roots(data_dir):
        if not root.is_dir():
            continue
        for idx in sorted(root.glob("*/index.json")):
            code = idx.parent.name
            if code in seen:
                continue  # 우선순위 높은 루트가 가림
            seen.add(code)
            try:
                meta = json.loads(idx.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            out.append({"code": code, "label": meta.get("label", code),
                        "license": meta.get("license", ""), "root": str(root)})
    return out


# ── 장절 참조 파싱 ────────────────────────────────────────────────────────────

@dataclass
class Ref:
    """파싱된 장절 참조 하나 (단일 장 내 절 범위 목록)."""
    raw: str
    book_n: int | None          # None = 책 미상(문맥 책으로 해석할 것)
    book_label: str
    chapter: int
    ranges: list[tuple[int, int]] = field(default_factory=list)  # 빈 리스트 = 장 전체
    book_explicit: bool = True
    pos: int = 0                # draft 내 시작 오프셋

    def label(self) -> str:
        if not self.ranges:
            return f"{self.book_label} {self.chapter}장"
        parts = [f"{a}" if a == b else f"{a}-{b}" for a, b in self.ranges]
        return f"{self.book_label} {self.chapter}:{','.join(parts)}"


def _book_alt(tr: Translation) -> str:
    """책 이름 정규식 alternation — 긴 이름 우선(한글명 → 약칭)."""
    names: set[str] = set()
    for b in tr.index["books"]:
        names.add(b["ko"])
        for a in b.get("abbr", []):
            if not a.isascii():
                names.add(a)
    return "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))


# 절 명세: "38", "38-39", "38,40", "38-39,45-46" (+ 절/상반절 꼬리 허용)
_VERSESPEC = r"\d{1,3}(?:\s*[-~–]\s*\d{1,3})?(?:\s*,\s*\d{1,3}(?:\s*[-~–]\s*\d{1,3})?)*"


def _parse_versespec(spec: str) -> list[tuple[int, int]]:
    ranges = []
    for part in re.split(r"\s*,\s*", spec.strip()):
        m = re.match(r"(\d{1,3})(?:\s*[-~–]\s*(\d{1,3}))?", part)
        if m:
            a = int(m.group(1))
            b = int(m.group(2)) if m.group(2) else a
            ranges.append((a, b) if a <= b else (b, a))
    return ranges


def build_patterns(tr: Translation) -> list[tuple[str, re.Pattern]]:
    book = _book_alt(tr)
    return [
        # 마태복음 21:38-39 / 마 21:38,40 (책 명시 + 장:절)
        ("book_cv", re.compile(
            rf"(?P<book>{book})\s*(?P<ch>\d{{1,3}})\s*[:：]\s*(?P<vs>{_VERSESPEC})")),
        # 마태복음 21장 38-39절 / 마태복음 21장 (책 명시 + N장 [M절])
        ("book_jang", re.compile(
            rf"(?P<book>{book})\s*(?P<ch>\d{{1,3}})\s*장(?:\s*(?P<vs>{_VERSESPEC})\s*절)?")),
        # 시편 23편 [3절]
        ("book_pyeon", re.compile(
            rf"(?P<book>시편|시)\s*(?P<ch>\d{{1,3}})\s*편(?:\s*(?P<vs>{_VERSESPEC})\s*절)?")),
        # 책 없는 21:38-39 (문맥 책으로 해석 — 시간 표기 등 오탐 가능성은 호출자가 zone으로 거름)
        ("bare_cv", re.compile(
            rf"(?<![가-힣\d:．\.])(?P<ch>\d{{1,3}})\s*[:：]\s*(?P<vs>{_VERSESPEC})")),
    ]


def parse_refs(text: str, tr: Translation, default_book: int | None = None) -> list[Ref]:
    """draft 전체에서 장절 참조를 추출. 겹치는 매치는 책-명시 패턴 우선."""
    taken: list[tuple[int, int]] = []
    refs: list[Ref] = []
    for kind, pat in build_patterns(tr):
        for m in pat.finditer(text):
            s, e = m.span()
            if any(s < te and e > ts for ts, te in taken):
                continue  # 이미 더 구체적인 패턴이 차지한 구간
            gd = m.groupdict()
            if kind.startswith("book"):
                bn = tr.resolve_book(gd["book"])
                if bn is None:
                    continue
                explicit = True
                label = tr.book_meta(bn)["ko"]
            else:
                bn = default_book
                explicit = False
                label = tr.book_meta(bn)["ko"] if bn and tr.book_meta(bn) else "(책 미상)"
            ranges = _parse_versespec(gd["vs"]) if gd.get("vs") else []
            refs.append(Ref(raw=m.group(0).strip(), book_n=bn, book_label=label,
                            chapter=int(gd["ch"]), ranges=ranges,
                            book_explicit=explicit, pos=s))
            taken.append((s, e))
    refs.sort(key=lambda r: r.pos)
    return refs


def parse_passage(s: str, tr: Translation) -> Ref | None:
    """seed의 passage 문자열("마태복음 21:38-39") → Ref 하나."""
    refs = parse_refs(s, tr)
    return refs[0] if refs else None


def validate_ref(ref: Ref, tr: Translation) -> list[str]:
    """존재 검증 — 문제 목록(빈 리스트 = 정상). 책 미상 ref는 책이 채워져 있어야 한다."""
    problems = []
    if ref.book_n is None:
        return [f"책을 해석할 수 없음: '{ref.raw}'"]
    meta = tr.book_meta(ref.book_n)
    if meta is None:
        return [f"존재하지 않는 책 번호: {ref.book_n}"]
    vc = tr.verse_count(ref.book_n, ref.chapter)
    if vc == 0:
        problems.append(
            f"{meta['ko']}에 {ref.chapter}장이 없음 (총 {tr.chapter_count(ref.book_n)}장)")
        return problems
    for a, b in ref.ranges:
        if b > vc:
            problems.append(
                f"{meta['ko']} {ref.chapter}장은 {vc}절까지 — '{ref.raw}'의 {a}-{b}절은 범위 밖")
        elif a < 1:
            problems.append(f"절 번호는 1 이상이어야 함: '{ref.raw}'")
    return problems


# ── 인용 대조 (정규화·포함 점수) ──────────────────────────────────────────────

_NORM_RE = re.compile(r"[^가-힣a-zA-Z0-9]")


def normalize_ko(text: str) -> str:
    """공백·문장부호 제거 — 인용 대조용 정규화."""
    return _NORM_RE.sub("", text)


def containment(quote_norm: str, window_norm: str, min_block: int = 3) -> tuple[float, int]:
    """quote가 window 안에 어느 정도 '담겨' 있는지 → (점수 0~1, 매칭 블록 수).

    SequenceMatcher 매칭 블록 중 min_block 이상 길이의 합 / len(quote).
    quote ⊂ window 면 window가 길어도 1.0에 수렴한다(부분 인용 허용).
    블록 수 > 1 이면 인용 내부에 생략/변형 구간이 있다는 뜻(중략 신호).
    """
    if not quote_norm:
        return 0.0, 0
    sm = difflib.SequenceMatcher(None, quote_norm, window_norm, autojunk=False)
    blocks = [bl for bl in sm.get_matching_blocks() if bl.size >= min_block]
    matched = sum(bl.size for bl in blocks)
    return min(1.0, matched / len(quote_norm)), len(blocks)


def best_verse_match(quote: str, tr: Translation, search_chapters: list[tuple[int, int]],
                     max_window: int = 3) -> dict | None:
    """quote를 후보 장들의 1~max_window 연속 절 윈도우와 대조해 최고 매치 반환.

    search_chapters: [(book_n, chapter), ...]
    반환: {"score","ref","book_n","chapter","v1","v2","verse_text"} 또는 None.
    """
    qn = normalize_ko(quote)
    if not qn:
        return None
    best: dict | None = None
    for bn, ch in search_chapters:
        vc = tr.verse_count(bn, ch)
        if vc == 0:
            continue
        texts = {v: tr.verse_text(bn, ch, v) or "" for v in range(1, vc + 1)}
        norms = {v: normalize_ko(t) for v, t in texts.items()}
        for v1 in range(1, vc + 1):
            window = ""
            for w in range(max_window):
                v2 = v1 + w
                if v2 > vc:
                    break
                window += norms[v2]
                if len(window) < max(4, int(len(qn) * 0.5)):
                    continue
                score, nblocks = containment(qn, window)
                better = best is None or score > best["_raw"] + 1e-9 or (
                    abs(score - best["_raw"]) <= 1e-9
                    and (v2 - v1) < (best["v2"] - best["v1"]))
                if better:
                    ko = tr.book_meta(bn)["ko"]
                    best = {
                        "_raw": score,
                        "score": round(score, 3),
                        "blocks": nblocks,
                        "ref": f"{ko} {ch}:{v1}" + (f"-{v2}" if v2 > v1 else ""),
                        "book_n": bn, "chapter": ch, "v1": v1, "v2": v2,
                        "verse_text": " ".join(texts[v].strip() for v in range(v1, v2 + 1)),
                    }
    if best and best["score"] < 0.3:
        return None  # 사실상 무관 — 오해 소지 있는 best_ref를 내보내지 않는다
    if best:
        best.pop("_raw", None)
    return best
