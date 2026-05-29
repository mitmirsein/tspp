---
name: nlk-biblio-searcher
description: >
  국립중앙도서관 검색 OpenAPI(www.nl.go.kr)를 호출해 제목/저자/ISBN 기반
  자연어 서지 검색을 수행하고, 도서·신문·기사·전자자료 등의 서지 메타데이터와
  nlk-interlinker 조회용 제어번호(CNTS-…)를 추출하는 스킬. 국립중앙도서관
  자연어 검색, 제어번호 확보, NLK LOD 파이프라인 앞단 구축에 사용한다.
---

# 국립중앙도서관 서지 검색 스킬 (검색 OpenAPI)

국립중앙도서관 직접 검색 OpenAPI(`https://www.nl.go.kr/NL/search/openApi/search.do`)로 자연어/제목/저자/ISBN 서지 검색을 수행하고, `nlk-interlinker`에 넘길 제어번호(CNTS-…)를 찾는다.

> **전환 배경:** 기존 data.go.kr `BookInformationService_v2`(`getbookList_v2`) 게이트웨이는 기관 백엔드 장애로 무응답(타임아웃) 상태였다. 동일 서지 데이터의 권위 원천인 **국립중앙도서관 자체 검색 OpenAPI**로 전환했다.

## 인증키
- dev 루트 `.env`의 **`NLK_SEARCH_API_KEY`** (국립중앙도서관 발급, 2026-05-27). data.go.kr 통합키(`NLK_API_KEY`)와 **별개**다.

## Quick Start
```bash
# 스킬 디렉터리(skills/nlk-biblio-searcher) 안에서 실행. 의존성은 자체 pyproject.toml로 격리됨.
uv run python scripts/search.py "톨스토이 무저항" --output markdown
uv run python scripts/search.py "본회퍼" --target title --limit 5 --output json
uv run python scripts/search.py --isbn 9788932473901 --output json
```

## 파라미터
- `query`: 검색어(`kwd`). `--isbn` 사용 시 생략.
- `--target`: 검색 대상 `total`(기본)·`title`·`author`·`publisher`
- `--isbn`: ISBN 정확 조회 (상세검색 모드)
- `--limit`(pageSize)·`--page`(pageNum)
- `--output`: `json`(기본) | `markdown`
- `--param key=value`: 추가 OpenAPI 파라미터(반복 가능)

## Output Contract
각 결과: `title`(하이라이트 태그 제거), `creator`, `publisher`, `issued`, `isbn`, `type`(도서/신문/기사/전자자료 등), `kdc`, **`control_number`**(CNTS-…, interlinker 입력), `nl_control_no`(KMO/KSE 등 NLK 제어번호), `place`, `url`, `raw`.

## Pipeline
1. 제목/저자/ISBN으로 서지를 검색해 **제어번호**를 확보한다.
2. `control_number`(CNTS-…)를 `nlk-interlinker`에 넘겨 외부 전거(owl:sameAs)를 보강한다.

## 한계 (정직)
- 글로벌 전거 연계(`owl:sameAs` → VIAF/LoC/Wikidata)는 **저자(KAC)·주제(KSH) 전거에 풍부**하고, **개별 서지 항목(CNTS)에는 대개 없다.** 따라서 biblio가 뽑은 CNTS를 interlinker에 넣어도 0건일 수 있다(정상). 전거 연계는 저자·주제 축(`nlk-subject-searcher` / 저자 전거)에서 일어난다.
- biblio의 핵심 가치는 **자연어 서지 검색 + 서지 메타데이터 + 제어번호 확보**다.
