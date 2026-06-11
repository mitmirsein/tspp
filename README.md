# TSPP

**TSPP**(Theology Sermon Preparation Pipeline)는 로컬에서 실행하는 설교 준비 파이프라인입니다.

설교자의 최초 묵상을 보존하면서 학술 자료를 검색하고, 사용자가 선택해 추가한 원문 PDF/텍스트를 추출하며, 설교자의 목소리를 유지한 채 설교 개요 작성을 준비합니다. 이 도구는 설교자의 분별, 목소리, 최종 승인을 대체하지 않습니다.

## 원칙

- 돕되, 대체하지 않는다.
- 설교자의 최초 묵상을 보존한다.
- 주요 단계 사이에는 HITL(사람 승인)을 요구한다.
- 실제 자료만 사용한다. 인용, 통계, 일화, 출처를 지어내지 않는다.
- **성경 인용도 동일하다.** 로컬 정본 본문(`data/scripture/`, 개역한글판)에서만 인용하고, 스크립트가 장절 존재와 인용 일치를 대조한다.
- 초록만으로 분석하지 않고, 사용자가 추가한 원문을 분석 대상으로 삼는다.
- 예화는 설교자의 예화 금고(`input/illustrations/`)에서만 조회한다. AI가 예화를 생성하지 않는다.
- 목회적 비공개 자료는 로컬 `input/`과 `output/` 안에 둔다.

에이전트 행동 규칙은 `AGENTS.md`를 먼저 읽습니다.

## 빠른 시작

실행 폴더를 만듭니다.

```bash
python3 scripts/tspp.py init my-run
```

학술 자료를 검색합니다.

```bash
python3 scripts/tspp.py search my-run --query "마태복음 5장 팔복"
```

사람이 고를 수 있는 원문 확보 리스트를 만듭니다.

```bash
python3 scripts/tspp.py list my-run
```

사용자가 선택한 PDF 또는 텍스트 원문을 아래 폴더에 넣습니다.

```text
input/resources/my-run/
```

원문을 추출하고 분석 패킷을 생성합니다.

```bash
python3 scripts/tspp.py ingest my-run
```

LLM 분석은 아래 파일에서 시작합니다.

```text
output/my-run/resource_analysis_packet.md
```

## 환경변수

`.env.example`을 복사해 `.env`를 만들고 필요한 키를 채웁니다. `.env`는 git에 포함되지 않습니다.

```bash
cp .env.example .env
```

필수 키:

- `KCI_OPEN_API_KEY`: KCI OpenAPI 검색
- `NLK_DATA_GO_KR_KEY`: data.go.kr 국립중앙도서관 전자저널 검색

선택 키:

- `SEMANTIC_SCHOLAR_API_KEY`: Semantic Scholar 호출 한도 안정화
- `CROSSREF_MAILTO`: Crossref polite pool용 연락 이메일

## 검색 엔진

fan-out 검색은 네 개의 API 엔진을 사용합니다.

| 엔진 | 키워드 | API | 키 |
|---|---|---|---|
| KCI | 한글 | KCI OpenAPI `articleSearch` | `KCI_OPEN_API_KEY` 필수 |
| NLK 전자저널 | 한글 | data.go.kr 전자저널 API | `NLK_DATA_GO_KR_KEY` 필수 |
| Semantic Scholar | 영어 | Graph API `/paper/search` | `SEMANTIC_SCHOLAR_API_KEY` 선택 |
| Crossref | 영어 | REST API `/works` | `CROSSREF_MAILTO` 선택 |

`output/<run>/meditation_seed.json`이 있으면 검색 명령은 아래 키워드 필드를 우선 사용합니다.

```text
evidence.keywords_used.ko
evidence.keywords_used.en
```

## 주요 명령

```bash
python3 scripts/tspp.py init <run>
python3 scripts/tspp.py status <run>
python3 scripts/tspp.py search <run> --query "<본문 또는 주제>"
python3 scripts/tspp.py list <run>
python3 scripts/tspp.py ingest <run>
python3 scripts/tspp.py preflight <run> \
  --meditation-seed output/<run>/meditation_seed.json \
  --resolved-voice output/<run>/resolved_voice.json
python3 scripts/tspp.py scripture <run>   # pericope 정본 팩 + 성경 인용 대조
python3 scripts/tspp.py binding <run>     # 본문 정합 구조 게이트 (개요 앵커)
python3 scripts/tspp.py audit <run>       # 호밀레틱 계기판 (비점수 worklist)
python3 scripts/tspp.py review <run>      # 정성 검수 보고서 뼈대 (3-pass)
python3 scripts/tspp.py retro <run>       # 설교 후 회고 + 이력 장부 적립
python3 scripts/tspp.py report <run>      # 종합 현황판 (읽기 전용)
```

## 원문 처리

`resource_ingest.py`는 아래 폴더의 PDF 또는 텍스트 파일을 읽습니다.

```text
input/resources/<run>/
```

생성 파일:

```text
output/<run>/resources/*.txt
output/<run>/resource_manifest.json
output/<run>/resource_analysis_packet.md
```

추출 텍스트는 페이지 표지를 보존합니다.

```text
===== p.3 =====
```

에이전트는 원문 기반 주장에 이 페이지 표지를 붙여야 합니다. 초록만 있는 검색 결과는 선별용 맥락일 뿐이며, 원문 분석의 대체물이 아닙니다.

## PDF 추출 방식

기본 추출 우선순위:

```text
opendataloader (.skills/pdf-extractor)
-> pymupdf
-> pdfplumber
-> pypdf
-> pdftotext
```

텍스트가 너무 적은 스캔 PDF는 `pdftoppm`과 `tesseract`가 있을 때 OCR로 보완할 수 있습니다.

## 성경 본문 데이터

`data/scripture/KorRV/`에 개역한글판(1961, 퍼블릭 도메인) 66권 31,104절이 vendoring되어 있습니다(출처·라이선스: `VENDOR.md`). `scripture_pack.py`가 본문(pericope)을 추출하고, `scripture_check.py`가 개요/원고의 장절 표기(존재 검증 = hard)와 직접 인용(일치 대조 = worklist)을 점검합니다.

### 다른 번역본 사용 (개역개정·새번역 등)

기본은 개역한글(KorRV)이지만, 자신이 쓰는 번역본 텍스트를 보유하고 있다면 로컬 변환해 그 번역본 기준으로 인용 대조를 받을 수 있습니다.

```bash
# 1) 보유 텍스트를 변환 (lines 포맷: "창1:1 본문" 또는 "창세기 1:1 본문" 한 줄 한 절)
python3 scripts/scripture_import.py --source ~/my_nkrv.txt --format lines \
  --translation NKRV --label "개역개정 (사용자 보유)" --license "사용자 사적 이용"
#    → input/scripture/NKRV/ 에 생성 (gitignore — 로컬 전용, 커밋되지 않음)

# 2) 기본 번역본으로 지정 (.env)
echo 'TSPP_TRANSLATION=NKRV' >> .env
#    또는 명령마다: python3 scripts/tspp.py scripture <run> --translation NKRV
```

- 지원 입력 포맷: `lines`(한 줄 한 절), `tsv`(책\t장\t절\t본문), `scrollmapper`(JSON). 부분 변환(신약만, 한 권만)도 동작합니다.
- `input/scripture/`의 사용자 보유본이 같은 코드의 vendored 본보다 우선합니다.
- **저작권이 살아 있는 번역본은 절대 `data/scripture/`(커밋 영역)에 두지 않습니다** — `--out` 생략 시 자동으로 로컬 전용 영역에 변환되며, 커밋 영역에 비공개 라이선스를 넣으려 하면 경고합니다.

## 세부 문서

- `START_HERE.md`: IDE/에이전트에서 멘션하기 좋은 빠른 진입점
- `MANUAL.md`: 전체 운영 매뉴얼
- `QUALITY_UPGRADE.md`: 품질 업그레이드 제안·구현 기록 (P0~P2)
- `references/research-workflow.md`: 검색, 원문 추가, 분석 워크플로우
- `references/interactive-hitl.md`: 대화형 HITL 5대 체크포인트 (HITL 5에 게이트 의무)
- `VENDOR.md`: vendored 검색 엔진·성경 본문 데이터 출처와 운영 메모
- `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`: 동일한 목회 윤리 헌법 파일
