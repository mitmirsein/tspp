---
name: voice-ingest
description: 설교자 보이스 인제스트. 설교자가 자기 설교문 샘플 N편(권장 5~10)을 주면, 객관 문체 계량(stylometry) 위에서 개인 목소리 지문을 preacher_voice.json(L1-개인 보이스 카드) 초안으로 추출한다(HITL 승인 후 확정). AI 대필을 막는 안전장치 — 남의 문체가 아니라 설교자 자신의 문체를 학습해 되돌려준다.
version: 0.1.0
author: MS_Dev (TSPP)
triggers:
  - "#보이스"
  - "#보이스등록"
  - "#설교보이스"
  - "내 설교 문체 분석"
  - "설교자 보이스 추출"
  - "내 목소리 등록"
references_path: "./references"
---

# 🗣️ Voice Ingest 0.1 — 설교자 개인 보이스 추출

## 1. Overview

설교자가 **자기 설교문 샘플 N편**(권장 5~10)을 입력하면, 그 사람의 **개인 목소리 지문**을 `preacher_voice.json`(L1-개인 보이스 카드) *초안*으로 추출한다. 이후 설교 준비에서 이 카드가 L1-개인으로 주입된다.

> **제1원칙**: 이것은 *대필 도구가 아니라 대필 방지 장치*다. AI가 남의 매끈한 문체를 입히는 것을 막으려고, 설교자 자신의 문체를 학습해 되돌려준다. opt-in이며(미등록 시 호밀레틱 L1 보편 헌장만 — 정상 degraded), 추출본은 *초안*이고 HITL이 확정한다. 방법론 전체는 [voice-profiling.md](./references/voice-profiling.md).

## 2. 두 단계 — 측정과 해석 (환각 차단)

보이스 카드의 모든 차원은 **① 객관 측정값 + ② 실제 샘플 인용**에 정착해야 한다(TSPP 제1원칙의 보이스판). 근거 없는 인상비평("따뜻한 목소리") 금지.

```
1 측정  scripts/voice_ingest.py → voice_signals.json   (계량만, 지어내지 않음)
2 해석  이 스킬: 신호 + 샘플 인용 → preacher_voice.json 초안 (각 차원에 signal_basis)
3 승인  설교자 HITL 교정·확정 (approved=false → true)
```

## 3. Workflow — 4-Phase

### Phase 0 — Setup & Guardrail
- 제1원칙(대필 방지·opt-in) 로드. 입력 확인: 설교자가 제공한 `input/sermon_samples/`(.md/.txt).
- **프라이버시 고지**: 샘플·카드는 설교자 자산 — 로컬 처리, 외부 전송·학습 데이터화 금지.
- 샘플이 없으면 **먼저 청한다**. 백지에서 보이스를 *생성*하지 않는다(빈손이면 L1 보편 헌장 폴백을 안내).

### Phase 1 — 객관 계량 (Measurement)
샘플에서 문체 신호를 *측정*만 한다. 보이스를 해석하지 않는다.

```bash
python scripts/voice_ingest.py \
  --samples input/sermon_samples/ \
  --out output/<run>/voice_signals.json
```
- 산출 `voice_signals.json`: cadence(리듬)·rhetoric(수사)·register(종결)·lexicon(어휘대)·recurring_phrases.
- `coverage.status` 확인: `ok`(≥5) / `partial`(3~4) / `insufficient`(<3). partial·insufficient면 폴백 경고를 사용자에게 전달.

### Phase 2 — 해석·정착 (Profiling)
`voice_signals.json`을 읽고 **샘플 원문을 직접 대조**하며 `preacher_voice.json` 초안을 빚는다. [voice-profiling.md §4](./references/voice-profiling.md) 해석 규칙 준수:
- 각 차원(stance·lexicon·cadence·rhetoric·register·closing)에 `signal_basis`(어떤 측정에 근거했는지)를 단다.
- 시그니처 표현·수사 습관은 **실제 샘플 문장**을 근거로(인용은 카드 본문에 옮기지 않고, 출처 파일명은 `created_from`에).
- 신호 약한 차원은 **억지로 메우지 말고** `fallback.fell_back_to_L1`에 명시 → 보편 헌장으로.
- 스키마: [templates/preacher_voice.example.json](./templates/preacher_voice.example.json)

### Phase 3 — HITL 승인 (Confirmation)
- 설교자에게 카드를 차원별로 제시 → ✅승인 / ✏️교정 / ↻재추출 / ⏸보류.
- 설교자 교정을 반영해 `hitl.approved=true`로 확정. **승인 전까지 설교 작성 단계에 주입하지 않는다.**

## 4. Gotchas (피해야 할 함정)

1. **빈손 차원 메우기** — 가장 큰 죄. 신호 없으면 지어내지 말고 L1 폴백. `signal_basis` 없는 주장 금지.
2. **목소리 중성화** — 거친 구어·반복·사투리·특유 호명은 *결함이 아니라 지문*. "다듬어 더 좋게" 만들지 않는다.
3. **신학 강조 평탄화** — 무게중심(은혜/십자가/언약…)은 그 사람의 신학. 균형 강요로 흐리지 않는다.
4. **인상비평** — 측정·인용 없는 "따뜻한/힘찬 목소리" 류 금지. 모든 차원은 근거에 정착.
5. **자동 확정** — 추출은 초안. HITL 없이 카드를 확정·주입하지 않는다.
6. **회중 실명 유출** — 샘플 속 실명 일화는 카드·인용에 옮기지 않는다(익명화).

## 5. 윤리 & 안전 (목회 윤리 헌법 연동)

- 대필 금지 — 이 카드는 설교자 목소리를 *보존·증폭*하기 위한 것. 영적 권위·최종 sign-off는 설교자 귀속.
- 샘플·카드는 사용자 자산 — 로컬 처리, 외부 전송·학습 데이터화 금지.
- L1-개인은 **opt-in**. 미등록은 결함이 아니라 정상(호밀레틱 L1 보편 헌장으로 동작).

## 6. Reference Links

- [references/voice-profiling.md](./references/voice-profiling.md) — 방법론(측정 차원·해석 규칙·폴백·HITL·드리프트·학술 보이스와의 두 전도).
- [templates/preacher_voice.example.json](./templates/preacher_voice.example.json) — L1-개인 보이스 카드 스키마.
- `../../scripts/voice_ingest.py` — 객관 계량 엔진(순수 stdlib).
- `../../scripts/voice_resolve.py` — **소비측**: 추출 카드(L1-개인) + L1 보편 + L2 상황을 합성해 작성 단계 주입(`resolved_voice.json` + 강단 의례 injection_block).
- (자매 부품) `../../references/homiletic-voice.md`(L1 보편 헌장·폴백) ✅ · `../../data/homiletic_voice_palette.json`(L2-상황) ✅ — 보이스 3층 원칙. 보이스 3층 완성.

---
*MS_Dev · TSPP · voice-ingest v0.1 — TAWP authorial-voice의 설교 도메인 전도 + 객관 계량 정착. 보이스는 설교 개요(Phase 5) 진입 전에 L1-개인 + L2-상황으로 고정된다.*
