# TSPP 세션 인계 (HANDOFF)

> **목적**: 새 세션에서 이 한 파일만 가리키면 TSPP 작업을 이어받도록 묶은 자기완결 인계 문서.
> 작성: 2026-05-29 | 직전 작업: `CONCEPT.md` v0.1 → v0.4 개선 (TAWP 세션에서 수행)

---

## 0. 새 세션 시작 시 — 먼저 읽을 것

```
1. tspp/CONCEPT.md                  ← 설계 본체 (v0.4, 자기완결)
2. tspp/HANDOFF.md                  ← 이 파일
3. ../Theology_Ontology_Starter/frameworks/homiletics.md            ← TOS Decalogue 10종 + 게이트/청중
4. ../Theology_Ontology_Starter/frameworks/homiletics_compositor.md ← TOS Meta-Compositor
5. (권장) ../Theology_Ontology_Starter/AGENTS.md · ROUTING_MATRIX.md · QUALITY_GATES.md
```

> 경로 기준: `/Users/msn/Desktop/MS_Dev.nosync/projects/`. TSPP는 **단독 레포·단독 프로젝트**이며, TAWP·TOS는 트리 *밖* 상류 의존이다.

---

## 1. 한 문장 정체성

TSPP = **"설교 파이프라인 신축"이 아니라, `TAWP`(주해·학술 리서치)와 `TOS`(설교 작성 엔진)를 잇고 그 위에 *설교자 보이스 + 목회 윤리* 층을 얹는 단독 오케스트레이션 프로젝트.**

---

## 2. 3-프로젝트 분업 (가장 중요한 재정의 — `CONCEPT.md §2.5`)

| 프로젝트 | 위치 | 역할 |
|---|---|---|
| **TAWP** | `projects/tawp` | 주해·학술 리서치 정밀(fan-out 5엔진·binding·claim-ledger). → TOS 온톨로지 입력 강화 |
| **TOS** (Theology_Ontology_Starter v5.8) | `projects/Theology_Ontology_Starter` | 호밀레틱 *작성* 엔진: Decalogue 10종·Meta-Compositor·품질게이트·청중레이어·다운스트림(slides/shortform/education/bible_study/deep_qt) |
| **TSPP** ★ | `projects/tspp` | (신규) 오케스트레이션 + 설교자 보이스 아키텍처 + 목회 윤리 |

**TSPP가 진짜 신축하는 것 (두 상류에 없는 것)** — 나머지는 TOS/TAWP 재사용:
1. **TAWP↔TOS 브리지 어댑터** — EvidencePack → TOS 온톨로지 JSONL (`scripts/bridge_evidence_to_ontology.py`)
2. **설교자 보이스 아키텍처** (§4-5) — 아래 §3
3. **목회 윤리 헌법** (§8) — 책임귀속·대필방지·HITL sign-off

> ⚠️ "TOS에 리서치 fan-out·보이스 *층*이 없다"는 판단은 `homiletics*.md` 정독 기반 *추정*이다. 새 세션에서 TOS의 `data/`·`src/`·`lenses/`를 한 번 더 훑어 **확정**할 것.

---

## 3. 설교자 보이스 아키텍처 (`CONCEPT.md §4-5` — TSPP의 심장)

TAWP의 보이스 2층 구조(L1 헌장 + L2 팔레트 + audit 계기판)를 *장르 이식*하되, **두 전도(inversion)** 필요:

**(1) L1은 복사가 아니라 전도** — 학술 L1이 *금지*하는 것을 설교는 *요구*한다(2인칭 호명·케리그마 선포·권면 당위·본문→회중→응답 동선). 그러므로:
- 별도 호밀레틱 L1 헌장(`references/homiletic-voice.md`)을 새로 쓴다.
- TAWP `tawp_audit §8`(학술 시점 검출기)은 **재사용 불가** — 정당 설교 어법을 오검출. 신호가 다른 호밀레틱 계기판을 별도 제작.

**(2) 보이스 축이 이중** (학술은 L2 단층뿐):
- **L1-개인** (설교자 동일성, 모든 설교 공유, **opt-in**) — `preacher_voice.json`
- **L2-상황** (본문장르 × 청중 × 절기 × tier) — `homiletic_voice_palette.json`

**(3) 윤리 정합** — 개인 보이스 보존이 곧 대필 방지. L1-개인은 편의가 아니라 안전장치.

**(4) 보이스 인제스트 ★ (사용자 요청)** — 설교자가 자기 설교문 샘플 5~10편 입력 → 어휘대·리듬·수사습관·신학강조점·구어체 표지 프로파일링 → `preacher_voice.json` 자동 초안 → HITL 승인 (`scripts/voice_ingest.py`). *남의 문체가 아니라 설교자 자신의 문체를 학습해 되돌려주는* 대필 방지 실물 메커니즘. 샘플은 로컬 처리·비공개.

**회중 컨텍스트 심화 ★ (사용자 요청, `CONCEPT.md §4-2`)** — 연령(TOS 3모드)뿐 아니라 신앙색채·정서/분위기·상황(지역·사회/교회 사건)·예전 위치까지 `audience_profile.json`에 수용 → L2-상황 보이스 + 적용에 동시 반영. **회중 프로파일은 목회자가 작성(AI 추정 금지).**

---

## 4. 미결 결정 (forks — `CONCEPT.md §12`, 사용자 판단 대기)

- **F5 결합 방식**: 산출물 소비(파일 계약) / vendoring 복사 / submodule — 단독 레포라 nesting 불가
- **F10 즉시 액션**: A 수동 PoC / B 단독 레포 골격 / **C TAWP↔TOS 브리지 어댑터(심장)** / D 한 본문 수직 PoC
- **F11 개인 보이스 모델**: opt-in(권장) / 필수 / 미지원 · 등록은 인제스트 추출(1순위)
- 그 외 F1(프로젝트명) · F2(분량) · F3(회중 깊이) · F4(렉셔너리) · F6(예화) · F7(윤리 강도) · F8(한국교회) · F9(첫 PoC 본문)

---

## 5. 현 상태 / 다음 액션

- `tspp/`에는 현재 `CONCEPT.md` + 이 `HANDOFF.md`만 있음. **아직 git 레포 아님** → 골격 신설(옵션 B) 시 `git init`부터.
- 다음 1수: F5·F10 결정 → 단독 레포 골격(헌법 3파일 + `references/homiletic-voice.md` + 보이스 데이터 2종 + `sermon-mentor`) 또는 브리지 어댑터 PoC.

---

## 6. 원본 메모리 (참고)

이 인계의 출처 메모리(자동 로드는 tawp 세션에서만 됨):
`/Users/msn/.claude/projects/-Users-msn-Desktop-MS-Dev-nosync-projects-tawp/memory/tspp-sibling-project-voice-architecture.md`
관련 메모리: `tawp-authorial-voice-architecture.md` (TAWP 보이스 구조 — 이식 원본).
