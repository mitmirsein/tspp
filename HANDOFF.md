# TSPP 세션 인계 (HANDOFF)

> **목적**: 새 세션에서 이 한 파일만 가리키면 TSPP 작업을 이어받도록 묶은 자기완결 인계 문서.
> 작성 2026-05-29 | **갱신 2026-05-29** | 직전 작업: `git init` + `sermon-mentor` 골격 + fan-out vendoring (커밋 `8664ea8`)

---

## 0. 새 세션 시작 시 — 먼저 읽을 것

```
1. tspp/CONCEPT.md                                   ← 설계 본체 (v0.4, 자기완결)
2. tspp/HANDOFF.md                                   ← 이 파일
3. tspp/skills/sermon-mentor/SKILL.md                ← 첫 구현물(6-Phase 묵상 멘토)
4. tspp/skills/sermon-mentor/references/mentoring-homiletics.md  ← 산파술 방법론 상세
5. tspp/skills/sermon-mentor/templates/meditation_seed.example.json ← 산출 스키마
6. tspp/VENDOR.md                                    ← fan-out 엔진 출처(TAWP vendored)
7. (보이스/작성 단계 갈 때) ../Theology_Ontology_Starter/frameworks/homiletics.md · homiletics_compositor.md
```

> 경로 기준: `/Users/msn/Desktop/MS_Dev.nosync/projects/`. TSPP는 **공개 단독 레포**다 — 런타임에 TAWP·TOS에 의존하지 않는다(필요 부품은 vendoring).

---

## 1. 한 문장 정체성

TSPP = **"설교 파이프라인 신축"이 아니라, 주해·학술 리서치(TAWP 계보)와 설교 작성 엔진(TOS)을 잇고 그 위에 *묵상 멘토 + 설교자 보이스 + 목회 윤리* 층을 얹는 공개 단독 오케스트레이션 프로젝트.** 기초 원칙: **품질 높은 학술자료로부터 설교 인사이트를 획득**한다(LLM 일반론 금지).

---

## 2. 3-프로젝트 분업 (`CONCEPT.md §2.5`)

| 프로젝트 | 위치 | 역할 | TSPP와의 관계 |
|---|---|---|---|
| **TAWP** | `projects/tawp` | 주해·학술 리서치(fan-out 5엔진·binding·claim-ledger) | fan-out 부품을 **vendoring**(복사)해 옴 |
| **TOS** (v5.8) | `projects/Theology_Ontology_Starter` | 호밀레틱 *작성* 엔진(Decalogue 10종·Meta-Compositor·게이트·청중·다운스트림) | 향후 작성 단계 연결 대상 |
| **TSPP** ★ | `projects/tspp` | 묵상 멘토 + 오케스트레이션 + 보이스 + 목회 윤리 | 공개 단독 |

**✅ 확정된 사실 (이번 세션 도구 검증)** — 이전 ⚠️ 추정 해소:
- TOS `frameworks/`·`src/`·`data/`에 리서치 fan-out·설교자 보이스 *층* **없음 확인** → TSPP/TAWP의 몫이 맞다.
- TOS에 `lenses/` **18종**(reformed·lutheran·liberation·pentecostal·pastoral 등 *신학 관점 축*) 발견 — 설교자 보이스(L1/L2)와 **다른 축**이라 충돌 없음. 향후 L2-상황의 *관점 입력*으로 활용 여지.
- TAWP 재사용 부품 8종 모두 실재 확인(research_fanout·binding_verifier·claim_ledger·research-mentor·voice_palette·authorial-voice·tawp_audit·EvidencePack).

---

## 3. ★ 이번 세션 구현물 — sermon-mentor (TSPP의 출발점)

**정체성**: 설교자의 **최초 아이디어(본문/주제) + 기초 묵상 메모**를 받아 *경청·심화·발전*시키는 묵상 멘토. TAWP `research-mentor`의 설교 도메인 변형 — 결정적 차이는 **사용자가 빈손이 아니라 씨앗을 들고 온다**는 것. 제1원칙: **묵상은 증폭하되 대체하지 않는다**(메모리 `theology-meditation-seed`).

**6-Phase 흐름** (research-mentor 4-Phase + 학술 fan-out 통합):
```
0 가드레일 → 1 경청·반향 → 2 심화+키워드도출 → 3 학술 fan-out ★ → 4 자료 정착 → 5 메시지 후보 → 6 씨앗 산출(HITL)
```
- **순서 불변식**: fan-out(P3)은 반드시 경청(P1) *이후* — 자료가 처음 생각을 납치하지 않게.
- **품질 원칙**: 묵상·메시지 통찰은 LLM 일반론이 아니라 fan-out 자료에 `supporting_refs`로 정착(유령인용 차단).
- **산출 스키마 불변식**: `meditation.origin_memo` 불가침(읽기전용) · `tensions[].disposition`(open/resolving/resolved — 봉합도 강제개방도 금지) · `evidence`(EvidencePack 참조).
- **보이스(L2)는 여기서 안 잡음** — 설교 개요 진입 직전 확정(CONCEPT §5).

**fan-out (vendored, `VENDOR.md`)**: `scripts/research_fanout.py` + 4엔진(`kci`·`nlk`·`semantic-scholar`·`crossref`). **IxTheo 제외 → ko/en 2언어**. KCI/NLK는 `KCI_OPEN_API_KEY`·`NLK_SEARCH_API_KEY` 필요·uv 격리. S2/Crossref 키 불요.

---

## 3.5. ★ 구현물 — voice-ingest (설교자 L1-개인 보이스 추출)

**정체성**: 설교자가 자기 설교문 샘플 N편(권장 5~10)을 주면 **개인 목소리 지문**을 `preacher_voice.json`(L1-개인) 초안으로 추출(HITL 확정). `CONCEPT §4-5 (4)` 구현. **대필 방지 안전장치** — 남의 문체가 아니라 설교자 자신의 문체를 학습해 되돌려준다. opt-in(미등록은 호밀레틱 L1 보편 헌장 폴백).

**환각 차단 — 2단계 분리** (TSPP 제1원칙의 보이스판):
```
1 측정  scripts/voice_ingest.py → voice_signals.json   (순수 stdlib, 계량만)
2 해석  skills/voice-ingest: 신호+샘플 인용 → preacher_voice.json (각 차원 signal_basis)
3 승인  설교자 HITL 교정·확정
```
- **측정 차원**: cadence(리듬)·rhetoric(질문·호명·권면·성구밀도)·register(~습니다 vs ~다)·lexicon·recurring_phrases.
- **불변식**: 빈손 차원은 지어내지 말고 L1 폴백(`fallback.fell_back_to_L1`) · 모든 주장에 `signal_basis` · 목소리/신학강조 평탄화 금지 · 추출은 초안(HITL 전 주입 금지) · 샘플은 로컬 자산(외부 전송 금지).
- **coverage**: ok(≥5)/partial(3~4)/insufficient(<3) 자동 판정.

**산출물**: `scripts/voice_ingest.py` · `skills/voice-ingest/{SKILL.md, references/voice-profiling.md, templates/preacher_voice.example.json}`.

**✅ 검증 (이번 세션)**: py_compile 통과 · 실제 220 설교 7편 스모크 → coverage=ok, hapnida·성구밀도·신학무게중심·관용구 정상 산출. **실전 발견**: 220 폴더가 순수 설교+분석노트 혼합 → 관용구에 메타표현("총평 Homiletical Summary") 노출. 메커니즘이 코퍼스 오염을 *드러낸* 것(정상). Phase 2/HITL이 걸러야 함 → 방법론 §5("대표 설교만") 실증. registry.json은 fan-out 엔진 전용이라 voice-ingest 미등록(의도).

## 3.6. ★ 구현물 — homiletic-voice.md (설교자 L1 *보편* 헌장)

**정체성**: `references/homiletic-voice.md` — 모든 설교 보이스의 바닥이자 voice-ingest opt-out 폴백. TAWP `authorial-voice.md`의 **장르 전도판**. 핵심 명제: **"본문 안에 거주하면서 회중 앞에 선 설교자."**

**두 전도 구현**:
1. **L1 전도** — 학술이 금지하는 2인칭 호명·케리그마 선포·당위를 설교는 *요구*. 단 그 자유의 고유 위험(강사화·재판관화·본문 미끼·선동)을 §3 네 원칙으로 잡는다. 핵심 가드레일: 정죄는 '너희'가 아니라 **'우리'**로 향한다(설교자가 먼저 말씀 아래 선 첫 청중).
2. **계기판 전도(§6)** — 학술 `tawp_audit §8`이 *검출·경고*하는 호명·선포·당위를 **잡지 않는다**(설교의 생명). 정반대로 그 *결핍*(강사화)과 *부패*(재판관화·선동)를 본다. `voice_ingest.py` 신호를 호밀레틱으로 *재해석*(scripture_density↑+address↓+question↓=강사화 등). 전용 스크립트 `scripts/homiletic_audit.py`는 향후.

**3층 보이스 해석 순서**: ① preacher_voice.json(L1-개인) → ② homiletic_voice_palette(L2-상황) → ③ 둘 다 없으면 이 헌장만(정상 degraded). L1-개인은 이 헌장을 *덮지 않는다*("회중 채점"을 개인 보이스로 등록 불가 — 부패이지 개성이 아님). 보이스는 개요(Phase 5) 진입 전 고정.

**검증**: 구조·교차참조 정합 확인(voice-ingest SKILL §6·voice-profiling §9·preacher_voice.example.json l1_charter_ref 모두 일치). 미커밋.

## 3.7. ★ 구현물 — homiletic_voice_palette.json (L2-상황) → 보이스 3층 완성

**정체성**: `data/homiletic_voice_palette.json` — 이 설교의 register. 학술 `voice_palette.json`의 전도판. **결정적 차이: 학술은 단일 축(주제별 톤)이지만 호밀레틱 L2는 4축 합성**(본문장르 × tier × 절기 × 청중, CONCEPT §4-5).

**4축**:
- **text_genre**(1차 결정자, 7종): narrative·gospel_parable·law_torah·wisdom·psalm_lament·epistle·prophetic_apocalyptic. 각 native_register·cadence·**watch**(homiletic-voice §6 부패 연결).
- **tier**(5종, CONCEPT): expository·prophetic·pastoral·evangelistic·catechetical. 각 tier의 상시 위험 명시(교리=강사화, 전도=선동, 예언=재판관화…).
- **season**(9종, 교단중립): advent~thanksgiving. register_color + watch.
- **audience_modulation**: ★ **프리셋 아님** — 헌법(AI 회중 추정 금지). audience_profile.json 있을 때만 활성, 없으면 보편 폴백. 조율 지침(정서·신앙색채·상황·예전위치·연령)만 제공.

**핵심 불변식**: ① 모든 값은 L1 보편을 *공유*하는 register 변주 — "회중 채점"을 register로 가질 수 없음(부패이지 변주 아님). ② conflict_rule: 축 충돌 시 **text_genre 우선**(절기가 본문 안 덮음 — 부활절+탄식시 예시). ③ 신학전통(TOS lenses)은 register와 *직교축* — 4축에 미포함(HANDOFF §2 확인). ④ persona는 *어조 차용원* 5종(§3.9)이며 tier에 정렬·tspp 자체 파일(TAWP/TOS 런타임 의존 아님). ⑤ `scripts/voice_resolve.py`가 소비(§3.8). composition_examples 3개로 합성 시연.

**검증**: JSON 유효 · 4축 구조·예시 확인 · 교차참조 갱신(SKILL §6·voice-profiling §9). 미커밋.

## 3.8. ★ 구현물 — voice_resolve.py (추출→주입 연결: 보이스 3층 합성)

**정체성**: `scripts/voice_resolve.py` — 추출(voice_ingest)과 작성(Phase 5)을 잇는 *소비측*. L1 보편 + L1-개인(opt-in) + L2-상황(4축)을 합성해 `resolved_voice.json` + 사람이 읽는 `injection_block`(강단 의례 §5)을 산출. CONCEPT 부록 `voice_resolve.py` 구현.

**설계(voice_ingest와 동일한 정직성)**: **스크립트는 구조만 합성, 산문 렌더는 에이전트의 강단 의례에서.** L2 stance를 스크립트가 짓지 않고 components(genre native_register / tier tightens / season color / audience modulation / cadence)를 모아 `render_hint`로 넘긴다.

**불변식**: ① L1 보편은 **항상 바닥**(charter_ref + core 선언). ② preacher_voice 미제공=정상 degraded(L1보편+L2만), 미승인(hitl.approved=false)=⚠️경고+주입 차단. ③ 청중 축은 audience_profile 있을 때만 활성(헌법: 추정 금지). ④ conflict_rule: text_genre 우선(부활절+탄식시 자동 감지). ⑤ lexicon_avoid = L2 + L1-개인 회피 병합 · watch = genre+tier+season 병합(homiletic-voice §6 계기판). ⑥ 산출은 HITL 승인(approved=false) 전 주입 금지. 순수 stdlib.

**✅ 검증 (4 시나리오)**: A)3층 완성(승인 preacher_voice+audience, lent+lament 충돌없음) · B)degraded(L1개인·청중 없음) · C)conflict_rule(easter+lament→genre 우선 자동) · D)미승인 경고 + 잘못된 키 에러(valid 목록 반환, exit 2). 전 출력 JSON 유효 · `-W error::SyntaxWarning` 0건.

## 3.9. ★ 구현물 — personas/Preacher_*.md 5종 (어조 차용원)

**정체성**: `personas/Preacher_{Expositor,Prophet,Pastor,Evangelist,Catechist}.md` — L2 팔레트의 *어조 차용원*(tone source). CONCEPT §4-5 "Preacher_*.md 5종" 구현. **persona = 설교 직임 = tier 5종과 정렬**(강해자·예언자·목자·전도자·교사) — 각 persona가 그 tier의 깊은 음성 초상.

**배선(팔레트)**: `axes.tier[].persona_ref` → 해당 파일 / `axes.text_genre[].tone_affinity` → 장르가 빌리는 어조(persona key 배열; 옛 가짜 라벨 "Narrative_Preacher" 등 7개 전부 교체) / 새 top-level `personas.set`(5종 인덱스: key·tier·file·voice·risk). `voice_resolve.py`가 tier→persona_ref·genre→tone_affinity 를 components·injection_block에 노출("어조 차용원: …  ※어조만 차용, 견해 아님").

**불변식**: ① **어조만** 차용 — 견해·신학입장·교파교의 인용 아님. ② 모두 L1 보편 공유하는 register 변주(정체성 아님 — '회중 채점' 불가). ③ L1 보편 위, L1-개인 아래(덮지 못함). ④ 각 persona의 *고유 위험*을 homiletic-voice §6·tier.watch와 연결(강해자/교사=강사화, 예언자=재판관화·정치편향, 목자=본문미끼, 전도자=선동).

**검증**: 5 파일 존재 · 팔레트 무결성(tier persona_ref ⊆ 파일, genre tone_affinity ⊆ persona key) · resolver 노출 확인 · 가짜 라벨 0건 · JSON·py 0경고. 미커밋.

## 3.10. ★ 구현물 — homiletic_audit.py (호밀레틱 보이스 계기판)

**정체성**: `scripts/homiletic_audit.py` — homiletic-voice.md §6 계기판. 학술 `tawp_audit §8`의 **전도**. **비점수 HITL worklist**("다시 읽어보라" 신호, pass/fail·게이트 아님). 측정은 `voice_ingest.py` 재사용(import, DRY).

**전도 핵심**: 학술 audit이 *검출·경고*하는 직접 호명·케리그마 선포·권면·기도 종결을 **잡지 않는다**(설교의 생명) — 그 *결핍*이 경보다. 잡는 것: ① **강사화**(호명·질문 결핍 + 주석밀도↑ + 문어체화 + 강의투 표지) ② **재판관화**(2인칭 정죄 + *함의형* '우리'(우리도/우리 역시) 결핍 — 우발적 '우리에게'는 연대로 안 침) ③ **강단 상투구**(은혜가 되시기 바랍니다 等) ④ **논문체 전이**(되어진다·다름 아니다·본고 等, TAWP §2.1 이식). + 선택: `preacher_voice.json` 드리프트(문어체화·시그니처 소실) · `resolved_voice.json` lexicon_avoid 출현 점검.

**설계 편향**: 보수적(false-negative 지향) — 정당한 설교 어법 오탐 방지가 1순위. 비점수라 임계는 신호 점등용.

**✅ 검증 (3 시나리오)**: A)건강한 실제 설교(눅17) → **0 신호**(정당 호명·선포·'우리도' 연대 정상 통과 = 전도 핵심 검증) · B)부패 초안 → 4부패 전부 점등(강사화·재판관화·상투구·논문체) + 결핍 2 · C)드리프트 초안 → 시그니처 소실 + 회피표현 2 출현 포착. 전 출력 JSON 유효 · py 0경고. 미커밋.

## 3.11. ★ 구현물 — audience_profile.example.json (회중 컨텍스트 스키마)

**정체성**: `data/audience_profile.example.json` — 회중 프로파일 스키마·예시(CONCEPT §4-2). 실제 파일은 `input/audience_profile.json`(목회자 작성·gitignore 비공개). 두 곳에 먹힘: ① L2 보이스 음높이·구체성(voice_resolve audience 축) ② 적용 매핑.

**5차원**(= voice_resolve `AUDIENCE_KEYS`와 일치): affect(정서·분위기)·faith_texture(신앙색채)·situation(상황)·liturgical_setting(예배종류+시리즈위치; ※절기는 --season 별도 축)·age(인구학). 각 `{value, _comment}`.

**불변식(헌법 §8)**: ① **목회자 작성 — AI 추정 금지**(빈 차원=보편 폴백, AI가 안 채움). ② 회중 익명성 — 식별 가능 개인·실명 일화 금지, 집합 묘사만. ③ 로컬 자산(외부 전송 금지). ④ 적용 왜곡·정치편향 정당화 금지(redteam 별도).

**resolver 보강**: voice_resolve가 audience 값을 `{value,...}` 객체/문자열 둘 다 수용(노이즈 키 _comment/usage/ethics 등은 AUDIENCE_KEYS 밖이라 자동 무시).

**✅ 검증**: JSON 유효 · 5차원 ⊆ AUDIENCE_KEYS · 노이즈 키 0 픽업 · 객체형 audience로 resolve 청중 조율 정상 · py 0경고. 미커밋.

## 3.12. ★ 구현물 — 작성 단계 연결 (outline_preflight.py + sermon-outline 스킬)

**정체성**: 묵상 씨앗 + 보이스 + 근거 → **본문 충실 설교 개요**. 보이스/멘토를 *실제 설교*로 잇는 고리(CONCEPT §5 Phase 5→7→8). `scripts/outline_preflight.py` + `skills/sermon-outline/{SKILL.md, references/outline-method.md, templates/sermon_outline.example.md}`.

**고리**:
```
meditation_seed(HITL) + resolved_voice(HITL) + EvidencePack(선택)
  → outline_preflight.py (게이트+writing_brief 수합)  → [sermon-outline 스킬: 의례·작성]
  → sermon_outline.md  → homiletic_audit.py (계기판)  → HITL sign-off
```

**정직성 division(파이프라인 일관)**: outline_preflight = 게이트·수합(산문 아님) / 개요(산문) = 에이전트 / 점검 = homiletic_audit. **게이트**: 씨앗·보이스 둘 다 hitl.approved=true 라야 `gates.ready` — 아니면 작성 차단.

**작성 규율(brief 필드 정착)**: 본문 뿌리(rooted_in_text·text_anchor) · 유령인용 금지(EvidencePack 레코드만) · origin_memo 불가침 · 긴장 보존(disposition) · 보이스 충실(injection_block·lexicon_avoid·persona 어조차용) · 청중 음높이. supporting_refs는 설교자 참고이지 강단 인용 아님(강사화 경계). eisegesis_risk high는 재정착/제외. **AI는 돕는다 — 대필 금지**(개요가 ★기본; 전체 원고는 선택·분리).

**계기판 보정 주의**: homiletic_audit는 *구어 산문* 기준 — 골격 개요는 hapnida 낮아 강사화 아티팩트 가능. 산문 단락(도입·적용·결단·기도) 기준으로 읽고 원고 확장 시 재점검. 단 호명·질문·기도 *결핍* 신호는 개요에도 유효.

**✅ 검증**: preflight READY/BLOCKED 게이트 · brief 수합(origin_memo·eisegesis_risk·긴장·injection_block·청중5차원) · 예시 개요 계기판 **0 신호**(호명 추가 후) · **전체 파이프라인 종단**(ingest→resolve→preflight→audit) 통과 · py 0경고. 미커밋.

## 3.13. ★ 구현물 — 목회 윤리 헌법 3파일 (CLAUDE/AGENTS/GEMINI.md)

**정체성**: `CLAUDE.md` = `AGENTS.md` = `GEMINI.md`(동일, md5 일치) — tspp 루트. CONCEPT §8 구현. 그간 스킬·스크립트 12곳이 "목회 윤리 헌법"을 *참조*했으나 실물이 없던 **정합성 공백을 메움**. 우리가 구현한 불변식들을 한 헌법으로 묶음.

**12조**: 0)준비도구·대체 아님 1)대필 금지 2)권위 귀속·HITL 3)본문충실>시대적합(eisegesis hard gate) 4)origin_memo 불가침 5)보이스=대필방지(회중 채점 금지·정죄는 '우리'·persona 어조만) 6)아포리아 보존 7)유령인용 금지·출처신중 8)회중 목회자입력·익명·편향차단 9)프라이버시 로컬 10)신학분별 worklist(판단은 목회자) 11)개발수칙(단독레포·stdlib·스크립트≠산문·머신로컬git·검증정직) 12)언어·태도.

**검증**: 3파일 md5 동일 · diff 0 · "헌법" 참조 12파일이 실물을 가리킴. 미커밋.

## 3.14. ★ 구현물 — manuscript-expander (개요 → 전체 원고, 선택)

**정체성**: 승인된 개요 → 보이스 충실 **전체 구어 원고**(`full_manuscript.md`, 6~10쪽). 작성 arc 완결. `scripts/delivery_pack.py` + `skills/manuscript-expander/{SKILL.md, references/expansion-method.md, templates/full_manuscript.example.md, templates/delivery_pack.example.md}`. CONCEPT §5 Phase 7·§6(**선택** 산출 — 기본은 개요).

**고리**: `sermon_outline.md(approved)` + brief + resolved_voice → [의례·확장] → full_manuscript.md → `delivery_pack.py`(시간·섹션·낭독보조) + `homiletic_audit.py`(계기판) → HITL.

**제1원칙**: **펴는 것이지 새로 쓰는 게 아니다.** 개요의 논리·구조·보이스를 구어로 펼 뿐 새 논점·메시지·일화 무첨가(대필 미끄러짐 차단). 전체 원고는 ★기본 아님 — 개요로 충분하면 권하지 않음.

**정직성 division**: delivery_pack=측정(시간·섹션 배분·낭독 보조) / 원고·delivery_pack.md=에이전트 / 계기판=homiletic_audit. **전체 원고는 구어 산문이라 계기판이 정밀**(개요의 hapnida 아티팩트 없음).

**delivery_pack.py(전달 준비물)**: ① 전체+**섹션별** 시간(±15% under/on/over, 40% 쏠림 점검) ② **낭독 보조**(긴문장 호흡·원어 발음[그리스어/히브리어 자동검출, 예 πτωχός→풀어말하기]·숫자 읽기·긴 어절). 측정만 — `delivery_pack.md`(언어 조정 산문)는 에이전트가 정리(templates/delivery_pack.example.md).

**✅ 검증**: delivery_pack(섹션 배분·그리스어 πτωχός 발음보조·숫자 검출·쏠림 신호 정상) · 예시 원고 계기판 **0 부패**(부분 발췌라 기도결핍 1은 정확) · py 0경고. 미커밋.

---

## 4. 설교자 보이스 아키텍처 (`CONCEPT.md §4-5` — ✅ **3층 완성 + 주입 연결**: L1보편·L1개인·L2상황·resolve)

TAWP 보이스 2층(L1 헌장 + L2 팔레트 + 계기판)의 *장르 이식*. **두 전도(inversion)**:
1. **L1은 복사 아닌 전도** ✅ **구현 완료**(§3.6 `references/homiletic-voice.md`) — 학술이 금지하는 것(2인칭 호명·케리그마 선포·권면)을 설교는 요구. `tawp_audit §8`(학술 시점 검출) 재사용 불가 → 전도된 계기판.
2. **축이 이중** ✅ **구현 완료**(§3.6 L1-보편 + §3.7 L2-상황) — L1-개인(설교자 동일성, opt-in, `preacher_voice.json`) + L2-상황(본문장르×tier×절기×청중 4축, `data/homiletic_voice_palette.json`).
3. **보이스 인제스트** ✅ **구현 완료** (§3.5) — 설교문 샘플 5~10편 → 문체 프로파일링 → `preacher_voice.json` 초안 → HITL. 대필 방지의 실물 메커니즘.
4. **회중 컨텍스트 심화** ★ — 연령+신앙색채·정서·상황·예전 위치를 `audience_profile.json`에. **목회자 작성(AI 추정 금지).**

---

## 5. 결정 현황 (forks — `CONCEPT.md §12`)

**✅ 이번 세션 확정:**
- **F5(상류 결합)** = **공개 단독 → vendoring**. 런타임 외부 의존 금지. fan-out 부품을 TSPP로 복사.
- **F10(즉시 액션)** = **sermon-mentor 우선**(옵션 B 변형). + fan-out을 멘토 단계에 통합.
- **엔진**: KCI·NLK·Semantic Scholar·Crossref 4종(IxTheo 제외, ko/en).
- **묵상 산출**: origin_memo 불가침 / 메시지 후보 형성까지 멘토 책임 / 보이스는 개요 직전 / 긴장은 출구 열린 disposition.

**⬜ 미결 (사용자 판단 대기):**
- **F11 개인 보이스**: opt-in(권장)/필수/미지원 · 등록=인제스트 추출(1순위)
- ~~**TAWP↔TOS 브리지 어댑터**~~ → **폐기**(§6.3): F5 단독 원칙 모순 + 네이티브 작성으로 대체. vendoring만 선택지.
- 그 외 F1(프로젝트명)·F2(분량)·F3(회중 깊이)·F4(렉셔너리)·F6(예화)·F7(윤리 강도)·F8(한국교회)·F9(첫 PoC 본문)

---

## 6. 현 상태 / 다음 액션

**현 상태**: 다른 맥 tspp 레포 = `main`, 커밋 `8664ea8`(sermon-mentor 골격 + fan-out vendoring). 이 맥에서 **설교 준비 파이프라인 전체 신규 구현·종단 검증 완료 — 전부 미커밋**(§3.5~3.14): 보이스 아키텍처(추출·L1보편·L2 4축·페르소나5·주입·계기판·회중스키마) + 작성 연결(개요·원고·전달준비물) + 목회 윤리 헌법. 종단(ingest→resolve→preflight→audit→delivery_pack) 통과. 정적 검증(JSON·py_compile·SyntaxWarning 0).

---

### 6.1 ⚠️ 커밋은 **다른 맥(git 머신)**에서 — 안내

**왜 이 맥에선 못 하나**: `.stignore`가 `**/.git`를 Syncthing 제외 → `.git`은 머신별. 이 맥(작성 머신)엔 tspp `.git` 없음(상위 MS_Dev 레포는 `projects/` ignore). 여기서 `git init`하면 `8664ea8`과 무관한 별개 루트가 생겨 **영영 분기**한다. → **결정: 다른 맥에서 커밋**(2026-05-30 사용자 확정).

**절차**(파일은 Syncthing이 git 머신으로 이미 전파 — `.git` 제외, 작업 파일만). 그 맥에서 `8664ea8` 위에 그대로 실행:

```bash
cd <tspp>                       # .git 있는 맥
git status                      # 신규 파일 확인 (input/·sermon_samples/ 는 .gitignore → 자동 제외)
git add scripts/voice_ingest.py scripts/voice_resolve.py scripts/homiletic_audit.py \
        scripts/outline_preflight.py scripts/delivery_pack.py \
        references/homiletic-voice.md \
        data/homiletic_voice_palette.json data/audience_profile.example.json \
        personas/ skills/voice-ingest/ skills/sermon-outline/ skills/manuscript-expander/ \
        CLAUDE.md AGENTS.md GEMINI.md HANDOFF.md
git commit -F - <<'MSG'
feat(sermon-prep): 설교 준비 파이프라인 — 보이스 3층 + 작성 연결 + 윤리 헌법

CONCEPT §4-5 보이스 아키텍처 + §5 작성 연결 (TAWP authorial-voice의 설교 도메인 전도).
묵상 씨앗 → 보이스 → 개요 → 원고 → 전달준비물까지 종단. AI는 돕는다 — 대필 금지.

보이스 아키텍처(§3.5~3.11):
- voice-ingest + voice_ingest.py: 설교문 샘플 → 객관 계량 → preacher_voice.json
  (L1개인) 추출(HITL). 대필 방지 안전장치.
- references/homiletic-voice.md: L1 보편 헌장(본문 안 거주+회중 전향).
- data/homiletic_voice_palette.json: L2-상황(본문장르×tier×절기×청중 4축).
- personas/Preacher_*.md 5종: 어조 차용원(tier 정렬, 어조만·견해 아님).
- scripts/voice_resolve.py: 3층 합성→주입(injection_block, HITL 게이트).
- scripts/homiletic_audit.py: 계기판(tawp_audit §8 전도, 비점수 worklist).
  호명·선포·권면은 안 잡고 강사화·재판관화·상투구·논문체를 본다.
- data/audience_profile.example.json: 회중 스키마(목회자 작성·익명·로컬).

작성 연결(§3.12·3.14):
- scripts/outline_preflight.py + sermon-outline: 씨앗+보이스+근거 → 게이트·수합
  → 본문 충실 개요 → 계기판 → HITL.
- scripts/delivery_pack.py + manuscript-expander: 개요 → 전체 구어 원고(선택)
  + 전달 준비물(시간·섹션 배분·낭독 보조). 펴는 것이지 새로 쓰기 아님.

목회 윤리 헌법(§3.13):
- CLAUDE/AGENTS/GEMINI.md 12조(동일 3파일, CONCEPT §8).

순수 stdlib·헌법 준수(대필 금지·청중 추정 금지·로컬 처리). 종단 검증 통과.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
MSG
```

- **포함**: 위 git add 목록(스크립트 5·헌장·데이터 2·페르소나·스킬 3·헌법 3·HANDOFF).
- **제외(정상)**: `input/`·`sermon_samples/`(목회자 자산)·`output/`·`.venv*`·`.DS_Store` — 모두 .gitignore.
- **분할 옵션**: 한 커밋이 크면 ① 보이스(§3.5~3.11) ② 작성연결(§3.12·3.14) ③ 헌법(§3.13) 셋으로 나눠도 됨. 한 커밋도 무방(한 기능 arc).
- **검증 권장**(커밋 후, 그 맥에서): `python3 -W error::SyntaxWarning -m py_compile scripts/*.py` · JSON 로드 · `diff CLAUDE.md AGENTS.md`.

### 6.2 남은 후보 (선택)
- **fan-out 실네트워크 검증** — `uv sync`(kci/nlk) + API 키 후, S2/Crossref(키 불요)로 한 본문 검색 → EvidencePack 생성 확인. (⚠️ 실제 네트워크 미검증)
- **sermon-mentor 실사용 1사이클** — 실제 본문+묵상으로 6-Phase 돌려 거친 곳 다듬기.
- (선택) TTS 리허설 오디오 · delivery_pack 분당 글자수 설교자 보정값 수집.

### 6.3 폐기된 방향
- **TAWP↔TOS 브리지**(2026-05-30 폐기): F5(공개 단독·런타임 외부의존 금지) 모순 + 작성 엔진을 TSPP 네이티브로 구축해 불필요. 단독 패턴 = **리서치 vendoring · 작성 네이티브**. TOS Decalogue 필요 시 *브리지*가 아니라 *vendoring*만 선택지. CONCEPT §11 옵션C·부록 `bridge_evidence_to_ontology.py`는 superseded(이 HANDOFF가 최신).

---

## 7. 원본 메모리 (참고)

`/Users/msn/.claude/projects/-Users-msn-Desktop-MS-Dev-nosync-projects-tawp/memory/tspp-sibling-project-voice-architecture.md`
관련: `tawp-authorial-voice-architecture.md` (TAWP 보이스 구조 — 이식 원본). 본 세션 결정(공개 단독·vendoring·fan-out 멘토 통합·4엔진)은 이 HANDOFF가 최신.
