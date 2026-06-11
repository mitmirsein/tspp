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
| `skills/nlk-ejournal-searcher/` | TSPP 추가/대체 | 국립중앙도서관 data.go.kr 전자저널 검색 · 키 `NLK_DATA_GO_KR_KEY` |
| `skills/semantic-scholar/` | 동일 | Semantic Scholar(영문) 검색 · 키 불요 |
| `skills/crossref-journal-searcher/` | 동일 | Crossref(영문 저널) 검색 · 키 불요 |

## TSPP 적응(원본과의 차이)

공개 단독·설교 도메인에 맞춰 fan-out 범위를 API 4엔진으로 고정했다.
결과적으로 검색 라우팅은 한국어/영어 2언어만 사용한다.

반영 위치: `research_fanout.py`의 `ADAPTERS`·`DEFAULT_ENGINE_ROUTING`·`ENGINE_TIMEOUT`, `query_expand.py`의 `DEFAULT_ENGINE_ROUTING`, `skills/registry.json`.

## 성경 본문 데이터 (`data/scripture/`)

성경 인용 정합 게이트(`QUALITY_UPGRADE.md` P0-1)의 정본 본문 데이터.

| 항목 | 내용 |
|---|---|
| 번역본 | **개역한글판 (1961)** — `data/scripture/KorRV/` (66권 31,104절) |
| 라이선스 | **퍼블릭 도메인.** 대한성서공회의 개역한글판 저작권은 만료되어 자유 이용 가능 — 대한성서공회 저작권 FAQ 및 알파알렙 라이선스 안내에서 확인(2026-06-11). |
| 원 데이터 | [scrollmapper/bible_databases](https://github.com/scrollmapper/bible_databases) `formats/json/KorRV.json` (2026-06-11 입수) |
| 변환 도구 | `scripts/scripture_import.py` (scrollmapper JSON → 책별 파일 + `index.json`) |
| 검증 | 마태복음 21:33·38·39를 독립 소스(한국어 위키문헌 개역한글판)와 글자 단위 대조 — 3구절 일치 확인(2026-06-11). 총 절수 31,104는 정경(KJV 절번호 체계) 표준과 일치. |

라이선스 확인 출처:
- 대한성서공회 저작권 FAQ: <https://www.bskorea.or.kr/bbs/board.php?bo_table=copyright_faq&wr_id=3>
- 알파알렙 저작권 안내(개역한글 퍼블릭 도메인 명시): <https://app.alphalef.com/page/license/>

주의:
- **저작권이 살아 있는 번역본(개역개정·새번역 등)은 커밋하지 않는다.** 사용자 보유본은 `scripture_import.py`(lines/tsv/scrollmapper 포맷)로 변환해 `input/scripture/<코드>/`(gitignore, 로컬 전용)에 둔다 — `--out` 생략 시 기본 경로이며, scripture_lib가 vendored 본보다 우선 탐색한다. 선택은 `.env`의 `TSPP_TRANSLATION=<코드>` 또는 명령별 `--translation`.
- 원어 데이터(SBLGNT·WLC)는 라이선스상 vendoring 가능하나 현재 미포함(향후 선택 과제 — QUALITY_UPGRADE §3 P0-1).

## 동기화 정책

vendoring이므로 TAWP 개선이 자동 반영되지 않는다. 엔진 검색 로직(API 변경 대응 등)에 중요한 업데이트가 TAWP에 생기면 **수동으로** 다시 가져온다. 그때 위 "TSPP 적응" 차이를 재적용할 것.

## 제외(복사하지 않음)

- `.venv/` — machine-local·architecture-specific(헌법). 각 머신에서 `uv sync`로 생성.
- `output/`·`.raw/` — 산출물.

## 환경 준비

```bash
# KCI는 uv 격리 실행(uv_isolated=true), NLK전자저널은 stdlib 실행:
cd skills/kci-api-searcher && uv sync
# API 키 (.env, git 제외됨):
#   KCI_OPEN_API_KEY=...
#   NLK_DATA_GO_KR_KEY=...
```
