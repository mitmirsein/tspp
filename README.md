# TSPP

**TSPP**(Theology Sermon Preparation Pipeline)는 로컬에서 실행하는 설교 준비 파이프라인입니다.

설교자의 최초 묵상을 보존하면서 학술 자료를 검색하고, 사용자가 선택해 추가한 원문 PDF/텍스트를 추출하며, 설교자의 목소리를 유지한 채 설교 개요 작성을 준비합니다. 이 도구는 설교자의 분별, 목소리, 최종 승인을 대체하지 않습니다.

## 원칙

- 돕되, 대체하지 않는다.
- 설교자의 최초 묵상을 보존한다.
- 주요 단계 사이에는 HITL(사람 승인)을 요구한다.
- 실제 자료만 사용한다. 인용, 통계, 일화, 출처를 지어내지 않는다.
- 초록만으로 분석하지 않고, 사용자가 추가한 원문을 분석 대상으로 삼는다.
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
- `ZOTERO_AUTO_PUSH`: Zotero 자동 푸시 사용 여부

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

## 세부 문서

- `START_HERE.md`: IDE/에이전트에서 멘션하기 좋은 빠른 진입점
- `MANUAL.md`: 전체 운영 매뉴얼
- `references/research-workflow.md`: 검색, 원문 추가, 분석 워크플로우
- `VENDOR.md`: vendored 검색 엔진 출처와 운영 메모
- `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`: 동일한 목회 윤리 헌법 파일
