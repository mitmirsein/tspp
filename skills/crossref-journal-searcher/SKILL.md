---
name: crossref-journal-searcher
description: Crossref API /works 엔드포인트를 활용하여 엄선된 135종(실제 58개) 프리미엄 신학 저널의 서지 데이터를 정밀 검색 및 필터링합니다.
version: 1.0.0
author: Antigravity
triggers:
  - "#journal"
  - "#crossref-journal"
  - "저널 검색"
  - "journal search"
capabilities:
  - crossref_journal_filtering
  - issn_chunking_query
  - bibliographic_normalization
---

# 📚 Crossref Journal Searcher

## 1. Overview
엄선된 주요 신학 학술 저널 목록(`theology_journals.json`)의 ISSN 필터를 Crossref `/works` API와 결합하여, 사용자가 요청한 검색어와 일치하는 정밀한 저널 논문 서지 데이터를 실시간으로 조회하고 필터링하는 전용 검색 스킬이다.

## 2. Core Engine
이 스킬의 핵심 실행체는 **`scripts/crossref_journal_searcher.py`**이다.

### ⚙️ Usage
```bash
# 기본 검색어 기반 조회 (JSON 결과 표준 출력)
python scripts/crossref_journal_searcher.py --query "Amos 4:13"

# 검색 결과 수 한도 설정 및 디버그 모드
python scripts/crossref_journal_searcher.py --query "messiah" --limit 10 --debug
```

## 3. Operations & Standards
- **ISSN Chunking**: Crossref API의 요청 제한(URL 길이 제한 및 필터 갯수 제약)을 예방하기 위해, 타겟 저널의 ISSN 목록을 25개 단위로 청킹(Chunking)하여 병렬/순차 쿼리를 전송한다. 이후 최종 취합된 결과들을 중복 제거 및 점수 순으로 정렬하여 반환한다.
- **표준화된 출력**: 수집된 메타데이터는 동일한 공통 서지 규격(`title`, `authors`, `journal`, `year`, `volume`, `issue`, `pages`, `doi`, `link`, `format`)으로 노멀라이징하여 JSON 또는 마크다운 형식으로 출력한다.
