# 학술 자료 정찰 및 3단계 수집 워크플로우 (KCI + NLK전자저널 + Crossref + Semantic Scholar)

이 문서는 API 메타데이터(특히 초록 데이터 누락 및 부실)의 한계를 극복하고, 설교 작성 시 발생할 수 있는 유령 인용(Ghost Citation)을 원천 방지하며, 고품질 학술 통찰을 확보하기 위한 **TSPP(Theology Sermon Preparation Pipeline)의 연구 및 문헌 수집 워크플로우**를 정의합니다.

---

## 1. 4대 엔진 (언어 라우팅: ko 2 + en 2)

국내·글로벌 신학 담론을 균형 있게 정찰하기 위해 4대 엔진을 조합한다.
키워드는 언어별로 라우팅된다 — **한국어 → KCI·NLK전자저널 / 영어 → Crossref·S2**.

| 엔진 | 언어 | 주 역할 및 특징 |
| :--- | :--- | :--- |
| **KCI** (한국학술지인용색인) | ko | 한국어 신학 논문 — 한국어 초록을 가장 안정적으로 공급. 목회 컨텍스트 즉시 적용 |
| **NLK전자저널** (data.go.kr v2) | ko | 국가서지 LOD 전자저널 — 초록·목차·ISSN·**DBpia 원문링크** 제공(서지 전용 nlk-biblio 대체) |
| **Crossref** | en | 글로벌 권위 자료·DOI 매핑 — 출판사 직접 등록 서지, JATS 초록 수집 |
| **Semantic Scholar** (S2) | en | 글로벌 시맨틱 검색 — 인용 그래프 + **OA PDF 링크** 직접 제공 |

> NLK전자저널 키: `NLK_DATA_GO_KR_KEY`(data.go.kr 일반 인증키, nl.go.kr `NLK_SEARCH_API_KEY`와 별개).
> 초록 채움률은 엔진·쿼리별 편차(KCI 충실 / Crossref·전자저널 부분 / S2 가변) — 없어도 리스트에서 버리지 않는다(§3).

---

## 2. 3단계 수집 워크플로우 (3-Stage Workflow)

TSPP는 API 검색 결과에만 의존해 최종 원고를 작성하지 않고, **사용자의 개입(HITL)**을 결합한 3단계 프로세스를 따릅니다.

```
[1단계: 1차 정찰] ──────▶ [2단계: HITL 원문 입수] ──▶ [3단계: LLM 본문 분석]
 (KCI+NLK전자저널+Crossref+S2)   (정예 파일 로컬 배치)         (유령인용 원천 차단)
```

### 1단계: 1차 정찰 (Discovery Phase)
* **목표**: 완벽한 초록 분석이 아니라, 설교자가 선별할 수 있는 **'식별 정보(제목/저자/DOI)'와 '원문 입수 경로(링크)'**를 정직하게 제공하는 것입니다.
* **작동**: KCI, NLK전자저널, Crossref, Semantic Scholar를 키워드별로 가동하여 후보 리스트를 추출합니다. API 응답의 초록 필드가 비어있더라도 유용한 연구 목록이라면 필터링(삭제)하지 않고 리스트에 남겨둡니다.

### 2단계: HITL 원문 입수 (Ingestion Phase)
* **목표**: 실제 분석에 사용할 고밀도 학술 원문(Full Text)을 로컬 환경에 확보합니다.
* **작동**: 설교자가 1단계 정찰 결과를 보고, 설교에 정말 도움이 될 정예 논문 2~3편을 선별합니다. 제공된 링크(OA PDF 링크, DOI 링크 등)를 통해 인터넷에서 PDF 또는 Markdown 파일을 다운로드하여 지정된 리소스 폴더(`input/resources/` 등)에 직접 넣습니다.

### 3단계: LLM 본문 분석 (Analysis Phase)
* **목표**: 입수된 실물 본문을 심층 분석하여 설교 개요와 온톨로지 정보를 추출합니다.
* **작동**: 에이전트가 리소스 폴더에 투입된 실제 텍스트 전체를 분석합니다. 요약이나 단편적인 초록 대신 **실제 논문의 서론-본론-결론 전체 컨텍스트**를 활용하므로 주해의 깊이가 비약적으로 상승하며, 유령 인용의 위험이 차단됩니다.

---

## 3. 세부 설계 및 편의성 고려사항

### ① 원문 입수를 돕는 링크 제공 (1단계)
* 1단계 1차 정찰 결과 리포트에는 설교자가 쉽게 원문을 확보할 수 있도록 아래 항목들이 명확히 표기되어야 합니다.
  * Semantic Scholar가 반환하는 `openAccessPdf` 직접 다운로드 링크
  * Google Scholar 검색 바로가기 링크 (DOI 혹은 제목 쿼리 자동 완성)
  * RISS 또는 국립중앙도서관 바로가기 링크 (KCI 논문용)

### ② 입수 폴더 · 파일 매핑 규칙 (File Mapping Rule)
* **입수 폴더**: `input/resources/<run>/` (목회자 자산 — gitignore·로컬 처리, 헌법 §9). `evidence_list.md`가 이 경로를 안내하고, `resource_ingest.py`가 없으면 만든다.
* **권장 파일명 = DOI 슬러그** (`10.x/abc` → `10.x_abc.pdf`). 실측상 레코드의 **DOI 보유율이 압도적**(예: 팔복 38건 중 DOI 37·citekey 0)이라 DOI를 사실상의 안정 식별자로 삼는다. `evidence_list.md`의 각 항목이 **권장 파일명**을 직접 표기하므로, 그대로 저장하면 자동 매핑된다.
* **매핑 단계**(`resource_ingest.match_record`): ① 파일명 stem == DOI 슬러그(정확) → ② DOI 부분 포함 → ③ citekey → ④ 제목 토큰 자카드(파일명+첫 페이지 텍스트 vs 레코드 제목, ≥0.5). DOI 없는 소수 레코드는 제목 슬러그로 폴백.

### ③ 본문 추출 — 페이지 번호 보존 (Citation-Safe Extraction)
* `python3 scripts/resource_ingest.py <run>` → 입수 PDF/텍스트를 **페이지 마커가 박힌 텍스트**로 추출하고 `resource_manifest.json`(파일↔레코드 매핑)을 만든다. 추출물은 `output/<run>/resources/`(gitignore).
* **인용을 위한 페이지 보존**: 각 페이지를 `===== p.N =====` 마커로 구분 → 에이전트가 `(저자 연도, p.N)` 정확 인용을 만든다(유령인용 차단, §7). 스크립트는 추출·매핑만 하고 산문(요약·분석)은 짓지 않는다(§11) — 분석은 에이전트가 페이지 표시 텍스트를 읽고 한다.
* **백엔드(있는 것 자동 선택)**: pymupdf > pdfplumber > **pypdf**(requirements.txt 기본·순수 파이썬·BSD) > pdftotext(poppler). OCR된 PDF(요즘 추세)는 텍스트 레이어가 있어 그대로 추출되고, 스캔본은 tesseract가 있으면 best-effort OCR 폴백.
* **최초 1회 환경**(불특정 다수 배포 상정): `pip install -r requirements.txt` (또는 시스템 `poppler`). 머신 로컬 venv(`.venv-*`, gitignore)에 설치 — 헌법 §11.

### ④ 소프트 폴백 모드 (Degraded Mode)
* 원문 PDF를 확보하지 못한 레코드는 `resource_manifest.json`에 `status: abstract_only`로 남는다. 1차 정찰의 초록·메타데이터로 제한적 분석은 허용하되, 정보 밀도가 낮으므로 과도한 비약을 하지 않도록 경고를 표시한다.
