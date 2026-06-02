---
name: semantic-scholar
description: "Semantic Scholar API 기반의 학술 논문 및 인용 네트워크 탐색 에이전트. (API Key 필수)"
author: "MS_Dev"
version: "2.0.0"
triggers:
  - "#semanticscholar"
  - "#s2"
  - "#시맨틱스콜라"
category: "Intelligence & Workflow"
tags: ["recon", "api", "academic", "papers"]
---

# 🎓 Semantic Scholar (API) Recon Skill

> **Identity**: API 기반 초고속 학술 논문 탐색망
> **Core Tool**: `scripts/s2_runner.py`
> **Target**: semanticscholar.org (Graph API)

## 📌 개요 (Overview)
`semantic-scholar` 스킬은 **Semantic Scholar Graph API**를 활용하여 지정된 키워드나 논문을 검색하고, 인용 수, 초록, Open Access PDF 링크 등을 즉각적으로 마크다운 리포트로 생성하는 API 정찰 도구입니다.

## 🛠️ 사용법 (Usage)

### 1. 일반 키워드 검색
사용자의 키워드를 `--query`로 전달하여 즉각적인 논문 리스트를 확보합니다.

```bash
# 기본 검색 (터미널 출력)
uv run python skills/semantic-scholar/scripts/s2_runner.py --query "Pauline justification ethics" --limit 5

# 리포트 파일로 저장
uv run python skills/semantic-scholar/scripts/s2_runner.py --query "Dietrich Bonhoeffer Sermon on the Mount" --limit 10 --output "./output/S2_Bonhoeffer_Report.md"
```

## ⚙️ 아키텍처 및 설정 (Architecture)

1. **Authentication**: 프로젝트 루트의 `.env` 파일 내 `SEMANTIC_SCHOLAR_API_KEY`를 사용합니다. 키가 없어도 동작하지만 Rate Limit(3초당 1회)가 걸립니다.
2. **Output Format**: 생성되는 Markdown 리포트는 서지 정보(Authors, Year, Venue, Citations, Links, Abstract)를 포함하여 MS_Brain.nosync 지식망에 즉시 편입할 수 있도록 규격화되어 있습니다.
