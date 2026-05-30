#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""query_expand.py — 엔진 언어 라우팅 + (선택적) per-essay 용어 사전 확장 (TAWP)

설계 원칙(사용자 피드백 2026-05-28):
- 정적 신학 glossary는 사실상 대응 불가(per-topic 정밀도 부재 · 어떤 에세이에도 부분 매칭만).
- 다국어 검색은 **per-essay 키워드 세트**(research-mentor 산출 또는 사용자 정의 YAML)가
  검색 *전 단계*에서 생성되어야 한다(메모리: [[tawp-keyword-set-principle]]).
- 본 모듈은 (a) 엔진→언어 라우팅 테이블을 *코드 내 상수*로 유지하고,
  (b) glossary 파일(있을 때만)을 보조 폴백으로 사용하며,
  (c) per-essay 사전 도입 후에는 `expand(text, glossary=per_essay_dict)` 시그니처로 주입한다.

  - import: expand(text, glossary=None) -> {"queries": {ko,en}, "matched": {...}, "engine_routing": {...}}
  - CLI:    python scripts/query_expand.py "본회퍼 비폭력" [--lang en] [--json] [--glossary path.json]

TSPP 검색 언어는 한국어·영어 2종(ko→KCI·NLK / en→Crossref·S2). 독일어(de)는 미사용.
"""
import argparse
import json
import os
import re
import sys

# 엔진→언어 라우팅(코드 내장; glossary 파일 없어도 라우팅은 동작).
# per-essay 사전이나 외부 glossary로 override 가능.
DEFAULT_ENGINE_ROUTING = {
    "ko": ["kci-api-searcher", "nlk-ejournal-searcher"],
    "en": ["crossref-journal-searcher", "semantic-scholar"],
}

_GLOSSARY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "theology_glossary.json")


def load_glossary(path: str = _GLOSSARY_PATH) -> dict:
    """glossary 파일이 있으면 로드하고, 없거나 비어 있으면 라우팅만 채운 빈 사전 반환.
    per-essay 사전을 주입할 때는 호출자가 직접 dict를 만들어 expand(text, glossary=...)로 넘긴다."""
    if not os.path.exists(path):
        return {"terms": {}, "engine_routing": DEFAULT_ENGINE_ROUTING}
    g = json.load(open(path, encoding="utf-8"))
    g.setdefault("engine_routing", DEFAULT_ENGINE_ROUTING)
    return g


def expand(text: str, glossary: dict | None = None) -> dict:
    g = glossary or load_glossary()
    terms = g.get("terms", {})
    clean = re.sub(r'\[\^[^\]]+\]', ' ', text or '').strip()
    # 긴 용어부터 매칭(부분 겹침 방지)
    matched = []
    for ko in sorted(terms, key=len, reverse=True):
        if ko in clean:
            matched.append(ko)
    # 토큰 단위 dedup: 서로 다른 한국어 키가 동일 영/독 토큰을 산출하면(예: '언약'·'새 언약'→'Bund' 중복)
    # 합쳐진 쿼리의 노이즈 토큰이 늘어나 엔진이 0건을 반환할 수 있다. 단어 단위로 한 번 더 정규화한다.
    def _join_dedup(values):
        seen, out = set(), []
        for v in values:
            for tok in v.split():
                low = tok.lower()
                if low and low not in seen:
                    seen.add(low); out.append(tok)
        return " ".join(out)

    en_terms = [terms[k].get("en", "") for k in matched if terms[k].get("en")]
    return {
        "input": clean[:120],
        "matched": {k: terms[k] for k in matched},
        "queries": {
            "ko": clean,
            "en": _join_dedup(en_terms),
        },
        "engine_routing": g.get("engine_routing", {}),
    }


def best_query_for_engine(text: str, engine: str, glossary: dict | None = None) -> tuple[str, str]:
    """엔진명에 맞는 (언어, 쿼리)를 반환. 라우팅 표로 엔진→언어를 역추적."""
    g = glossary or load_glossary()
    exp = expand(text, g)
    routing = g.get("engine_routing", {})
    # 한 엔진이 여러 언어 목록에 있으면 먼저 등재된 언어를 우선(en이 de보다 앞).
    lang_of = {}
    for lang, engines in routing.items():
        for e in engines:
            lang_of.setdefault(e, lang)
    lang = lang_of.get(engine, "en")
    # 해당 언어 쿼리가 비어 있으면 en→ko 순으로 폴백
    q = exp["queries"].get(lang) or exp["queries"].get("en") or exp["queries"]["ko"]
    return lang, q


def main():
    ap = argparse.ArgumentParser(description="TAWP 다국어 질의 확장")
    ap.add_argument("text", help="확장할 질의/주장 텍스트")
    ap.add_argument("--lang", choices=["ko", "en"], help="특정 언어 쿼리만 출력")
    ap.add_argument("--json", action="store_true", help="전체 결과 JSON 출력")
    args = ap.parse_args()
    exp = expand(args.text)
    if args.json:
        print(json.dumps(exp, ensure_ascii=False, indent=2))
    elif args.lang:
        print(exp["queries"].get(args.lang, ""))
    else:
        print(f"입력: {exp['input']}")
        print(f"매칭 용어: {list(exp['matched'])}")
        for lang in ("ko", "en"):
            q = exp["queries"][lang]
            engs = exp["engine_routing"].get(lang, [])
            print(f"  [{lang}] '{q}'  → 엔진 {engs}")


if __name__ == "__main__":
    main()
