---
name: nlk-ejournal-searcher
description: 국립중앙도서관 data.go.kr 전자저널(학술논문) 검색. 초록·목차·ISSN·DBpia 원문링크를 제공하는 한국어 학술 자료 1차 정찰 엔진.
version: 1.0.0
author: MS_Dev (TSPP)
---

# 📚 NLK 전자저널 검색 (data.go.kr BookInformationService_v2)

## 1. Overview

국립중앙도서관 국가서지 LOD의 **전자저널 정보 서비스**(`getElectronicJournalList_v2`)를
호출해 한국어 학술논문을 검색한다. 이 엔진은 **초록·목차·ISSN·DBpia 원문링크**(`DCTERMS_identifier`)를 제공해 [research-workflow](../../references/research-workflow.md)
1단계(정찰)의 한국어 공급원이 된다.

## 2. Usage

```bash
python scripts/search.py "칭의" --limit 5 --output json
```

- 검색: `label=<쿼리>` (제목/저자 부분매칭). API 응답은 XML 전용(type=json 무시됨) → ElementTree 파싱.
- 인증: 환경변수 **`NLK_DATA_GO_KR_KEY`**(data.go.kr 일반 인증키, dev 루트 `.env`).
- 순수 stdlib(외부 패키지 0).

## 3. 출력 (정규화)

`research_fanout`/`evidence_collect`가 소비하는 키만 산출(raw LOD 30필드는 버림 — 토큰 절약):

| 키 | 출처 태그 | 비고 |
|---|---|---|
| title | DCTERMS_title | |
| authors | DC_creator | 복수 콤마결합 |
| year | DCTERMS_issued | 앞 4자리 연도 추출 |
| venue | NLON_titleOfHostItem | 저널명 |
| abstract | DCTERMS_abstract | ★초록(채움률 ~20%, 없어도 레코드 유지) |
| issn | BIBO_issn | |
| url | DCTERMS_identifier | DBpia 등 원문 입수 경로 |
| toc | DCTERMS_tableOfContents | 목차 |

## 4. 한계 (정직)

- 초록 채움률 ~20% — 없어도 리스트에서 **버리지 않는다**(워크플로우 §3 소프트 원칙).
- `label`은 제목/저자 매칭이라 주제 전용 검색은 아님.
- data.go.kr 일평균 트래픽 10,000(서비스당).

---
*MS_Dev · TSPP · nlk-ejournal-searcher v1.0 — 초록·원문링크 공급.*
