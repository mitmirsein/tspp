#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""research_fanout.py — 병렬 리서치 오케스트레이터 (TAWP, 개선1)

여러 검색 스킬(KCI·NLK·Semantic Scholar·Crossref·IxTheo)을 동시에 fan-out 실행하고,
결과를 evidence_collect.py로 단일 EvidencePack 후보로 병합한다.

설계 원칙:
- 레코드 정규화·dedup·EvidencePack 생성은 evidence_collect.py에 위임한다(중복 구현 금지).
- 엔진별 호출 규약 차이(positional vs -q, --output vs --format)는 ADAPTERS 테이블이 흡수한다.
- 스킬 경로·격리 여부는 skills/registry.json(단일 진실 소스)에서 읽는다.
- 부분 실패는 degraded mode — 스킵 사유를 남기고 전체를 멈추지 않는다(헌법 규약).
- 키 요구 엔진(KCI·NLK)은 셸 환경변수(dev/.env export)에 키가 없으면 스킵으로 강등한다.
- 누락 최소화: 기본 실행은 **순차**(동시성 contention·rate-limit 충돌 제거) + **엔진별 재시도**
  (--retries, 지수 백오프). 속도 우선 동시 fan-out은 --parallel로 전환한다.
- 핵심 엔진은 --require-engines로 커버리지 하드 게이트(키 외 누락 시 exit 2)를 건다.

사용:
  # 기본: 순차 + 재시도 2회(누락 최소화)
  python scripts/research_fanout.py "테오시스 신화 구원론" \
      --limit 10 --out output/EvidencePack.json [--expand] [--retries 2]
  # 속도 우선 병렬 + 핵심 엔진 하드 게이트
  python scripts/research_fanout.py "..." --parallel --max-workers 6 \
      --require-engines kci-api-searcher,semantic-scholar,crossref-journal-searcher
  python scripts/research_fanout.py "..." --engines semantic-scholar,crossref-journal-searcher
"""
import argparse
import concurrent.futures
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

def _load_dotenv():
    """간이 .env 로더 — python-dotenv 미사용. 기존 환경변수는 덮어쓰지 않음."""
    p = os.path.join(_ROOT, ".env")
    if not os.path.exists(p):
        return
    try:
        with open(p, encoding="utf-8") as f:
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

sys.path.insert(0, _HERE)
try:
    from query_expand import best_query_for_engine, DEFAULT_ENGINE_ROUTING
except Exception:
    best_query_for_engine = None
    DEFAULT_ENGINE_ROUTING = {
        "ko": ["kci-api-searcher", "nlk-ejournal-searcher"],
        "en": ["crossref-journal-searcher", "semantic-scholar"],
    }

REGISTRY = os.path.join(_ROOT, "skills", "registry.json")


def _engine_lang(engine: str) -> str:
    """엔진→1차 언어(ko/en) 결정. TSPP는 IxTheo 제외로 de 검색 경로 없음 — ko/en 2언어."""
    for lang, engines in DEFAULT_ENGINE_ROUTING.items():
        if engine in engines:
            return lang
    return "en"


def load_keywords(path: str) -> dict:
    """키워드 세트 로드 → {"ko":[...], "en":[...]} (TSPP 검색 언어 2종: 한국어·영어).
    지원 위치(우선순위): (1) top-level "keywords"(per-essay 사전),
    (2) meditation_seed의 "evidence.keywords_used"(sermon-mentor 산출).
    파일 없거나 ko·en 모두 비면 빈 dict 반환 → fan-out이 base_q로 폴백."""
    if not path or not os.path.exists(path):
        return {}
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"[⚠️ warning] keywords-file 로딩 실패({path}): {e}", file=sys.stderr)
        return {}
    kw = data.get("keywords")
    if not isinstance(kw, dict):
        kw = (data.get("evidence") or {}).get("keywords_used") or {}
    out = {lang: list(kw.get(lang, [])) for lang in ("ko", "en")}
    return out if (out["ko"] or out["en"]) else {}

# 엔진 어댑터: 레지스트리 스킬명 → (argv 빌더(query, limit), 키 환경변수 or None)
#   argv 빌더는 엔트리 스크립트 *뒤에* 붙는 검색 인자 리스트를 만든다.
ADAPTERS = {
    "kci-api-searcher":          (lambda q, l: [q, "--limit", str(l), "--output", "json"], "KCI_OPEN_API_KEY"),
    "nlk-ejournal-searcher":     (lambda q, l: [q, "--limit", str(l), "--output", "json"], "NLK_DATA_GO_KR_KEY"),
    "semantic-scholar":          (lambda q, l: ["-q", q, "-l", str(l), "--format", "json"], None),
    "crossref-journal-searcher": (lambda q, l: ["-q", q, "-l", str(l), "--format", "json"], None),
}
DEFAULT_ENGINES = list(ADAPTERS.keys())

# 엔진별 타임아웃 오버라이드(초). cold uv 환경 부팅·브라우저 스크레이프가 있는
# 격리/브라우저 엔진은 --timeout 기본값으로 부족하기 쉬워 더 넉넉히 준다.
# 미등재 엔진은 --timeout 기본값을 그대로 사용한다.
ENGINE_TIMEOUT = {
    "kci-api-searcher": 180,
    "nlk-ejournal-searcher": 60,
}


def _engine_timeout(engine: str, default_timeout: int) -> int:
    return ENGINE_TIMEOUT.get(engine, default_timeout)


# 엔진별 키워드당 결과 수 오버라이드(키워드별 개별 검색 모드). --per-keyword-limit가
# 전역 기본이고, 여기 등재된 엔진은 이 값으로 덮는다. 토큰·중복 특성에 맞춘 양 조절:
#   - 한국어(KCI·NLK전자저널)는 상호 중복 0% → 합산 시 dedup으로 안 줄어 결과가 그대로
#     누적된다. 보수적으로 작게 잡아 한국어 쏠림·토큰 폭증을 막는다.
#   - 영어(S2·Crossref)는 DOI 중복이 잦아 dedup 여지가 있어 약간 넉넉히 받는다.
# CLI --per-keyword-limit-<engine> 로 개별 덮어쓸 수 있다(없으면 이 표 → 전역값 순).
ENGINE_PER_KEYWORD = {
    "kci-api-searcher": 2,
    "nlk-ejournal-searcher": 2,
    "semantic-scholar": 3,
    "crossref-journal-searcher": 3,
}


def _engine_per_keyword(engine: str, default_limit: int, overrides: dict | None = None) -> int:
    if overrides and engine in overrides:
        return overrides[engine]
    return ENGINE_PER_KEYWORD.get(engine, default_limit)


def load_registry() -> dict:
    try:
        return json.load(open(REGISTRY, encoding="utf-8")).get("skills", {})
    except Exception as e:
        print(f"[!] registry.json 로드 실패: {e}", file=sys.stderr)
        return {}


def engine_query(base_q: str, engine: str, expand: bool, keywords_map: dict | None = None):
    """엔진별 (쿼리, 언어) 결정 — 우선순위: keywords_map(per-essay) > expand(query_expand) > base_q.
    keywords_map이 있으면 엔진의 1차 언어에 해당하는 키워드 리스트를 공백 결합해 쿼리로 사용한다."""
    if keywords_map:
        lang = _engine_lang(engine)
        toks = keywords_map.get(lang) or keywords_map.get("ko") or []
        if toks:
            return " ".join(toks), lang
    if expand and best_query_for_engine:
        try:
            lang, q = best_query_for_engine(base_q, engine)
            return (q or base_q), (lang or "-")
        except Exception:
            pass
    return base_q, "-"


def _count(payload) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for k in ("results", "records", "data", "items", "hits", "docs"):
            v = payload.get(k)
            if isinstance(v, list):
                return len(v)
    return 0


def _attempt(cmd, cwd, timeout, lang, q):
    """단일 subprocess 시도 → (payload_or_None, note, retriable).
    retriable=True인 실패(타임아웃·rate-limit·빈 출력·파싱 실패 등)는 재시도 대상."""
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return (None, f"타임아웃({timeout}s) [{lang}] q='{q}'", True)
    except FileNotFoundError:
        return (None, "실행 실패: uv 미설치/경로 없음", False)
    except Exception as e:
        return (None, f"실행 실패: {e}", False)
    dt = round(time.time() - t0, 1)

    out = (r.stdout or "").strip()
    if r.returncode != 0 and not out:
        tail = (r.stderr or "").strip().splitlines()
        return (None, f"비정상 종료(rc={r.returncode}, {dt}s): {tail[-1] if tail else ''}", True)
    if not out:
        return (None, f"빈 출력({dt}s)", True)

    payload = None
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        for ch in ("[", "{"):  # 검색기가 JSON 앞에 로그를 흘릴 경우 첫 구분자부터 재시도
            i = out.find(ch)
            if i >= 0:
                try:
                    payload = json.loads(out[i:])
                    break
                except json.JSONDecodeError:
                    payload = None
    if payload is None:
        return (None, f"JSON 파싱 실패({dt}s)", True)
    if isinstance(payload, dict) and "error" in payload and _count(payload) == 0:
        return (None, f"검색기 오류({dt}s): {str(payload.get('error'))[:80]}", True)
    return (payload, f"OK {_count(payload)}건 ({dt}s) [{lang}] q='{q}'", False)


def _records(payload) -> list:
    """payload(list/dict)에서 레코드 dict 리스트를 추출(키워드별 결과 합산용)."""
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for k in ("results", "records", "data", "items", "hits", "docs"):
            v = payload.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


def engine_keywords(engine: str, keywords_map: dict | None):
    """keywords_map에서 엔진 1차 언어의 키워드 리스트를 반환 → (toks, lang).
    keywords_map이 없거나 해당 언어 키워드가 없으면 None(단일 base_q 모드로 폴백)."""
    if not keywords_map:
        return None
    lang = _engine_lang(engine)
    toks = keywords_map.get(lang) or keywords_map.get("ko") or []
    return (toks, lang) if toks else None


def _make_cmd(meta: dict, entry: str, builder, q: str, lim: int):
    """엔진 호출 argv + cwd 구성(uv_isolated 여부 흡수)."""
    if meta.get("uv_isolated", False):
        skill_path = os.path.join(_ROOT, meta["path"])
        rel = os.path.relpath(os.path.join(_ROOT, entry), skill_path)
        return ["uv", "run", "python", rel] + builder(q, lim), skill_path
    return [sys.executable, entry] + builder(q, lim), _ROOT


def _search_with_retry(cmd, cwd, eng_timeout, lang, q, retries):
    """단일 쿼리 검색 + 지수 백오프 재시도 → (payload_or_None, note)."""
    last = ""
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(min(2 ** attempt, 15) + random.uniform(0, 1))
        payload, note, retriable = _attempt(cmd, cwd, eng_timeout, lang, q)
        suffix = f" (재시도 {attempt}/{retries})" if attempt else ""
        if payload is not None:
            return payload, note + suffix
        last = note + suffix
        if not retriable:
            break
    return None, last


def run_engine(engine, reg, base_q, limit, expand, timeout, keywords_map=None,
               retries=0, per_keyword_limit=3, pk_overrides=None):
    """단일 엔진 실행 → (engine, payload_or_None, note, status).

    keywords_map에 엔진 언어 키워드가 있으면 **키워드별 개별 검색 후 합산**한다
    (AND 결합이 0건을 유발하던 문제 해소; 중복은 evidence_collect가 dedup).
    없으면 단일 base_q 검색(기존 동작).

    status ∈ {ok, empty, skip_key, fail, unsupported}
    """
    if engine not in ADAPTERS:
        return (engine, None, "어댑터 없음(미지원 엔진)", "unsupported")
    meta = reg.get(engine, {})
    entry = meta.get("entry_script", "")
    if not entry:
        return (engine, None, "entry_script 없음(레지스트리)", "unsupported")
    builder, key_env = ADAPTERS[engine]
    if key_env and not os.environ.get(key_env):
        return (engine, None, f"스킵: {key_env} 미설정 → degraded(키 없는 엔진으로 진행)", "skip_key")
    eng_timeout = _engine_timeout(engine, timeout)
    kw = engine_keywords(engine, keywords_map)

    # ── 단일 쿼리 모드(키워드맵 없음) — 기존 동작 ──────────────────────────
    if kw is None:
        q, lang = engine_query(base_q, engine, expand, keywords_map)
        cmd, cwd = _make_cmd(meta, entry, builder, q, limit)
        payload, note = _search_with_retry(cmd, cwd, eng_timeout, lang, q, retries)
        if payload is None:
            return (engine, None, note, "fail")
        return (engine, payload, note, "ok" if _count(payload) else "empty")

    # ── 키워드별 개별 검색 모드 (a) — 각 키워드를 키워드당 리미트로 검색·합산 ──
    # 리미트는 엔진별 오버라이드(ENGINE_PER_KEYWORD) → CLI overrides → 전역 순으로 결정.
    # 한국어(KCI·전자저널)는 상호 중복 0%라 작게(2), 영어는 dedup 여지로 넉넉히(3).
    toks, lang = kw
    pk_limit = _engine_per_keyword(engine, per_keyword_limit, pk_overrides)
    merged, notes, n_ok, n_fail = [], [], 0, 0
    for t in toks:
        cmd, cwd = _make_cmd(meta, entry, builder, t, pk_limit)
        payload, _note = _search_with_retry(cmd, cwd, eng_timeout, lang, t, retries)
        if payload is None:
            n_fail += 1
            notes.append(f"✗{t}")
        else:
            recs = _records(payload)
            merged.extend(recs)
            n_ok += 1
            notes.append(f"{t}={len(recs)}")
    summary = f"[{lang}] {len(toks)}키워드×{pk_limit}→{len(merged)}건 ({'; '.join(notes)})"
    if not merged:
        # 전부 실패(검색 자체 실패)면 fail, 검색은 됐으나 0건이면 empty
        return (engine, None, summary, "fail") if (n_fail and not n_ok) else (engine, [], summary, "empty")
    return (engine, merged, summary, "ok")


def main():
    ap = argparse.ArgumentParser(description="TAWP 병렬 리서치 오케스트레이터(fan-out)")
    ap.add_argument("query")
    ap.add_argument("--engines", default=",".join(DEFAULT_ENGINES),
                    help=f"쉼표구분 엔진(기본 전체: {','.join(DEFAULT_ENGINES)})")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--out", default="output/EvidencePack.json")
    ap.add_argument("--raw-dir", default="output/.raw")
    ap.add_argument("--expand", action="store_true", help="query_expand로 엔진별 ko/en 라우팅(per-essay 사전이 1차이며 이 옵션은 보조)")
    ap.add_argument("--keywords-file", default=None,
                    help="키워드 JSON 경로. top-level keywords.{ko,en} 또는 meditation_seed의 evidence.keywords_used.{ko,en}를 "
                         "엔진 언어로 라우팅(ko→KCI·NLK / en→Crossref·S2). --expand보다 우선.")
    ap.add_argument("--timeout", type=int, default=120,
                    help="엔진별 타임아웃 초 기본값(기본 120). 격리/브라우저 엔진은 ENGINE_TIMEOUT로 더 길게 오버라이드.")
    ap.add_argument("--parallel", action="store_true",
                    help="엔진을 동시 fan-out(--max-workers)으로 실행. 기본은 순차(누락 최소화) 실행이며 "
                         "이 플래그로 속도 우선 병렬로 전환한다.")
    ap.add_argument("--retries", type=int, default=2,
                    help="엔진별 일시 실패(타임아웃·rate-limit·파싱 실패) 재시도 횟수(기본 2, 지수 백오프).")
    ap.add_argument("--per-keyword-limit", type=int, default=3,
                    help="키워드별 개별 검색 모드(--keywords-file)에서 키워드당 결과 수(전역 기본 3). "
                         "각 키워드를 따로 검색해 합산·dedup하므로 AND 결합 0건 문제를 피한다. "
                         "엔진별 기본은 ENGINE_PER_KEYWORD(한국어 2·영어 3)가 우선.")
    ap.add_argument("--per-keyword-limit-engine", action="append", default=[], metavar="ENGINE=N",
                    help="특정 엔진의 키워드당 결과 수 덮어쓰기(반복 가능). 예: "
                         "--per-keyword-limit-engine nlk-ejournal-searcher=1")
    ap.add_argument("--require-engines", default=None,
                    help="쉼표구분 핵심 엔진 목록. 키 외 사유로 누락(fail/unsupported/미실행)되면 exit 2로 차단(커버리지 하드 게이트). "
                         "키 미설정 스킵·0건은 게이트 통과(정당한 degraded·검색 수행됨).")
    ap.add_argument("--max-workers", type=int, default=6)
    ap.add_argument("--report", help="fan-out 로그 마크다운 경로")
    args = ap.parse_args()

    reg = load_registry()
    engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    raw_dir = os.path.join(_ROOT, args.raw_dir)
    os.makedirs(raw_dir, exist_ok=True)

    keywords_map = load_keywords(args.keywords_file) if args.keywords_file else None
    if keywords_map:
        print(f"📚 키워드 라우팅 적용: ko {len(keywords_map.get('ko',[]))}(→KCI·NLK) | en {len(keywords_map.get('en',[]))}(→Crossref·S2)")

    # 엔진별 키워드당 리미트 오버라이드 파싱(ENGINE=N)
    pk_overrides = {}
    for spec in args.per_keyword_limit_engine:
        if "=" in spec:
            e, _, n = spec.partition("=")
            if n.strip().isdigit():
                pk_overrides[e.strip()] = int(n)

    results, notes, status = {}, {}, {}

    def _collect(res):
        engine, payload, note, st = res
        notes[engine] = note
        status[engine] = st
        if payload is not None:
            results[engine] = payload

    run_args = (reg, args.query, args.limit, args.expand, args.timeout, keywords_map,
                args.retries, args.per_keyword_limit, pk_overrides)
    if args.parallel:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as ex:
            futs = {ex.submit(run_engine, e, *run_args): e for e in engines}
            for fut in concurrent.futures.as_completed(futs):
                _collect(fut.result())
    else:
        # 순차 실행: 동시성 contention·rate-limit 충돌·격리 환경 동시 부팅을 제거해 누락을 최소화.
        for e in engines:
            _collect(run_engine(e, *run_args))

    # raw 저장 + evidence_collect 입력 구성(상대경로 — 콜론 충돌 방지)
    inputs = []
    for engine, payload in results.items():
        rp = os.path.join(args.raw_dir, f"{engine}.json")
        json.dump(payload, open(os.path.join(_ROOT, rp), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        inputs.append(f"{engine}:{rp}")

    merged = None
    if inputs:
        cmd = [sys.executable, os.path.join(_HERE, "evidence_collect.py"), "merge", "--out", args.out]
        for i in inputs:
            cmd += ["--input", i]
        mc = subprocess.run(cmd, cwd=_ROOT, capture_output=True, text=True)
        merged = (mc.stdout or "").strip() or (mc.stderr or "").strip()

    # 상태 분류: 검색됨(ok) / 0건(empty, 누락 후보) / 키스킵(정당 degraded) / 실패 / 미지원
    _ICON = {"ok": "✅", "empty": "🟡", "skip_key": "⏭️", "fail": "❌", "unsupported": "🚫"}
    ok = [e for e in engines if status.get(e) == "ok"]
    empty = [e for e in engines if status.get(e) == "empty"]
    skip_key = [e for e in engines if status.get(e) == "skip_key"]
    failed = [e for e in engines if status.get(e) in ("fail", "unsupported")]
    mode = "병렬" if args.parallel else "순차"
    print(f"🔱 research_fanout({mode}, retries={args.retries}): "
          f"검색 {len(ok)} | 0건 {len(empty)} | 키스킵 {len(skip_key)} | 실패 {len(failed)} / 총 {len(engines)} → {args.out}")
    for e in engines:
        print(f"  {_ICON.get(status.get(e), '⏭️')} {e}: {notes.get(e, '')}")
    if merged:
        print("  " + merged.replace("\n", "\n  "))
    if empty:
        print(f"  🟡 0건(검색은 됨 — 쿼리/키워드 점검 권장): {empty}", file=sys.stderr)
    if failed:
        print(f"  ❌ 실패(키 외 사유 — 재시도 {args.retries}회 후에도 미수집): {failed}", file=sys.stderr)

    # 핵심 엔진 커버리지 하드 게이트: 키 외 사유 누락(fail/unsupported/미실행)만 차단.
    require = [e.strip() for e in (args.require_engines or "").split(",") if e.strip()]
    missing_required = [e for e in require if status.get(e) not in ("ok", "empty", "skip_key")]

    if args.report:
        lines = ["# 🔱 Research Fan-out 로그", "",
                 f"- 질의: `{args.query}` | 모드 {mode} | retries {args.retries} | 엔진 {len(engines)}",
                 f"- 검색 {len(ok)} · 0건 {len(empty)} · 키스킵 {len(skip_key)} · 실패 {len(failed)}",
                 f"- 시각: {datetime.now(timezone.utc).isoformat()}", "",
                 "## 엔진별 결과",
                 *[f"- {_ICON.get(status.get(e), '⏭️')} **{e}**: {notes.get(e, '')}" for e in engines],
                 "", "## 병합", f"- 출력: `{args.out}`", f"- {merged or '(병합 없음 — 수집 0)'}"]
        if require:
            lines += ["", "## 커버리지 게이트",
                      f"- require-engines: {require}",
                      f"- 미충족(키 외 누락): {missing_required or '없음 — 통과'}"]
        open(os.path.join(_ROOT, args.report), "w", encoding="utf-8").write("\n".join(lines))
        print(f"💾 로그: {args.report}")

    if not inputs:
        print("   ▶ 수집 0 — 모든 엔진 degraded. 네트워크/키/엔진 상태 점검.", file=sys.stderr)
        sys.exit(2)

    if missing_required:
        print(f"   ⛔ require-engines 미충족(키 외 사유 누락): {missing_required} "
              f"— 커버리지 하드 게이트 실패(exit 2). --retries 상향·개별 엔진 점검 후 재실행.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
