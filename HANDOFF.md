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

## 4. 설교자 보이스 아키텍처 (`CONCEPT.md §4-5` — 향후 구현, 미착수)

TAWP 보이스 2층(L1 헌장 + L2 팔레트 + 계기판)의 *장르 이식*. **두 전도(inversion)**:
1. **L1은 복사 아닌 전도** — 학술이 금지하는 것(2인칭 호명·케리그마 선포·권면)을 설교는 요구. 별도 `references/homiletic-voice.md` 필요. `tawp_audit §8`(학술 시점 검출) 재사용 불가.
2. **축이 이중** — L1-개인(설교자 동일성, opt-in, `preacher_voice.json`) + L2-상황(본문장르×청중×절기×tier, `homiletic_voice_palette.json`).
3. **보이스 인제스트** ★ — 설교문 샘플 5~10편 → 문체 프로파일링 → `preacher_voice.json` 초안 → HITL. 대필 방지의 실물 메커니즘.
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
- **TAWP↔TOS 브리지 어댑터** (`scripts/bridge_evidence_to_ontology.py`) — 작성 단계 연결, 미착수
- 그 외 F1(프로젝트명)·F2(분량)·F3(회중 깊이)·F4(렉셔너리)·F6(예화)·F7(윤리 강도)·F8(한국교회)·F9(첫 PoC 본문)

---

## 6. 현 상태 / 다음 액션

**현 상태**: `git init` 완료(main, 커밋 `8664ea8`). sermon-mentor 골격(SKILL.md + 방법론 + 스키마) + fan-out vendoring 완료. 정적 검증 통과(import·라우팅·JSON·registry·gitignore).

**다음 1수 후보:**
1. **fan-out 스모크 테스트** — `uv sync`(kci/nlk) + API 키 세팅 후, 우선 S2/Crossref(키 불요)로 한 본문 키워드를 실제 검색 → EvidencePack 생성 확인. (⚠️ 실제 네트워크 fan-out은 아직 미검증)
2. **sermon-mentor 실사용 1사이클** — 실제 본문+묵상 메모로 6-Phase를 돌려 흐름의 거친 곳 발견 → SKILL.md 다듬기.
3. **목회 윤리 헌법 3파일** (CLAUDE/AGENTS/GEMINI.md, `CONCEPT.md §8`) — 아직 없음. 책임귀속·대필방지·HITL.
4. (작성 단계 갈 때) TAWP↔TOS 브리지 어댑터 또는 보이스 아키텍처 착수.

---

## 7. 원본 메모리 (참고)

`/Users/msn/.claude/projects/-Users-msn-Desktop-MS-Dev-nosync-projects-tawp/memory/tspp-sibling-project-voice-architecture.md`
관련: `tawp-authorial-voice-architecture.md` (TAWP 보이스 구조 — 이식 원본). 본 세션 결정(공개 단독·vendoring·fan-out 멘토 통합·4엔진)은 이 HANDOFF가 최신.
