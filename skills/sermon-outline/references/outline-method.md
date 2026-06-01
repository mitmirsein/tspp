# 설교 개요 작성 방법론 (Outline Method)

> `sermon-outline` 스킬의 방법론 본체. SKILL.md는 흐름을, 이 문서는 *어떻게·왜*를 담는다.
> 설계: 보이스 고정 원칙(8-Phase)·§6(산출물). 상류: sermon-mentor(씨앗)·voice(3층)·TAWP fan-out(근거).

---

## 1. 무엇을 만드는가

`meditation_seed`(묵상 씨앗) + `resolved_voice`(고정 보이스) + (선택)`EvidencePack`(근거)를 받아 **본문에 충실한 설교 개요**(`sermon_outline.md`, 1~3쪽)를 빚는다. 이것은 설교 *준비*의 결정체이지 *대체*가 아니다 — 설교자의 묵상과 목소리를 본문 충실한 개요로 증폭하는 조력이다.

**왜 개요가 ★ 기본 산출인가**(개요 기본 산출 원칙): 전체 원고를 AI가 쓰면 대필 위험이 크다. 개요는 설교자가 *자기 입으로* 살을 붙일 뼈대다 — 준비를 돕되 강단의 말은 설교자의 것으로 남긴다. 전체 원고 확장은 *선택*이며 분리한다.

---

## 2. 정직성의 division — 스크립트와 에이전트

보이스 파이프라인과 같은 원칙이 작성에도 적용된다.

```
[수합·게이트]  scripts/outline_preflight.py  → writing_brief.json   (구조·게이트, 산문 아님)
[작성]         이 스킬(에이전트)               → sermon_outline.md   (개요 = 산문)
[점검]         scripts/homiletic_audit.py     → 비점수 worklist      (안전망)
```

스크립트는 게이트를 지키고 재료를 모은다. 개요(산문)는 에이전트가 쓰되, 다음 §3 규율에 정착한다. 점검은 작성 *후* 계기판으로.

---

## 3. 작성 규율 (writing_brief → 개요)

각 규율은 brief의 한 필드에 정착한다:

| 규율 | 정착 필드 | 위반 시 |
|---|---|---|
| **본문에 뿌리** | `meditation_core.rooted_in_text` · `message.text_anchor` | 논점이 본문 밖에서 오면 eisegesis |
| **유령인용 금지** | `evidence`(EvidencePack 레코드만) | 없는 문헌·통계·일화 = 환각 |
| **origin_memo 불가침** | `meditation_core.origin_memo` | 설교자 묵상 대체 = 대필 |
| **긴장 보존** | `tensions[].disposition` | 평탄화/강제개방 = 부정직 |
| **메시지 축** | `message.candidates`(확정안) | 산만·다초점 |
| **보이스 충실** | `voice.injection_block`·`lexicon_avoid`·`persona_ref` | 중성화·상투구 |
| **청중 음높이** | `audience_modulation` | 회중 무시 또는 추정 |

- **supporting_refs는 설교자 참고이지 강단 인용이 아니다.** 개요에 학자 이름을 나열하지 않는다 — 근거는 설교자가 *소화해* 본문을 비추게 하고, 출처는 개요 각주/메모로 내린다(L1 §3-① 강사화 경계).
- **eisegesis_risk가 high인 메시지**는 본문에 재정착하거나 제외한다(투명하게 사유 기록).

---

## 4. 보이스 주입 — 강단 의례 (Phase 1)

작성 진입 시, 첫 문장 전에 `voice.injection_block`을 자기에게 선언한다(원고엔 남기지 않음). 이는 homiletic-voice.md §5 의례의 실행이다:

1. L1 보편 — "본문 안에 서서 회중을 향해 돌아선 설교자. 채점하지 않는다(정죄는 '우리'). 결단을 제조하지 않고 청한다."
2. L1-개인(있으면) — 그 설교자 stance·시그니처.
3. L2-상황 — persona 어조 차용(견해 아님) + season 색 + 청중 음높이. components를 *한 문장 stance*로 렌더.
4. 그 자리로 끝까지 쓴다. 계기판은 작성 *후* 안전망.

---

## 5. 개요 구조 (sermon_outline.md)

`writing_brief.structure_hint` 순서. 본문장르(L2)에 따라 변주 — 내러티브는 재연 중심, 서신은 논증→권면, 탄식시는 함께 욺.

```
머리말        occasion(교회·예배·절기)
본문 · 제목
도입          회중을 본문 안으로 — 보이스대로(해설 아닌 거주)
논점 3–5      각 논점: 본문 뿌리 + 회중 접점; supporting_refs는 메모로
예화          본문장르·persona 어조에 맞게
적용          본문→오늘 이 회중(audience); 본문 왜곡 시 중단
긴장 보존     tensions를 살림(봉합/강제개방 금지)
결단·부름     tier에 맞게(전도=초청·제조금지 / 예언='우리' / 목회=동행)
기도·마무리
─ footer 메모  보이스 출처 · 근거(EvidencePack ref) · 계기판 결과 · eisegesis 판정
```

분량: 개요 1~3쪽(기본). 전체 원고(6~10쪽)는 선택·분리(manuscript-expander, 향후).

---

## 6. 게이트 (Phase 0·3·5)

- **Phase 0 진입 게이트**: `gates.ready`(씨앗·보이스 둘 다 HITL 승인). false면 작성 안 함.
- **Phase 3 Foundation Gate**: 본문 정합(binding) — 적용이 본문 왜곡 시 hard stop(본문 정합 hard gate). TAWP `binding_verifier` 정신.
- **Phase 5 sign-off**: 설교자 최종 승인. AI sign-off 절대 금지.

모든 Phase 사이 HITL 결정 카드(✅승인 / ↻돌아가기 / ✏️수정 / ⏸보류) — TAWP·sermon-mentor와 동일.

> **계기판 보정 주의**: `homiletic_audit`는 *구어 산문* 기준으로 보정됐다. 골격 개요(불릿·표제·괄호 메모)는 본래 종결비(hapnida)가 낮아 hapnida 기반 *강사화* 신호가 아티팩트일 수 있다. 개요의 **산문 단락**(도입·적용·결단·기도)을 기준으로 읽고, 전체 원고 확장 시 재점검한다. 단 *직접 호명·질문·기도의 결핍* 신호는 개요에도 유효하다(생명 표지).

---

## 7. 윤리 (목회 윤리 헌법 §8)

- **대필 금지** — 개요는 뼈대; 강단의 말은 설교자. AI는 돕는다.
- **본문 충실 > 시대 적합성** — 적용이 본문을 왜곡하면 차단.
- **회중 익명성** — 일화는 동의·익명화. 편향(정치·계층) redteam 차단.
- **자산 보호** — 씨앗·보이스·회중 정보 로컬 처리.

---

*MS_Dev · TSPP · sermon-outline — 씨앗+보이스+근거를 본문 충실 개요로. 스크립트는 게이트·수합, 에이전트는 개요, 계기판은 안전망.*
