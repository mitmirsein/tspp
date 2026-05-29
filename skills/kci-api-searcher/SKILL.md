---
name: kci-api-searcher
description: >
  KCI(한국학술지인용색인) 공식 직접 OpenAPI를 사용한 논문 메타데이터 검색 에이전트.
  open.kci.go.kr의 직접 API를 연동하여 초록, 저자, 학술지, DOI 정보를 일괄 수집합니다.
triggers:
  - "KCI API 검색"
  - "kci-api-searcher"
  - "KCI OpenAPI 검색"
  - "KCI API 논문 찾아줘"
---

# KCI OpenAPI Searcher Skill (kci-api-searcher)

KCI 직접 OpenAPI 서비스(`open.kci.go.kr/po/openapi/openApiSearch.kci`)를 **KCI 발급 직접 인증키(`KCI_OPEN_API_KEY`)**로 호출하는 에이전트 스킬. 공공데이터포털(data.go.kr) 우회 게이트웨이를 걷어내고, 초록 및 저자 정보를 1회의 단일 API 요청으로 고속 취합합니다.

## 핵심 특징
- **단일 요청 고속 취합:** 기존 data.go.kr의 4단계 보강 루프(M310 -> D214 -> D311)와 달리, 포털 직접 검색 API(`articleSearch`) 1회 호출로 저자명, 소속기관, 학술지명, UCI, DOI, 초록을 통합 반환합니다.
- **타임아웃 대폭 감소:** 공공 게이트웨이를 경유하지 않아 응답 딜레이 및 타임아웃 확률이 대폭 낮아집니다.
- **ForensicAudit 검증:** 입력 검색어가 부분 매칭되는 노이즈(예: "바르트" 검색 시 "헤르바르트" 매칭 등)를 지우기 위해 제목 텍스트 검증을 사후 수행합니다.

## 사용법

```bash
# 스킬 디렉터리(skills/kci-api-searcher) 안에서 실행. 의존성은 자체 pyproject.toml로 격리됨.

# 1) 기본 제목 검색 (JSON 출력)
uv run python scripts/search.py "구원론" --limit 5 --output json

# 2) 마크다운 리포트 출력
uv run python scripts/search.py "구원론" --limit 5 --output markdown
```

## 파라미터
- `query`: 검색할 논문 제목 키워드.
- `--page`: 페이지 번호 (기본 1).
- `--limit`: 출력 건수 (기본 10).
- `--output`: `json`(기본) | `markdown`.

## 에이전트 실행 패턴

```python
import subprocess, json

result = subprocess.run(
    ["uv", "run", "python", "scripts/search.py", "구원론", "--output", "json"],
    capture_output=True, text=True, cwd="skills/kci-api-searcher"
)
data = json.loads(result.stdout)
```

## 응답 필드
`title`, `title_eng`, `artiId`, `authors` (이름 배열), `affiliations` (소속기관 배열), `author_count`, `journal` (학술지명), `publisher`, `pub_year`, `pub_mon`, `doi`, `uci`, `citation_kci`, `citation_wos`, `abstract`, `url`
