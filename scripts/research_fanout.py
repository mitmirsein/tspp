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
sys.path.insert(0, _HERE)
try:
    from query_expand import best_query_for_engine, DEFAULT_ENGINE_ROUTING
except Exception:
    best_query_for_engine = None
    DEFAULT_ENGINE_ROUTING = {
        "ko": ["kci-api-searcher", "nlk-biblio-searcher"],
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
    "nlk-biblio-searcher":       (lambda q, l: [q, "--limit", str(l), "--output", "json"], "NLK_SEARCH_API_KEY"),
    "semantic-scholar":          (lambda q, l: ["-q", q, "-l", str(l), "--format", "json"], None),
    "crossref-journal-searcher": (lambda q, l: ["-q", q, "-l", str(l), "--format", "json"], None),
}
DEFAULT_ENGINES = list(ADAPTERS.keys())

# 엔진별 타임아웃 오버라이드(초). cold uv 환경 부팅·브라우저 스크레이프가 있는
# 격리/브라우저 엔진은 --timeout 기본값으로 부족하기 쉬워 더 넉넉히 준다.
# 미등재 엔진은 --timeout 기본값을 그대로 사용한다.
ENGINE_TIMEOUT = {
    "kci-api-searcher": 180,
    "nlk-biblio-searcher": 180,
}


def _engine_timeout(engine: str, default_timeout: int) -> int:
    return ENGINE_TIMEOUT.get(engine, default_timeout)


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


def run_engine(engine, reg, base_q, limit, expand, timeout, keywords_map=None, retries=0):
    """단일 엔진 실행(재시도 포함) → (engine, payload_or_None, note, status).

    status ∈ {ok, empty, skip_key, fail, unsupported}
      - ok        : payload 수집 + 1건 이상
      - empty     : payload 수집 + 0건(검색은 됨, 누락 후보)
      - skip_key  : 키 환경변수 미설정으로 정당한 degraded(하드 게이트 비대상)
      - fail      : 재시도 후에도 실패(하드 게이트 대상)
      - unsupported : 어댑터/레지스트리 미비
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
    q, lang = engine_query(base_q, engine, expand, keywords_map)
    eng_timeout = _engine_timeout(engine, timeout)

    if meta.get("uv_isolated", False):
        skill_path = os.path.join(_ROOT, meta["path"])
        rel = os.path.relpath(os.path.join(_ROOT, entry), skill_path)
        cmd = ["uv", "run", "python", rel] + builder(q, limit)
        cwd = skill_path
    else:
        cmd = ["uv", "run", "python", entry] + builder(q, limit)
        cwd = _ROOT

    last_note = ""
    for attempt in range(retries + 1):
        if attempt:
            # 지수 백오프 + 지터: rate-limit(429)·일시 네트워크 장애를 흡수한다.
            time.sleep(min(2 ** attempt, 15) + random.uniform(0, 1))
        payload, note, retriable = _attempt(cmd, cwd, eng_timeout, lang, q)
        suffix = f" (재시도 {attempt}/{retries})" if attempt else ""
        if payload is not None:
            return (engine, payload, note + suffix, "ok" if _count(payload) else "empty")
        last_note = note + suffix
        if not retriable:
            break
    return (engine, None, last_note, "fail")


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
    ap.add_argument("--require-engines", default=None,
                    help="쉼표구분 핵심 엔진 목록. 키 외 사유로 누락(fail/unsupported/미실행)되면 exit 2로 차단(커버리지 하드 게이트). "
                         "키 미설정 스킵·0건은 게이트 통과(정당한 degraded·검색 수행됨).")
    ap.add_argument("--max-workers", type=int, default=6)
    ap.add_argument("--report", help="fan-out 로그 마크다운 경로")
    ap.add_argument("--push-zotero", action="store_true",
                    help="병합 완료 후 EvidencePack을 Zotero 라이브러리에 자동 push "
                         "(env ZOTERO_AUTO_PUSH=true와 동일). Zotero 앱 가동 + 식별자 필터 "
                         "+ 라이브러리 중복 차단.")
    ap.add_argument("--no-push-zotero", action="store_true",
                    help="env ZOTERO_AUTO_PUSH=true가 설정되어 있어도 push 비활성.")
    args = ap.parse_args()

    reg = load_registry()
    engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    raw_dir = os.path.join(_ROOT, args.raw_dir)
    os.makedirs(raw_dir, exist_ok=True)

    keywords_map = load_keywords(args.keywords_file) if args.keywords_file else None
    if keywords_map:
        print(f"📚 키워드 라우팅 적용: ko {len(keywords_map.get('ko',[]))}(→KCI·NLK) | en {len(keywords_map.get('en',[]))}(→Crossref·S2)")

    results, notes, status = {}, {}, {}

    def _collect(res):
        engine, payload, note, st = res
        notes[engine] = note
        status[engine] = st
        if payload is not None:
            results[engine] = payload

    run_args = (reg, args.query, args.limit, args.expand, args.timeout, keywords_map, args.retries)
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

    # Zotero 자동 push (opt-in)
    env_push = (os.getenv("ZOTERO_AUTO_PUSH", "").strip().lower() in ("1", "true", "yes", "on"))
    do_push = (args.push_zotero or env_push) and not args.no_push_zotero
    if do_push and os.path.exists(os.path.join(_ROOT, args.out)):
        push_cmd = [sys.executable, os.path.join(_HERE, "zotero_push.py"),
                    os.path.join(_ROOT, args.out)]
        pc = subprocess.run(push_cmd, cwd=_ROOT, capture_output=True, text=True)
        out = (pc.stdout or "").strip()
        err = (pc.stderr or "").strip()
        if out:
            print(out)
        if err:
            print(err, file=sys.stderr)


if __name__ == "__main__":
    main()
