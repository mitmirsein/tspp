# Vendored Components

TSPP는 **공개 단독(self-contained) 레포**다. 런타임에 외부 상류 레포(TAWP·TOS)에 의존하지 않기 위해, 학술 리서치 fan-out 기능을 TAWP에서 **복사(vendoring)**해 TSPP 안에 자체 보유한다.

## 출처

- **상류**: `TAWP` (Theology Academic Writing Pipeline) — 같은 저자(MS_Dev)의 자매 프로젝트
- **vendored 시점**: 2026-05-29

## 복사된 구성요소

| 경로 | 원본(TAWP) | 역할 |
|---|---|---|
| `scripts/research_fanout.py` | `scripts/research_fanout.py` | 병렬 리서치 오케스트레이터 |
| `scripts/evidence_collect.py` | `scripts/evidence_collect.py` | 레코드 정규화·dedup·EvidencePack 생성 |
| `scripts/query_expand.py` | `scripts/query_expand.py` | 엔진별 ko/en 쿼리 라우팅(보조) |
| `skills/registry.json` | `skills/registry.json` | 엔진 레지스트리(단일 진실 소스) — **4엔진으로 축소** |
| `skills/kci-api-searcher/` | 동일 | KCI(한국학술지) OpenAPI 검색 · 키 `KCI_OPEN_API_KEY` |
| `skills/nlk-biblio-searcher/` | 동일 | 국립중앙도서관(NLK) 검색 · 키 `NLK_SEARCH_API_KEY` |
| `skills/semantic-scholar/` | 동일 | Semantic Scholar(영문) 검색 · 키 불요 |
| `skills/crossref-journal-searcher/` | 동일 | Crossref(영문 저널) 검색 · 키 불요 |

## TSPP 적응(원본과의 차이)

공개 단독·설교 도메인에 맞춰 **죽은 참조를 정리**했다 — TAWP 원본에서 다음을 제외:

- **IxTheo**(`ixtheo-searcher`) — 스크래핑 기반(느림)이라 제외. 결과적으로 **독일어(de) 검색 경로 없음 → ko/en 2언어 라우팅**.
- `nlk-subject-searcher`·`google-scholar-*`·`zotero-local` — TSPP fan-out 범위 밖.

반영 위치: `research_fanout.py`의 `ADAPTERS`·`DEFAULT_ENGINE_ROUTING`·`ENGINE_TIMEOUT`, `query_expand.py`의 `DEFAULT_ENGINE_ROUTING`, `skills/registry.json`.

## 동기화 정책

vendoring이므로 TAWP 개선이 자동 반영되지 않는다. 엔진 검색 로직(API 변경 대응 등)에 중요한 업데이트가 TAWP에 생기면 **수동으로** 다시 가져온다. 그때 위 "TSPP 적응" 차이를 재적용할 것.

## 제외(복사하지 않음)

- `.venv/` — machine-local·architecture-specific(헌법). 각 머신에서 `uv sync`로 생성.
- `output/`·`.raw/` — 산출물.
- `zotero_push.py` 등 멘토 단계에 불필요한 부속.

## 환경 준비

```bash
# kci/nlk 는 uv 격리 실행(uv_isolated=true) — 각 스킬 디렉터리에서:
cd skills/kci-api-searcher && uv sync   # nlk-biblio-searcher 도 동일
# API 키 (.env, git 제외됨):
#   KCI_OPEN_API_KEY=...
#   NLK_SEARCH_API_KEY=...
```
