#!/usr/bin/env python3
"""voice_ingest.py — 설교문 샘플에서 *객관 문체 신호*를 계량한다 (TSPP §4-5 (4)).

이 스크립트는 보이스를 '지어내지' 않는다. 측정만 한다.
산출 voice_signals.json 은 LLM 프로파일링(skills/voice-ingest)의 *근거*이며,
설교자 보이스 카드(preacher_voice.json)의 모든 주장은 이 측정값 + 실제 샘플
인용에 정착되어야 한다 (TSPP 제1원칙: LLM 일반론 금지 — 그 보이스판).

- 순수 stdlib (외부 패키지 0 — MS_Dev 패키지 가드레일 준수).
- 한국어 강단 화법 인식 (구어체 종결·청중 호명·권면·성구 인용).
- 프라이버시: 샘플은 사용자 자산. 로컬에서만 처리하고 외부로 보내지 않는다.

사용:
    python scripts/voice_ingest.py --samples input/sermon_samples/ \
        --out output/<run>/voice_signals.json
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

# ── 권장 샘플 수 (CONCEPT F11) ─────────────────────────────────────────────
MIN_SAMPLES = 3          # 미만이면 부분 폴백 신호
RECOMMENDED_SAMPLES = 5  # 5~10편 권장

# ── 한국어 기능어(어절) — 어휘대 상위 빈도에서 잡음 제거용 (보수적 목록) ──────
STOPWORDS = {
    "그리고", "그러나", "그런데", "그래서", "그러면", "그러므로", "그러니까",
    "이것은", "그것은", "이것이", "그것이", "이는", "그는", "저는", "우리는",
    "우리가", "우리의", "우리에게", "이런", "그런", "저런", "이렇게", "그렇게",
    "있는", "없는", "하는", "되는", "같은", "또한", "역시", "바로", "지금",
    "오늘", "다시", "정말", "아주", "매우", "너무", "더욱", "가장", "모든",
    "여기서", "거기서", "이때", "그때", "때문에", "위해", "대해", "통해",
    "하나님", "예수님", "주님",  # 신학 고빈도 — 별도 신학강조 신호로 따로 셈
}

# ── 성구 인용 탐지 ─────────────────────────────────────────────────────────
# "마 5:3", "마태복음 9장", "눅 17:1-6", "요 24:18-21", "N장 N절" 등
_BOOK_ABBR = (
    r"창|출|레|민|신|수|삿|룻|삼상|삼하|왕상|왕하|대상|대하|스|느|에|욥|시|잠|"
    r"전|아|사|렘|애|겔|단|호|욜|암|옵|욘|미|나|합|습|학|슥|말|"
    r"마|막|눅|요|행|롬|고전|고후|갈|엡|빌|골|살전|살후|딤전|딤후|딛|몬|히|"
    r"약|벧전|벧후|요일|요이|요삼|유|계"
)
RE_REF_COLON = re.compile(rf"(?:{_BOOK_ABBR}|[가-힣]{{2,4}}복음|[가-힣]{{2,4}}서)\s?\d+:\d+(?:-\d+)?")
RE_REF_JANG = re.compile(r"\d+\s?장(?:\s?\d+\s?절(?:[-~]\d+절?)?)?")

# ── 구어체 종결 / 강단 화법 표지 ──────────────────────────────────────────
RE_SENT_SPLIT = re.compile(r"[.!?…。！？]+|\n{2,}")
RE_QUESTION = re.compile(r"(?:까\?|까$|니까|ㄴ가요|는가요|나요|을까|ㄹ까|습니까|입니까|\?)")
ADDRESS_MARKERS = ["여러분", "형제자매", "성도 여러분", "성도님", "사랑하는",
                   "교우 여러분", "여러분께", "여러분의"]
EXHORT_MARKERS = ["합시다", "하십시다", "하십시오", "하시기 바랍니다", "바랍니다",
                  "해야 합니다", "해야 할", "합시오", "하자", "해보시기"]
PRAYER_MARKERS = ["아멘", "기도합니다", "기도하십시다", "기도하시다", "축복",
                  "주님,", "주여", "하나님 아버지"]
# 종결어미 레지스터: 격식 구어(설교체) vs 문어 평서
RE_END_HAPNIDA = re.compile(r"(?:습니다|ㅂ니다|입니다|십니다|됩니다|합니다)[.!?\"'”’)\s]*$")
RE_END_YO = re.compile(r"요[.!?\"'”’)\s]*$")
RE_END_DA = re.compile(r"(?<!니)다[.!?\"'”’)\s]*$")  # '~다.' 문어체 (습니다 제외)


def strip_markup(text: str) -> str:
    """YAML frontmatter·마크다운 마크업을 제거해 *발화 텍스트*만 남긴다."""
    # frontmatter
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:]
    lines = []
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("#"):           # heading
            s = s.lstrip("#").strip()
        s = re.sub(r"[*_`>]", "", s)     # bold/italic/code/quote
        s = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", s)  # links/images
        lines.append(s)
    return "\n".join(lines)


def split_sentences(text: str) -> list[str]:
    raw = RE_SENT_SPLIT.split(text)
    return [s.strip() for s in raw if s and len(s.strip()) > 1]


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]


def tokenize(text: str) -> list[str]:
    """공백 기반 어절 토큰 (형태소 분석 없음 — 의존성 0 유지).
    구두점을 떼고 한글/영문/숫자 어절만 남긴다."""
    toks = re.findall(r"[가-힣A-Za-z]+", text)
    return [t for t in toks if len(t) >= 2]


def analyze_one(name: str, raw_text: str) -> dict:
    text = strip_markup(raw_text)
    sents = split_sentences(text)
    paras = split_paragraphs(text)
    n_sent = len(sents)
    n_sent = n_sent or 1
    lengths = [len(s) for s in sents]

    questions = sum(1 for s in sents if RE_QUESTION.search(s))
    exclam = raw_text.count("!")
    addr = sum(text.count(m) for m in ADDRESS_MARKERS)
    exhort = sum(text.count(m) for m in EXHORT_MARKERS)
    prayer = sum(text.count(m) for m in PRAYER_MARKERS)

    refs_colon = RE_REF_COLON.findall(text)
    refs_jang = RE_REF_JANG.findall(text)
    n_refs = len(refs_colon) + len(refs_jang)

    # 종결 레지스터 (각 문장 끝)
    end_hap = sum(1 for s in sents if RE_END_HAPNIDA.search(s))
    end_yo = sum(1 for s in sents if RE_END_YO.search(s))
    end_da = sum(1 for s in sents if RE_END_DA.search(s))

    # 신학 고빈도어 (어휘대의 무게중심 후보)
    theo = {k: text.count(k) for k in ("하나님", "예수", "주님", "은혜", "십자가",
            "믿음", "복음", "사랑", "회개", "용서", "구원", "성령", "말씀", "기도",
            "언약", "거룩", "죄", "심판", "부활", "소망")}
    theo = {k: v for k, v in theo.items() if v > 0}

    return {
        "sample": name,
        "char_count": len(text),
        "paragraph_count": len(paras),
        "sentence_count": len(sents),
        "cadence": {
            "mean_sentence_chars": round(statistics.mean(lengths), 1) if lengths else 0,
            "median_sentence_chars": round(statistics.median(lengths), 1) if lengths else 0,
            "stdev_sentence_chars": round(statistics.pstdev(lengths), 1) if len(lengths) > 1 else 0,
            "short_ratio": round(sum(1 for l in lengths if l < 25) / n_sent, 3),   # 짧은 단언
            "long_ratio": round(sum(1 for l in lengths if l > 80) / n_sent, 3),    # 긴 전개
            "sentences_per_paragraph": round(len(sents) / (len(paras) or 1), 1),
        },
        "rhetoric": {
            "question_ratio": round(questions / n_sent, 3),
            "question_count": questions,
            "exclamation_count": exclam,
            "address_count": addr,                # 청중 호명 (여러분 등)
            "exhortation_count": exhort,          # 권면 (~합시다 등)
            "prayer_marker_count": prayer,        # 기도·아멘
            "scripture_ref_count": n_refs,
            "scripture_ref_density": round(n_refs / (len(text) / 1000 or 1), 2),  # 1000자당
            "scripture_ref_samples": (refs_colon + refs_jang)[:8],
        },
        "register": {                              # 종결어미 분포 (구어 vs 문어)
            "ends_hapnida": end_hap,               # ~습니다/~ㅂ니다 (격식 구어 강단체)
            "ends_yo": end_yo,                     # ~요 (친근 구어)
            "ends_da": end_da,                     # ~다 (문어 평서)
            "hapnida_ratio": round(end_hap / n_sent, 3),
        },
        "theology_emphasis": dict(sorted(theo.items(), key=lambda kv: -kv[1])),
    }


def aggregate(per_file: list[dict]) -> dict:
    if not per_file:
        return {}
    def avg(path):
        vals = []
        for f in per_file:
            d = f
            for k in path:
                d = d[k]
            vals.append(d)
        return round(statistics.mean(vals), 3)

    # 신학 강조 무게중심 (전 샘플 합산)
    theo_total: Counter = Counter()
    for f in per_file:
        theo_total.update(f["theology_emphasis"])

    return {
        "n_samples": len(per_file),
        "total_chars": sum(f["char_count"] for f in per_file),
        "cadence": {
            "mean_sentence_chars": avg(["cadence", "mean_sentence_chars"]),
            "short_ratio": avg(["cadence", "short_ratio"]),
            "long_ratio": avg(["cadence", "long_ratio"]),
            "sentences_per_paragraph": avg(["cadence", "sentences_per_paragraph"]),
        },
        "rhetoric": {
            "question_ratio": avg(["rhetoric", "question_ratio"]),
            "scripture_ref_density": avg(["rhetoric", "scripture_ref_density"]),
            "address_per_sample": round(statistics.mean(
                [f["rhetoric"]["address_count"] for f in per_file]), 1),
            "exhortation_per_sample": round(statistics.mean(
                [f["rhetoric"]["exhortation_count"] for f in per_file]), 1),
        },
        "register": {
            "hapnida_ratio": avg(["register", "hapnida_ratio"]),
        },
        "theology_emphasis_top": dict(theo_total.most_common(10)),
    }


def cross_sample_phrases(texts: list[str], top: int = 15) -> list[dict]:
    """여러 샘플에 *반복 등장*하는 3~5어절 구 — 관용구·상투 표현 후보.
    한 샘플에만 나오는 건 제외(설교자 *습관*만 잡기 위해)."""
    if len(texts) < 2:
        return []
    phrase_docs: dict[str, set] = {}
    for i, t in enumerate(texts):
        toks = tokenize(strip_markup(t))
        for n in (3, 4):
            for j in range(len(toks) - n + 1):
                ph = " ".join(toks[j:j + n])
                phrase_docs.setdefault(ph, set()).add(i)
    recurring = [(ph, len(docs)) for ph, docs in phrase_docs.items()
                 if len(docs) >= 2 and not all(w in STOPWORDS for w in ph.split())]
    recurring.sort(key=lambda x: (-x[1], -len(x[0])))
    return [{"phrase": ph, "appears_in_samples": n} for ph, n in recurring[:top]]


def top_lexicon(texts: list[str], top: int = 25) -> list[dict]:
    counter: Counter = Counter()
    for t in texts:
        for tok in tokenize(strip_markup(t)):
            if tok not in STOPWORDS:
                counter[tok] += 1
    return [{"token": w, "count": c} for w, c in counter.most_common(top)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="설교문 샘플 → 객관 문체 신호 (voice_signals.json)")
    ap.add_argument("--samples", required=True,
                    help="설교문 샘플 디렉터리 또는 파일 (.md/.txt)")
    ap.add_argument("--out", required=True, help="산출 voice_signals.json 경로")
    ap.add_argument("--glob", default="*.md,*.txt", help="샘플 확장자 (쉼표 구분)")
    args = ap.parse_args(argv)

    src = Path(args.samples)
    files: list[Path] = []
    if src.is_dir():
        for pat in args.glob.split(","):
            files.extend(sorted(src.glob(pat.strip())))
    elif src.is_file():
        files = [src]
    else:
        print(f"[voice_ingest] 입력을 찾을 수 없음: {src}", file=sys.stderr)
        return 2

    files = [f for f in files if f.is_file()]
    if not files:
        print(f"[voice_ingest] 샘플 0건: {src}", file=sys.stderr)
        return 2

    per_file, texts = [], []
    for f in files:
        try:
            raw = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw = f.read_text(encoding="utf-8", errors="replace")
        texts.append(raw)
        per_file.append(analyze_one(f.name, raw))

    n = len(per_file)
    coverage = "ok" if n >= RECOMMENDED_SAMPLES else (
        "partial" if n >= MIN_SAMPLES else "insufficient")

    result = {
        "schema": "tspp.voice_signals/1",
        "_note": ("객관 측정값일 뿐 보이스 카드가 아니다. preacher_voice.json 의 "
                  "모든 차원은 이 신호 + 실제 샘플 인용에 정착되어야 한다 (LLM 일반론 금지). "
                  "HITL 승인 전까지 확정이 아니다."),
        "coverage": {
            "n_samples": n,
            "status": coverage,           # ok(>=5) / partial(3-4) / insufficient(<3)
            "min_samples": MIN_SAMPLES,
            "recommended_samples": RECOMMENDED_SAMPLES,
            "fallback_note": (
                "샘플 부족 — 채워진 차원만 쓰고 나머지는 호밀레틱 L1 보편 헌장으로 폴백 "
                "(references/homiletic-voice.md)." if coverage != "ok" else
                "권장 샘플 수 충족."),
        },
        "aggregate": aggregate(per_file),
        "lexicon_top": top_lexicon(texts),
        "recurring_phrases": cross_sample_phrases(texts),
        "per_sample": per_file,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[voice_ingest] {n} samples → {out}  (coverage={coverage})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
