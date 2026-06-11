---
name: manuscript-expander
description: 설교 원고 확장. 설교자가 승인한 개요(sermon_outline.md)를 보이스에 충실한 전체 구어 설교 원고(full_manuscript.md)로 확장하고, 전달 시간을 추정하며, 호밀레틱 계기판으로 점검해 HITL 승인까지 잇는다. 개요의 뼈대에 설교자의 살을 붙이는 조력 — 대필이 아니다.
version: 0.1.0
author: MS_Dev (TSPP)
triggers:
  - "#원고"
  - "#설교원고"
  - "#원고확장"
  - "개요를 원고로"
  - "전체 원고 작성"
references_path: "./references"
---

# 📃 Manuscript Expander 0.1 — 개요 → 전체 원고 (선택)

## 1. Overview

설교자가 **승인한 개요(`sermon_outline.md`)**를 받아, 보이스에 충실한 **전체 구어 설교 원고(`full_manuscript.md`, 6~10쪽)**로 확장한다. 개요의 *뼈대*에 살을 붙이되 — 그 살은 *그 설교자의* 것이어야 한다. 보이스 고정 원칙 Phase 7·§6(선택 산출).

```
sermon_outline.md (승인) + writing_brief.json + resolved_voice.json
  → [manuscript-expander: 의례·확장] → full_manuscript.md
  → delivery_pack.py (시간·섹션·낭독) + homiletic_audit.py (계기판) → HITL sign-off
```

> **제1원칙**: 전체 원고는 **★ 기본이 아니라 선택**이다(개요 기본 산출 원칙). 개요가 기본 산출인 이유는 대필 위험 때문 — 전체 원고를 AI가 쓸수록 "설교자가 더 깊이 준비한 자기 설교"에서 "AI가 쓴 남의 글"로 미끄러지기 쉽다. 그러므로 이 스킬은 **개요의 논리·구조·보이스를 그대로 펴는** 확장이지 *새로 쓰는* 작업이 아니다. 방법론: [expansion-method.md](./references/expansion-method.md). 헌법: `../../CLAUDE.md`.

## 2. Workflow — 5-Phase

### Phase 0 — Gate
- `sermon_outline.md` frontmatter `approved: true` 확인. **미승인이면 확장하지 않는다**(개요 먼저 HITL).
- `writing_brief.json`·`resolved_voice.json` 재로드(같은 씨앗·보이스).

### Phase 1 — 보이스 주입 (강단 의례)
- 개요 작성 때와 **같은** `resolved_voice.injection_block`을 다시 선언한다(원고엔 남기지 않음). 보이스가 개요와 원고에서 흔들리지 않게.

### Phase 2 — 확장 (개요 → 구어 원고)
개요의 각 섹션(도입·논점·예화·적용·긴장·결단·기도)을 **구어 설교 산문**으로 편다. [expansion-method §3](./references/expansion-method.md):
- **개요의 논리를 따른다** — 새 논점·새 메시지를 *추가하지* 않는다. 개요에 있는 것을 *말로* 푼다.
- **구어 register** — 회중을 향한 직접 호명, 듣기 좋은 호흡, '~습니다'체. 문어·논문체 금지.
- **보이스 충실** — persona 어조 차용, 청중 음높이, lexicon_avoid 회피, 시그니처 표현 살림.
- **근거 정직** — 유령인용 금지(brief의 EvidencePack 레코드만). 새 통계·일화 지어내지 않음. 성경 인용은 `scripture_pack.json` 본문만(§7 확장 — 확장 후 `tspp.py scripture <run>`으로 재대조). 예화는 개요에 이미 인용된 금고 카드(`(예화금고: <id>)`)만 펴고, 확장 중 새 예화를 끼워넣지 않는다.
- **불변식** — origin_memo 불가침 · 긴장 보존(disposition) · eisegesis 차단.

### Phase 3 — 전달 준비물 (Delivery Pack)
```bash
python scripts/delivery_pack.py --manuscript output/<run>/full_manuscript.md \
  --target-min 30 [--chars-per-min 320] --out output/<run>/delivery_pack.json
```
- 측정: ① 전체·**섹션별** 전달 시간(±15% over/under/on_target, 분량 쏠림 점검) ② **낭독 보조**(긴 문장 호흡·원어/외국어 발음·숫자 읽기·긴 어절). **대략 추정** — 설교자가 자기 속도로 보정.
- 에이전트는 이 신호로 `delivery_pack.md`(언어 조정 산문 — *어떻게 소리 낼지*·호흡·강조)를 정리한다. 측정=스크립트, 산문=에이전트, 확정=설교자. 예시: [templates/delivery_pack.example.md](./templates/delivery_pack.example.md).
- over면 절제, under면 전개 보강(개요 내; 분량 채우려 군더더기·반복 금지). 원어는 강단에서 풀어 말하기 권장.

### Phase 4 — 호밀레틱 계기판
```bash
python scripts/homiletic_audit.py --draft output/<run>/full_manuscript.md \
  --resolved output/<run>/resolved_voice.json \
  --preacher-voice output/<run>/preacher_voice.json \
  --out output/<run>/homiletic_audit.json
```
- 전체 원고는 *구어 산문*이라 계기판이 **정밀히** 작동(개요의 hapnida 아티팩트 없음). 강사화·재판관화·상투구·논문체 + 드리프트·회피표현을 본다. 판단은 설교자.

### Phase 5 — HITL Sign-off
- 설교자 최종 승인(`full_manuscript` frontmatter `approved`). (선택) `delivery_pack`(시간·언어 최종 조정)은 분리.

## 3. Gotchas (피해야 할 함정)

1. **대필로의 미끄러짐** — 가장 큰 위험. 개요를 *펴는* 것이지 *새로 쓰는* 게 아니다. 개요에 없는 메시지·논점을 끼워넣지 않는다.
2. **분량 채우기** — 목표 시간을 맞추려 군더더기·반복·상투구로 늘리지 않는다(계기판이 상투구를 잡는다).
3. **유령인용** — 확장하면서 그럴듯한 통계·일화·인용을 지어내지 않는다.
4. **보이스 드리프트** — 길어질수록 설교자 목소리가 일반 설교투로 흐려지기 쉽다(계기판 드리프트 점검).
5. **구어 이탈** — 원고가 논문·에세이체로 굳지 않게(논문체 계기판).
6. **긴장 평탄화 / eisegesis** — 살을 붙이며 긴장을 봉합하거나 적용이 본문을 넘지 않게.

## 4. 윤리 & 안전

- 전체 원고는 선택 — 개요로 충분한 설교자에겐 권하지 않는다. 영적 권위·sign-off는 설교자(`../../CLAUDE.md` 헌법).
- 대필 금지 · 본문 충실 > 시대 적합 · 회중 익명성 · 자산 로컬 처리.

## 5. Reference Links

- [references/expansion-method.md](./references/expansion-method.md) — 확장 방법론(섹션별 펴기·구어 register·보이스 유지).
- [templates/full_manuscript.example.md](./templates/full_manuscript.example.md) — 한 섹션 확장 예시(구어 register 모델).
- [templates/delivery_pack.example.md](./templates/delivery_pack.example.md) — 전달 준비물 산출 예시(언어 조정).
- `../../scripts/delivery_pack.py` — 전달 준비 측정(시간·섹션·낭독 보조) · `../../scripts/homiletic_audit.py` — 계기판.
- 상류: `skills/sermon-outline`(개요) · `scripts/outline_preflight.py`(brief).

---
*MS_Dev · TSPP · manuscript-expander v0.1 — 개요를 그 설교자의 구어 원고로 편다. 전체 원고는 선택이지 기본 아님. AI는 돕는다, 대필하지 않는다.*
