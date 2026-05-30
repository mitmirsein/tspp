# TSPP 사용 매뉴얼 (Operating Manual)

> **TSPP** = Theology Sermon Preparation Pipeline — 설교 *준비*를 돕는 단독 오케스트레이션 도구.
> **돕되, 대체하지 않는다.** 강단의 말과 영적 권위는 설교자의 것이다(→ [`CLAUDE.md`](./CLAUDE.md) 목회 윤리 헌법).
> 이 문서는 *실제로 돌리는 법*을 다룬다. 설계 근거는 `CONCEPT.md`, 세션 인계는 `HANDOFF.md`.

---

## 0. 한눈에 — TSPP가 하는 일

설교자의 **처음 묵상**을 받아, 검증된 학술 자료로 심화하고, 설교자 자신의 **목소리**를 보존하며,
**본문에 충실한 개요(→ 선택적으로 전체 원고)**까지 함께 빚는다. 매 단계 **사람(설교자)이 승인(HITL)**해야 다음으로 넘어간다.

```
묵상 메모 ──▶ ① 묵상 멘토 ──▶ meditation_seed (HITL)
                  │                       │
  설교문 샘플 ─▶ ② 보이스 추출 ─┐         │
                              ▼          ▼
                  ③ 보이스 합성 ──▶ resolved_voice (HITL)
                              │          │
                              ▼          ▼
                  ④ 개요 프리플라이트 게이트 ──▶ writing_brief
                              ▼
                  ⑤ 설교 개요 작성(에이전트) ──▶ sermon_outline (계기판→HITL)
                              ▼  (선택)
                  ⑥ 전체 원고 확장 + 전달 준비물 ──▶ full_manuscript (계기판→HITL)
```

핵심 분업 — **스크립트는 측정·게이트·구조 합성만, 산문(묵상·개요·설교)은 에이전트, 확정은 설교자(HITL).**
스크립트가 설교문을 지어내지 않는다.

---

## 1. 사전 준비

### 1.1 런타임
- **Python 3 (stdlib만)** — 핵심 스크립트(`voice_ingest`·`voice_resolve`·`outline_preflight`·`homiletic_audit`·`delivery_pack`)는 외부 패키지가 **0**이다. 추가 설치 없이 바로 실행.
- **fan-out 검색 엔진**만 별도 환경/키가 필요(아래 1.3).

### 1.2 디렉터리 구조

```
tspp/
├─ CLAUDE.md · AGENTS.md · GEMINI.md   목회 윤리 헌법 12조 (동일 3파일)
├─ CONCEPT.md                          설계 본체
├─ HANDOFF.md                          세션 인계
├─ MANUAL.md                           ← 이 문서
├─ VENDOR.md                           fan-out 엔진 출처(TAWP vendored)
├─ scripts/                            stdlib 측정·게이트 스크립트
│   ├─ voice_ingest.py   voice_resolve.py   homiletic_audit.py
│   ├─ outline_preflight.py   delivery_pack.py
│   └─ research_fanout.py  evidence_collect.py  query_expand.py
├─ skills/                             에이전트 스킬(작성·멘토링 의례)
│   ├─ sermon-mentor/  voice-ingest/  sermon-outline/  manuscript-expander/
│   ├─ registry.json                  fan-out 엔진 단일 진실 소스(4엔진)
│   └─ kci-api-searcher/ nlk-biblio-searcher/ semantic-scholar/ crossref-journal-searcher/
├─ personas/                          Preacher_{Expositor,Prophet,Pastor,Evangelist,Catechist}.md
├─ references/homiletic-voice.md      L1 보편 보이스 헌장
├─ data/                              homiletic_voice_palette.json · audience_profile.example.json
├─ input/        ⚠️ 비공개(.gitignore) — 묵상 메모·설교 샘플·회중 프로파일
└─ output/       ⚠️ 비공개(.gitignore) — 실행 산출물(run별)
```

> **`input/`·`output/`·`sermon_samples/`는 설교자 자산**이라 버전관리에서 제외된다(외부 전송 금지·로컬 처리).
> 실행 전 직접 만든다: `mkdir -p input output`.

### 1.3 fan-out 검색 엔진 (선택 — 묵상 멘토 Phase 3에서만)

`skills/registry.json`의 4엔진:

| 엔진 | 언어 | 키 | 격리 |
|---|---|---|---|
| `semantic-scholar` | en | **선택** `S2_API_KEY`(없으면 public rate limit, 있으면 한도 상향) | 없음(stdlib) |
| `crossref-journal-searcher` | en | 불요 | 없음 |
| `kci-api-searcher` | ko | **필수** `KCI_OPEN_API_KEY` | uv |
| `nlk-biblio-searcher` | ko | **필수** `NLK_SEARCH_API_KEY` | uv |

- **키 종류 두 가지** — `registry.json`의 `env`(필수: 없으면 `research_fanout`이 해당 엔진을 자동 스킵 = degraded) vs `env_optional`(선택: 없어도 동작, 있으면 rate limit만 상향).
- **필수 키**는 KCI·NLK뿐. 한국어 엔진을 쓰려면 키를 셸 환경변수로 export(예: `dev/.env`)하고 해당 스킬에서 `uv sync`.
- **S2는 키 없이도 동작**한다 — 호출이 잦거나 429가 잦으면 `S2_API_KEY`를 export해 한도를 올린다(`s2_runner.py`가 `x-api-key` 헤더로 인증).
- 빠르게 시작하려면 키 불요인 Crossref + (키 없는) S2만으로 충분하다.

### 1.4 머신·git 주의 (Syncthing 환경)
- `.git`과 `.venv*`는 **머신 로컬**(`.stignore`로 Syncthing 제외). 한 맥의 환경/레포를 다른 맥과 공유하지 않는다.
- 커밋은 `.git`을 보유한 머신에서만 한다(→ `HANDOFF.md §6.1`).

---

## 2. 전체 파이프라인 — 단계별 실행

아래에서 `<run>`은 이번 설교의 작업 폴더명(예: `2026-pentecost-acts2`). 모든 산출은 `output/<run>/`에 모은다.

```bash
RUN=2026-pentecost-acts2
mkdir -p output/$RUN
```

### ① 묵상 멘토 — `meditation_seed.json`

설교자의 **본문/주제 + 기초 묵상 메모**를 멘토에게 준다. 에이전트가 6-Phase로 진행한다:

```
0 가드레일 → 1 경청·반향 → 2 심화+키워드도출 → 3 학술 fan-out → 4 자료 정착 → 5 메시지 후보 → 6 씨앗 산출(HITL)
```

- 스킬 트리거: `#묵상`, `#설교멘토`, `이 본문으로 묵상`, `묵상 메모 발전` → `skills/sermon-mentor/SKILL.md`
- **반드시 묵상 메모를 먼저 낸다.** 메모 없이 백지에서 메시지를 생성하지 않는다.
- Phase 3 학술 fan-out(선택, **경청 이후에만**):

```bash
python scripts/research_fanout.py "<본문/주제>" \
  --engines semantic-scholar,crossref-journal-searcher \
  --parallel --out output/$RUN/EvidencePack.json
# 한국어 엔진까지: --engines kci-api-searcher,nlk-biblio-searcher,semantic-scholar,crossref-journal-searcher
```

- 산출 `meditation_seed.json`은 **설교자 승인(`hitl.approved=true`) 전 다음 단계로 넘기지 않는다.**
- 스키마: `skills/sermon-mentor/templates/meditation_seed.example.json`
- 불변식: `origin_memo` 불가침(읽기전용) · 긴장은 `disposition`(open/resolving/resolved)으로 정직하게 · 근거는 EvidencePack 실제 레코드만.

### ② (선택·opt-in) 설교자 보이스 추출 — `preacher_voice.json`

자기 설교문 샘플 5~10편을 주면 **개인 목소리 지문**을 추출한다(대필 방지 안전장치).
샘플은 `input/sermon_samples/`(비공개)에 둔다.

```bash
# 1단계: 객관 신호 계량 (순수 stdlib)
python scripts/voice_ingest.py --samples input/sermon_samples/ \
  --out output/$RUN/voice_signals.json
```

- 2단계: 에이전트(`skills/voice-ingest`)가 신호+샘플 인용으로 `preacher_voice.json` 초안 작성(각 차원 `signal_basis`).
- 3단계: 설교자 HITL 교정·확정.
- **등록 안 해도 됨** — 미등록이면 L1 보편 헌장(`references/homiletic-voice.md`)으로 폴백(정상 degraded).
- coverage: ok(≥5)/partial(3~4)/insufficient(<3) 자동 판정. 샘플은 *대표 설교만*(분석노트 혼합 주의).

### ③ 보이스 합성 — `resolved_voice.json`

L1 보편 + L1-개인(있으면) + L2-상황(본문장르×tier×절기×청중 4축)을 합성한다.

```bash
python scripts/voice_resolve.py \
  --genre psalm_lament --tier pastoral --season lent \
  --preacher-voice output/$RUN/preacher_voice.json \   # 선택(opt-in)
  --audience input/audience_profile.json \             # 선택(목회자 작성)
  --out output/$RUN/resolved_voice.json
```

- `--genre` 7종: `narrative` `gospel_parable` `law_torah` `wisdom` `psalm_lament` `epistle` `prophetic_apocalyptic`
- `--tier` 5종: `expository` `prophetic` `pastoral` `evangelistic` `catechetical`
- `--season` 9종: `advent`~`thanksgiving`(교단중립)
- **충돌 규칙**: 축이 충돌하면 **text_genre 우선**(절기가 본문을 덮지 않음. 예: 부활절+탄식시 → 장르 우선, 자동).
- **청중 축**은 `audience_profile.json`이 있을 때만 활성(AI가 회중을 추정하지 않는다 — 헌법 §8).
- 산출에 사람이 읽는 `injection_block`(강단 의례에서 선언할 보이스)이 포함된다. **HITL 승인 전 주입 금지.**
- 잘못된 키를 주면 유효 목록을 반환하고 종료한다(exit 2).

> 회중 프로파일을 쓰려면 `data/audience_profile.example.json`을 복사해 `input/audience_profile.json`으로 채운다.
> **목회자가 작성**한다(5차원: affect·faith_texture·situation·liturgical_setting·age). 익명·집합 묘사만.

### ④ 개요 프리플라이트 게이트 — `writing_brief.json`

씨앗과 보이스가 **둘 다 승인**됐는지 검증하고 작성 brief를 수합한다.

```bash
python scripts/outline_preflight.py \
  --meditation-seed output/$RUN/meditation_seed.json \
  --resolved-voice  output/$RUN/resolved_voice.json \
  --evidence        output/$RUN/EvidencePack.json \   # 선택
  --out             output/$RUN/writing_brief.json
```

- **게이트**: 두 상류의 `hitl.approved`가 모두 true라야 `gates.ready=true`. 아니면 작성 차단(BLOCKED).
- brief가 작성 규율을 전달: 본문 뿌리 · 유령인용 금지 · `origin_memo` 불가침 · 긴장 보존 · 보이스 충실 · 청중 음높이 · eisegesis high는 재정착/제외.

### ⑤ 설교 개요 작성 — `sermon_outline.md` (★기본 산출)

에이전트(`skills/sermon-outline`)가 `writing_brief`를 받아 **본문 충실 개요**를 쓴다.
그 뒤 호밀레틱 계기판으로 점검:

```bash
python scripts/homiletic_audit.py \
  --draft     output/$RUN/sermon_outline.md \
  --resolved  output/$RUN/resolved_voice.json \
  --preacher-voice output/$RUN/preacher_voice.json \  # 선택
  --out       output/$RUN/homiletic_audit.json
```

- **계기판은 비점수 worklist**("다시 읽어보라" 신호). pass/fail·게이트가 아니다. **판단은 설교자.**
- 잡는 것: 강사화 · 재판관화 · 강단 상투구 · 논문체 전이. **호명·선포·권면·기도는 잡지 않는다**(설교의 생명) — 그 *결핍*이 경보다.
- 개요는 골격이라 구어 비율이 낮다 → 산문 단락(도입·적용·결단·기도) 기준으로 읽는다. 호명·질문·기도 *결핍* 신호는 개요에도 유효.
- 마지막에 설교자가 **sign-off**(AI는 sign-off하지 않는다).

### ⑥ (선택) 전체 원고 확장 + 전달 준비물

개요로 충분하면 여기서 멈춘다. 전체 구어 원고가 필요할 때만:

- 에이전트(`skills/manuscript-expander`)가 승인된 개요를 **펴서** `full_manuscript.md`로(새 논점·메시지·일화 무첨가 — 펴는 것이지 새로 쓰기 아님).

```bash
python scripts/delivery_pack.py \
  --manuscript output/$RUN/full_manuscript.md \
  --target-min 30 --chars-per-min 320 \
  --out output/$RUN/delivery_pack.json

# 원고도 구어 산문이라 계기판이 정밀하게 작동:
python scripts/homiletic_audit.py --draft output/$RUN/full_manuscript.md \
  --resolved output/$RUN/resolved_voice.json --out output/$RUN/homiletic_audit_ms.json
```

- `delivery_pack.py`: 전체·섹션별 전달 시간(±15% under/on/over, 40% 쏠림 점검) + 낭독 보조(긴 문장 호흡·원어 발음[그리스어/히브리어 자동검출]·숫자 읽기·긴 어절). **측정만** — 언어 조정 산문(`delivery_pack.md`)은 에이전트가 정리.
- 시간은 *대략* 추정(설교자별 `--chars-per-min` 보정 권장).

---

## 3. 가장 빠른 시작 (최소 경로)

키·샘플 없이 한 사이클 맛보기:

```bash
RUN=test01 && mkdir -p output/$RUN
# 1) 멘토 스킬에 본문+묵상 메모 제시 → meditation_seed.json 산출·승인
# 2) 보이스 합성(개인 보이스/청중 없이 — L1보편+L2만)
python scripts/voice_resolve.py --genre epistle --tier expository --season ordinary \
  --out output/$RUN/resolved_voice.json
# 3) 게이트 → 4) 개요 작성(스킬) → 5) 계기판
python scripts/outline_preflight.py \
  --meditation-seed output/$RUN/meditation_seed.json \
  --resolved-voice output/$RUN/resolved_voice.json \
  --out output/$RUN/writing_brief.json
```

---

## 4. 목회 윤리 헌법 — 항상 적용되는 12조 요약

전문은 [`CLAUDE.md`](./CLAUDE.md). 운영 중 반드시 지키는 핵심:

1. **AI는 돕는다, 대필하지 않는다** — 산출물은 설교자가 더 깊이 준비한 *자기 설교*.
2. **영적 권위·sign-off는 설교자 귀속** — 매 단계 HITL(✅승인 / ↻돌아가기 / ✏️수정 / ⏸보류).
3. **본문 충실 > 시대 적합성** — eisegesis(본문 왜곡) 감지 시 멈춘다.
4. **`origin_memo` 불가침** — 설교자의 원본 묵상을 요약·세련화로 덮어쓰지 않는다.
5. **보이스 = 대필 방지** — 회중 채점 금지, 정죄는 '너희'가 아니라 '우리', persona는 어조만 차용.
6. **아포리아 보존** — 신학적 긴장을 인위적으로 봉합/강제 개방하지 않는다.
7. **유령인용 금지** — 인용·통계·일화는 실제 EvidencePack 레코드에만 정착.
8. **회중은 목회자 입력** — AI가 회중을 추정하지 않는다. 익명·편향 차단.
9. **프라이버시·로컬 처리** — 묵상·샘플·보이스·회중 정보는 외부 전송·학습 데이터화 금지.
10. **신학 분별은 worklist** — 감지는 표시, 판단·결정은 목회자.
11. **개발 수칙** — 공개 단독 레포·stdlib 우선·스크립트≠산문·머신로컬 git·검증 정직.
12. **언어·태도** — 한국어 응답·검증한 것만 통과라 보고·임시 파일 정리.

---

## 5. 트러블슈팅

| 증상 | 원인 / 조치 |
|---|---|
| `outline_preflight`가 BLOCKED | 씨앗 또는 보이스의 `hitl.approved`가 false. 먼저 설교자 승인을 받는다. |
| fan-out에서 일부 엔진 스킵 | 정상(degraded). 키 없는 KCI/NLK는 자동 스킵. 키를 셸에 export하면 활성. |
| `voice_resolve` 잘못된 키 에러(exit 2) | `--genre/--tier/--season` 값 오타. 출력된 유효 목록에서 고른다(§2-③). |
| 계기판이 개요에서 강사화 점등 | 개요는 골격이라 hapnida 낮음 → 아티팩트일 수 있다. 산문 단락 기준으로 재해석, 원고 확장 후 재점검. |
| voice-ingest 관용구에 메타표현 노출 | 샘플 코퍼스 오염(설교+분석노트 혼합). 대표 설교만 넣고 Phase 2/HITL에서 거른다. |
| 파이프라인 정적 검증 | `python3 -W error::SyntaxWarning -m py_compile scripts/*.py` + JSON 로드 확인. |

---

*MS_Dev · TSPP — 설교 준비 파이프라인. 기능보다 헌법이 먼저다(→ `CLAUDE.md`). 설계는 `CONCEPT.md`, 인계는 `HANDOFF.md`.*
