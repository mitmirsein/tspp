---
name: sermon-outline
description: 설교 개요 작성. 묵상 씨앗(meditation_seed) + 고정된 보이스(resolved_voice) + (선택)학술 근거(EvidencePack)를 받아, 보이스를 주입한 강단 의례로 본문에 충실한 설교 개요(sermon_outline.md)를 함께 빚고, 호밀레틱 계기판으로 점검해 HITL 승인까지 잇는다. AI는 *돕는다* — 대필하지 않는다.
version: 0.1.0
author: MS_Dev (TSPP)
triggers:
  - "#개요"
  - "#설교개요"
  - "설교 개요 작성"
  - "씨앗으로 개요"
  - "개요 빚자"
references_path: "./references"
---

# 📜 Sermon Outline 0.1 — 작성 단계 연결

## 1. Overview

상류 산출물을 받아 **본문에 충실한 설교 개요(`sermon_outline.md`)**를 빚는다. 보이스 아키텍처(추출→3층→주입)와 묵상 멘토(씨앗)를 *실제 설교*로 잇는 고리다. 보이스 고정 원칙 Phase 5(메시지+개요)→7(작성)→8(감사).

```
meditation_seed.json (sermon-mentor·HITL)  ┐
resolved_voice.json  (voice_resolve·HITL)  ├→ preflight → [의례·작성] → sermon_outline.md → 계기판 → HITL
EvidencePack.json    (선택)                ┘
```

> **제1원칙**: AI는 *돕는다 — 대필하지 않는다*. 영적 권위·최종 sign-off는 설교자 귀속(목회 윤리 헌법 §8). 설교자의 묵상(origin_memo)과 목소리가 1차이고, 이 스킬은 그것을 *본문에 충실한 개요로* 빚는 조력자다. 방법론: [outline-method.md](./references/outline-method.md).

## 2. Workflow — 5-Phase

### Phase 0 — Preflight & Gate
상류를 한 브리프로 수합하고 **HITL 게이트**를 검증한다.

```bash
python scripts/outline_preflight.py \
  --meditation-seed output/<run>/meditation_seed.json \
  --resolved-voice  output/<run>/resolved_voice.json \
  [--evidence output/<run>/EvidencePack.json] \
  --out output/<run>/writing_brief.json
```
- `gates.ready=false`(묵상 씨앗·보이스 중 미승인)면 **작성에 들어가지 않는다**. 게이트 해소 먼저.

### Phase 1 — 보이스 주입 (강단 의례)
첫 문장을 쓰기 전, `writing_brief.voice.injection_block`을 **명시적으로 자기에게 선언**한다(원고엔 남기지 않음). homiletic-voice.md §5 의례 + L1-개인 + L2(persona 어조 차용·청중 음높이). L2 stance는 components로 *한 문장* 렌더(스크립트가 짓지 않음).

### Phase 2 — 개요 작성
`writing_brief.structure_hint`를 따라 `sermon_outline.md`를 쓴다(도입·논점 3–5·예화·적용·긴장 보존·결단·기도). 핵심 규율([outline-method §3](./references/outline-method.md)):
- **본문에 뿌리** — 각 논점은 `meditation_core.rooted_in_text`·`message.text_anchor`에 정착.
- **유령인용 금지** — 인용은 `evidence` EvidencePack 실제 레코드만. 자료는 설교자 참고이지 본문 권위 대체 아님.
- **origin_memo 불가침** — 설교자 원본 묵상을 덮어쓰지 않고 *증폭*.
- **긴장 보존** — `tensions[].disposition`(open/resolving/resolved) 따라; 평탄화 금지.
- **보이스 충실** — lexicon_avoid 회피, persona 어조 차용(견해 아님), 청중 음높이.

### Phase 3 — Foundation Gate (본문 정합)
작성 후 binding 점검: 각 논점·적용이 본문에서 나오는가? `message.eisegesis_risk`가 high인 후보는 본문 재정착 또는 제외. **적용이 본문을 왜곡하면 멈춘다**(eisegesis 차단 — 본문 정합 hard gate hard gate).

### Phase 4 — 호밀레틱 계기판
```bash
python scripts/homiletic_audit.py --draft output/<run>/sermon_outline.md \
  --resolved output/<run>/resolved_voice.json \
  --preacher-voice output/<run>/preacher_voice.json \
  --out output/<run>/homiletic_audit.json
```
- 비점수 worklist(강사화·재판관화·상투구·논문체 + 결핍·드리프트·회피표현). 점등 신호를 설교자에게 전달 — **판단은 설교자**.
- **보정 주의**: 계기판은 *구어 산문*(원고) 기준이다. 골격 개요(불릿·표제)는 본래 hapnida_ratio가 낮아 hapnida 기반 *강사화* 신호가 아티팩트일 수 있다 — 개요의 **산문 단락**(도입·적용·결단·기도)을 기준으로 읽는다. 전체 원고로 확장했을 때 더 정확.

### Phase 5 — HITL Sign-off
설교자 승인(`sermon_outline` frontmatter `approved`). (선택) 전체 원고 확장은 별도 — 개요가 ★ 기본 산출(개요 기본 산출 원칙).

## 3. Gotchas (피해야 할 함정)

1. **대필** — 가장 큰 위험. AI가 매끈한 *남의* 설교를 쓰지 않는다. 씨앗·보이스를 *그 설교자의* 개요로 빚는다.
2. **유령인용** — EvidencePack에 없는 문헌·통계·일화를 지어내지 않는다.
3. **묵상 덮어쓰기** — origin_memo는 불가침. "더 좋은 메시지"로 대체하지 않는다.
4. **긴장 평탄화** — 인위적 봉합도, 정직한 해소의 강제 개방도 금지.
5. **eisegesis** — 적용이 본문을 미끼로 다른 메시지로 도약하면 멈춘다.
6. **보이스 중성화** — 설교자 어투·persona 어조를 매끈한 일반 설교투로 중화하지 않는다.
7. **게이트 무시** — gates.ready=false인데 작성하지 않는다.

## 4. 윤리 & 안전 (목회 윤리 헌법)

- 대필 금지 · 영적 권위·sign-off는 설교자 · 본문 충실 > 시대 적합성.
- 회중 일화는 동의·익명화(audience 익명성). 정치·계층 편향 차단(redteam).
- 씨앗·보이스·회중 정보는 사용자 자산 — 로컬 처리.

## 5. Reference Links

- [references/outline-method.md](./references/outline-method.md) — 작성 방법론(구조·정착·게이트·보이스 주입).
- [templates/sermon_outline.example.md](./templates/sermon_outline.example.md) — 개요 산출 구조 예시.
- `../../scripts/outline_preflight.py` — 게이트+브리프 수합 · `../../scripts/homiletic_audit.py` — 계기판.
- 상류: `skills/sermon-mentor`(씨앗) · `scripts/voice_resolve.py`(보이스) · `references/homiletic-voice.md`(L1).
- (선택·향후) TOS Decalogue 작성 엔진 브리지 — TSPP 단독 원칙상 런타임 의존 아님.

---
*MS_Dev · TSPP · sermon-outline v0.1 — 씨앗+보이스+근거 → 본문 충실 개요. AI는 돕는다, 대필하지 않는다. 보이스는 작성 전 고정, 계기판은 작성 후 안전망.*
