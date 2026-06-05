# TSPP 에이전트 진입점

IDE 또는 에이전트 세션에서 이 파일을 단일 진입점으로 멘션하세요.

## 이 프로젝트가 하는 일

**TSPP**(Theology Sermon Preparation Pipeline)는 설교자의 설교 준비를 돕는 로컬 파이프라인입니다. 묵상 멘토링, 학술 자료 검색, 사용자가 추가한 원문 처리, 설교자 보이스 보존, 개요 생성, 선택적 원고 확장을 하나의 흐름으로 묶습니다.

TSPP는 설교 준비를 돕습니다. 설교자를 대체하지 않습니다.

## 양보할 수 없는 원칙

- 설교자의 최초 묵상이 우선입니다. `meditation.origin_memo`를 덮어쓰지 않습니다.
- 단계 이동은 HITL(사람 승인)로 통제합니다. `hitl.approved=false`인 산출물을 승인된 것처럼 다음 단계로 넘기지 않습니다.
- 인용, 통계, 일화, 출처를 지어내지 않습니다. 실제 `EvidencePack` 기록과 추출된 원문만 사용합니다.
- 학술 자료는 참고 자료입니다. 성경 본문을 대체하지 않습니다.
- 스크립트는 측정, 게이트, 추출, 구조화를 담당합니다. 에이전트는 산문을 작성합니다. 최종 확정은 설교자가 합니다.
- 비공개 입력과 출력은 로컬 `input/`과 `output/` 아래에 둡니다.

## 에이전트 작업 순서

1. 목회 윤리 헌법인 `AGENTS.md`를 먼저 읽습니다.
2. 사람용 짧은 워크플로우는 `README.md`에서 확인합니다.
3. 명령 단위의 자세한 설명이 필요할 때만 `MANUAL.md`를 읽습니다.
4. 검색 워크플로우 세부사항은 `references/research-workflow.md`를 확인합니다.
5. 가능하면 단일 CLI 래퍼를 사용합니다.

```bash
python3 scripts/tspp.py status <run>
python3 scripts/tspp.py search <run> --query "<본문 또는 주제>"
python3 scripts/tspp.py list <run>
python3 scripts/tspp.py ingest <run>
```

## 기본 실행 폴더 구조

```text
input/resources/<run>/                    사용자가 추가한 PDF 또는 텍스트 원문
output/<run>/EvidencePack.json            통합 검색 결과
output/<run>/evidence_list.md             사람이 고르는 원문 확보 리스트
output/<run>/resources/*.txt              페이지 표지가 붙은 추출 원문
output/<run>/resource_manifest.json       원문 파일과 검색 기록 매핑
output/<run>/resource_analysis_packet.md  LLM 분석 시작 패킷
```

## 기본 검색 라우팅

- 한글 키워드: KCI OpenAPI와 NLK 전자저널 API
- 영어 키워드: Semantic Scholar Graph API와 Crossref REST API
- `meditation_seed.json`이 있으면 아래 필드를 우선 사용합니다.
  `evidence.keywords_used.ko`, `evidence.keywords_used.en`

## PDF 추출

`resource_ingest.py`는 페이지 표지를 `===== p.N =====` 형식으로 보존합니다.

백엔드 우선순위:

```text
opendataloader (.skills/pdf-extractor)
-> pymupdf
-> pdfplumber
-> pypdf
-> pdftotext
```

스캔 PDF는 `pdftoppm`과 `tesseract`가 있을 때 OCR로 보완할 수 있습니다.

## 유용한 명령

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
