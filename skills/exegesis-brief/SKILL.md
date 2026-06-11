---
name: exegesis-brief
description: 주해 브리프 작성. pericope 본문 팩(scripture_pack)을 원본으로 본문 자체의 자리·문학 구조·장르 특성·병행 본문·긴장 후보를 준비실 문서(exegesis_brief.md)로 정리한다. 학술 fan-out과 별개로 '본문 자체'의 주해 기반을 닦는다 — 강의 자료가 아니라 설교자의 등불이다.
version: 0.1.0
author: MS_Dev (TSPP)
triggers:
  - "#주해"
  - "#주해브리프"
  - "본문 주해"
  - "본문 구조 분석"
  - "주해 브리프"
references_path: "./templates"
---

# 🔦 Exegesis Brief 0.1 — 본문 자체의 주해 기반 (P1-3)

## 1. Overview

학술 논문은 그 주의 검색 운에 좌우되지만, **본문 자체의 구조 분석은 항상 가능하다.** 이 스킬은 sermon-mentor의 묵상 심화(Phase 2)와 학술 fan-out(Phase 3) 사이(= **Phase 2.5, 선택**)에서, pericope 본문 팩을 원본으로 본문의 자리·구조·장르·병행·긴장을 정리한 **준비실 문서 `exegesis_brief.md`**를 산출한다.

```
scripture_pack.json (P0-1 정본 본문)  ┐
meditation_seed (초안 — origin_memo)  ├→ [주해 브리프 작성] → exegesis_brief.md (준비실 문서)
EvidencePack.json (선택 — 학설 정착)  ┘
```

> **제1원칙**: 이 브리프는 **준비실 문서**다 — 강단에 올라가지 않는다. 배경 지식은 *장면을 비추는 등불*이지 강의 주제가 아니다(homiletic-voice.md §3-①). 브리프의 어떤 단락도 개요·원고에 그대로 이식하지 않는다 — 이식은 *강사화*의 지름길이며 계기판이 잡는다.

## 2. Workflow — 5-Phase

### Phase 0 — 입력 확보
- `output/<run>/scripture_pack.json`이 없으면 먼저 생성한다:
  ```bash
  python scripts/tspp.py scripture <run>    # 또는 scripture_pack.py --passage "..."
  ```
- 묵상이 먼저다 — **sermon-mentor Phase 1(경청) 이전에는 작성하지 않는다.** 주해가 묵상을 납치하면 안 된다(자료 선행 납치와 같은 위험).

### Phase 1 — 본문의 자리 (Setting)
- pericope가 책 전체 흐름과 **직전·직후 문맥**(pack의 `context_before/after`) 속에서 어디에 서 있는지 서술한다. 문맥 주장은 pack에 실제로 담긴 절에 정착한다.

### Phase 2 — 문학 구조 (Structure)
- pericope를 절 단위로 따라가며 흐름·반복·대조·전환을 관찰한다(`v.N` 표기). **관찰은 pack 본문 문자열에서만** — 본문에 없는 단어·구문을 "본문이 말한다"고 쓰지 않는다.
- 원어(그리스어·히브리어) 분석은 현재 정본 원어 데이터가 없으므로, 쓰려면 (a) EvidencePack 레코드에 정착하거나 (b) **`[원어 미검증]` 표지를 의무**로 붙인다(§7 정직).

### Phase 3 — 장르·병행 (Genre & Parallels)
- 본문 장르(비유·내러티브·시가·서신…)의 읽기 규칙을 적는다 — `voice_resolve --genre` 선택의 근거가 된다.
- 병행/공명 본문(공관 병행, 인용된 구약 등)은 **장절을 명시**하고, 개요에서 앵커로 쓰려면 frontmatter `cross_refs` 선언이 필요함을 메모한다(binding_check §3 게이트와 연동).

### Phase 4 — 긴장·찌름 후보 (Offense)
- 본문이 *스스로* 일으키는 불편·아포리아 후보를 수집한다(봉합하지 않는다 — §6). seed의 `tensions`로 흘러갈 원석.

### Phase 5 — 묵상 접점 + 산출 (HITL)
- `origin_memo`의 처음 생각과 본문 관찰이 **만나는 지점/충돌하는 지점**을 적는다 — 묵상을 덮어쓰지 않고 비춘다(§4).
- `output/<run>/exegesis_brief.md` 산출(스키마: [templates/exegesis_brief.example.md](./templates/exegesis_brief.example.md)). 별도 승인 파일은 없다 — **HITL 3(씨앗 승인)에 부속**되어 설교자가 함께 확인한다.

## 3. Gotchas (피해야 할 함정)

1. **강단 이식** — 가장 큰 위험. 브리프 단락을 개요·원고에 복사하면 설교가 강의가 된다. 브리프는 등불, 개요는 그 빛 아래서 *새로* 쓴다.
2. **유령 주석** — "학자들은", "전통적으로" 같은 무출처 학설 금지. 학설은 EvidencePack 레코드(`(저자 연도, p.N)`)에만 정착.
3. **원어 허세** — 검증 불가한 원어 주장에 `[원어 미검증]`을 빼먹지 않는다.
4. **묵상 납치** — 경청(P1) 전에 주해를 들이밀지 않는다. 주해는 묵상의 종이지 주인이 아니다.
5. **본문 너머 관찰** — pack에 없는 절·단어를 본문 관찰로 서술하지 않는다(필요하면 pack의 `--context` 범위를 늘려 재생성).

## 4. 윤리 & 안전 (목회 윤리 헌법)

- 본문 충실 > 시대 적합성(§3) · origin_memo 불가침(§4) · 긴장 보존(§6) · 유령인용 금지(§7).
- 산문은 에이전트, 측정·추출은 스크립트(scripture_pack), 확정은 설교자(§11).

## 5. Reference Links

- [templates/exegesis_brief.example.md](./templates/exegesis_brief.example.md) — 산출 구조 예시.
- `../../scripts/scripture_pack.py` — pericope 정본 추출(P0-1) · `../../data/scripture/` — 본문 데이터(VENDOR.md).
- 상류: `skills/sermon-mentor`(Phase 2.5로 호출) · 하류: `skills/sermon-outline`(앵커·cross_refs 근거).
- `../../references/homiletic-voice.md` §3-① — 등불 원칙(강사화 해소).

---
*MS_Dev · TSPP · exegesis-brief v0.1 — 본문 자체의 주해 기반. 준비실 문서이지 강의 원고가 아니다. 주해는 묵상의 종이다.*
