# TSPP 품질 업그레이드 제안 및 구현 계획 (Quality Upgrade Plan)

> 작성일: 2026-06-11 · 상태: **구현 완료(2026-06-11)** — M1·M2·M3 전 마일스톤 구현·검증됨. 아래 §7에 구현 결과 요약.
> 전제: 목회 윤리 헌법(`CLAUDE.md`) 12조를 모두 보존한다. 아래 제안 중 헌법과 충돌하는 항목은 없으며, 오히려 헌법이 *선언만 하고 기계적으로 보증하지 못하던* 조항(§3 본문 정합 hard gate, §7 유령인용 금지)을 실체화하는 것이 골자다.

---

## 1. 진단 — 현재 파이프라인이 잘하는 것과 품질 병목

### 1.1 잘하는 것 (보존 대상)

- 묵상 경청 → 학술 fan-out → 원문 정착의 **근거 정직** 사슬 (EvidencePack + `===== p.N =====` 페이지 인용)
- 3층 보이스 아키텍처와 비점수 호밀레틱 계기판 (대필 방지 안전장치)
- 5대 HITL 체크포인트와 프리플라이트 게이트 (에이전트 대리 승인 차단 포함)
- 정성적 품질 검수(sermon-reviewer) 5대 차원

### 1.2 품질 병목 (이번 업그레이드의 표적)

| # | 병목 | 증거 | 헌법 연관 |
|---|---|---|---|
| 1 | **성경 인용이 무검증이다.** 유령인용 금지(§7)가 학술 자료(EvidencePack)에는 작동하지만, 정작 개요·원고 속 성경 직접 인용("이는 상속자니…")과 장절 표기는 어떤 스크립트도 대조하지 않는다. | `scripts/` 전체에 성경 본문 데이터·대조 로직 없음 | §7 (가장 큰 구멍) |
| 2 | **본문 정합 hard gate가 '정신'으로만 존재한다.** eisegesis 차단은 sermon-outline Phase 3에서 에이전트 자율 점검일 뿐, `text_anchor` 누락·pericope 이탈을 구조적으로 검증하는 스크립트가 없다. | `binding_verifier`는 MANUAL·헌법에 언급만, 구현 없음 | §3 |
| 3 | **본문 자체의 주해 단계가 없다.** 묵상(Phase 2)에서 곧장 *학술 논문* fan-out(Phase 3)으로 건너뛴다. 문맥·문학 구조·장르 특성·병행 본문을 정리한 산출물이 없어, 주해 깊이가 그 주에 입수한 논문의 운에 좌우된다. | 산출물 목록에 주해 브리프 부재 | §3·§7 |
| 4 | **예화 공급망이 없다.** 일화 날조는 금지(§7)인데 합법적 공급원은 학술 EvidencePack뿐이라, 개요가 예화 없이 메마르거나 에이전트가 '회중 접점' 서술로 우회하게 된다. | 샘플 run 개요에 예화 섹션 부재 | §7·§8 |
| 5 | **run 간 기억이 없다.** 본문·메시지·tier가 지난 설교들과 어떻게 이어지는지(중복·편중·시리즈 아크) 아무도 보지 않는다. 매주 설교하는 실제 목회 리듬에서 품질은 *한 편*이 아니라 *흐름*에서 나온다. | run 폴더가 완전 독립, ledger 부재 | §1 (준비 심화) |
| 6 | **강단 이후 피드백 루프가 없다.** 설교 후 무엇이 가닿았는지가 보이스 프로파일·다음 준비에 반영되지 않는다. preacher_voice가 한 번 추출되고 늙어간다. | retro 산출물·갱신 신호 없음 | §5 |
| 7 | **계기판 신호에 위치가 없다.** homiletic_audit이 "강사화 신호"를 점등해도 *몇째 단락*인지 알려주지 않아, 설교자가 다시 읽을 곳을 직접 찾아야 한다. | `homiletic_audit.py`에 단락 위치 출력 없음 | §10 |

---

## 2. 제안 개요 — 우선순위

핵심 원칙은 기존과 동일: **스크립트는 측정·게이트·구조 합성만, 산문은 에이전트, 확정은 설교자.**

| 우선순위 | 제안 | 산출물 | 성격 |
|---|---|---|---|
| **P0-1** | 성경 인용 정합 게이트 | `data/scripture/` + `scripture_pack.json` + `scripture_check.json` | 정직성(§7) 구멍 봉합 |
| **P0-2** | 본문 정합(binding) 게이트 실체화 | `binding_map`(개요 내) + `binding_check.json` | §3 hard gate 구현 |
| **P1-3** | 주해 브리프 단계 신설 | `exegesis_brief.md` | 주해 깊이 |
| **P1-4** | 예화 금고 (illustration vault) | `input/illustrations/` + 인덱스 | 예화 품질·프라이버시 |
| **P1-5** | 설교 이력 장부 + 시리즈 연속성 | `sermon_ledger.json` + `series_check` | 흐름 품질 |
| **P2-6** | 다중 렌즈 리뷰 확장 | sermon-reviewer 패스 추가 | 검수 깊이 |
| **P2-7** | 설교 후 회고 루프 | `sermon_retro.md` + 보이스 갱신 신호 | 보이스 생명 유지 |
| **P2-8** | 계기판 고도화 + 종합 리포트 | 신호 위치·추세, `tspp.py report` | 가시성 |

---

## 3. 제안 상세

### P0-1. 성경 인용 정합 게이트 — "성경 인용도 EvidencePack급으로"

**무엇**: 공개(퍼블릭 도메인/허용 라이선스) 성경 본문을 로컬에 vendoring하고, 개요·원고의 (a) 직접 인용 문자열과 (b) 장절 표기를 본문 데이터와 대조한다.

**왜**: 현재 파이프라인에서 가장 권위 있는 인용원(성경)이 가장 무검증 상태다. LLM은 익숙한 구절일수록 그럴듯한 *의역 혼합*을 생성하기 쉽고, 존재하지 않는 절 번호(예: 본문이 21:46에서 끝나는데 21:47 인용)도 걸러지지 않는다.

**구현 스케치**:

- `data/scripture/` — 본문 데이터 vendoring (장절 단위 JSON/TSV):
  - 한글: **개역한글판(1961)** — 저작권 만료로 통용되나, **착수 전 라이선스 재확인을 1번 태스크로 명시**한다. 확인 실패 시 대안(예: 원어 데이터만 + 한글 인용은 worklist 전용)으로 강등.
  - 원어(선택): SBLGNT(CC BY 4.0)·Westminster Leningrad Codex(퍼블릭 도메인) — delivery_pack이 이미 자동 검출하는 그리스어/히브리어 인용의 철자 검증용.
  - 출처·라이선스는 `VENDOR.md`에 추가.
- `scripts/scripture_pack.py` (stdlib) — run의 `passage_ref`로 pericope ± 전후 문맥 N절을 추출해 `output/<run>/scripture_pack.json` 생성. 에이전트는 **이 팩의 본문만** 인용 원본으로 쓴다(번역본 명기).
- `scripts/scripture_check.py` (stdlib) — 개요/원고에서 장절 표기와 인용부호 구간을 파싱해 대조:
  - **hard 신호**: 존재하지 않는 책/장/절, pericope·선언된 cross_ref 밖의 장절 (게이트성)
  - **worklist 신호**: 인용부호 안 문자열과 본문 불일치(의역 가능성 — 의역은 정당하므로 *비점수*, "번역본 확인" 신호만)
- `tspp.py scripture <run>` 서브커맨드로 래핑.

**헌법 정합**: §7 확장 적용. 스크립트는 대조만 하고 판단(의역 허용 여부)은 설교자(§10).

### P0-2. 본문 정합(binding) 게이트 실체화 — eisegesis 구조 검증

**무엇**: 개요의 각 논점·적용·예화에 기계가 읽을 수 있는 `text_anchor`를 의무화하고, 구조 검증 스크립트를 둔다.

**왜**: §3은 "적용이 본문을 왜곡하면 멈춘다"고 선언하지만, 현재 검증 주체가 작성자(에이전트) 자신뿐이다. *해석의 적절성*은 기계가 판단할 수 없어도, *정착의 구조*(앵커 존재·범위)는 기계가 보증할 수 있다.

**구현 스케치**:

- 개요 컨벤션 강화: 각 논점/적용 블록에 `**본문 뿌리**: <장절>` 표기는 이미 있음 → 이를 파싱 가능한 규격으로 고정하고, frontmatter에 `binding_map`(논점→anchor, claim_type: explicit/inference/application, cross_ref 선언) 요약을 둔다. **작성은 에이전트, 검증은 스크립트.**
- `scripts/binding_check.py` (stdlib):
  - **hard (BLOCKED)**: anchor 없는 논점/적용 존재 · anchor가 pericope 밖인데 cross_ref 미선언 · `writing_brief`의 `eisegesis_risk: high` 후보가 재정착 기록 없이 개요에 들어옴
  - **worklist**: claim_type이 application인데 explicit 근거 논점과 연결 없음(도약 가능성 신호)
  - 산출 `output/<run>/binding_check.json` — sermon-outline Phase 3의 자율 점검을 이 스크립트 실행으로 대체.
- `outline_preflight`와 대칭으로, HITL 5(최종 sign-off) 전에 실행을 의무화(스킬 지침 갱신).

**헌법 정합**: §3 hard gate의 1:1 구현. 해석 판단은 여전히 설교자(§10) — 스크립트는 구조만 본다.

### P1-3. 주해 브리프(exegesis brief) 단계 신설

**무엇**: sermon-mentor Phase 2(심화)와 Phase 3(학술 fan-out) 사이에 본문 자체를 정리하는 `exegesis_brief.md`를 추가한다 — 문학 구조(단락 흐름), 전후 문맥, 장르 특성, 병행 본문(공관 평행 등), 본문 내 긴장 후보.

**왜**: 학술 논문은 그 주의 검색 운에 좌우되지만, 본문 자체의 구조 분석은 항상 가능하다. 또한 주해 브리프가 있으면 메시지 후보의 `text_anchor`가 절 번호가 아니라 *본문 구조 안의 자리*에 정착해 P0-2의 질이 올라간다.

**구현 스케치**:

- `skills/exegesis-brief/SKILL.md` 신설(에이전트 산문 작업): 입력 = `scripture_pack.json`(P0-1) + meditation_seed 초안. 산출 = `output/<run>/exegesis_brief.md`.
- **강사화 방지 규율을 스킬에 내장**: 브리프는 *준비실 문서*다. 개요·원고에 이식 금지 — homiletic-voice.md §3-① "배경 지식은 등불"을 명문화. 브리프의 어떤 단락도 개요에 그대로 복사되면 계기판 강사화 신호와 교차 점검.
- 근거 규율: 구조 분석은 scripture_pack 본문에서만, 학설 인용은 EvidencePack 레코드에서만(유령 주석 금지).
- sermon-mentor SKILL.md에 Phase 2.5로 연결(선택 단계 — 묵상이 먼저, 주해가 묵상을 납치하지 않게 Phase 1 이후에만).

**헌법 정합**: §3(본문 충실)을 *상류에서* 강화. §7 인용 규율 동일 적용.

### P1-4. 예화 금고 (Illustration Vault)

**무엇**: 설교자 소유의 예화 은행. `input/illustrations/`(gitignore, 로컬 자산)에 카드 단위로 축적하고, stdlib 인덱서로 검색·사용 이력을 관리한다.

**왜**: 날조 금지(§7) 아래에서 예화의 유일한 합법 공급원이 필요하다. 또한 회중 일화의 동의·익명화(§8)를 *카드 메타데이터*로 강제할 수 있다.

**구현 스케치**:

- 카드 스키마(JSON 또는 frontmatter MD): `id, title, body, source(출처·연도), kind(개인 경험/역사/문학/회중), anonymized(bool), consent(bool, 회중 일화일 때), tags, used_in(run 목록)`.
- `scripts/illustration_index.py` (stdlib): 태그/키워드 검색, 사용 기록(`used_in` 갱신), **경고 신호**: 회중 일화인데 `anonymized=false` 또는 `consent=false` → 사용 차단 권고(worklist), 최근 N편 내 재사용 → 반복 신호.
- 스킬 규율 갱신: sermon-outline·manuscript-expander는 예화를 **금고 카드 또는 EvidencePack 레코드에서만** 인용(카드 id 표기). 금고가 비면 예화 없이 쓰고 "예화 후보 찾기"를 worklist로 설교자에게 넘긴다 — 지어내지 않는다.

**헌법 정합**: §7(실제 자료만)·§8(익명성·동의)·§9(로컬 자산). AI가 예화를 *생성*하지 않고 *조회*만 한다.

### P1-5. 설교 이력 장부(sermon ledger) + 시리즈 연속성

**무엇**: run이 sign-off될 때 한 줄 요약을 장부에 적립하고, 새 run 시작 시 흐름 신호를 보여준다.

**구현 스케치**:

- `output/sermon_ledger.json` (로컬, gitignore): run·설교일·본문·메시지 한 줄·genre·tier·season·사용 예화 id.
- `scripts/ledger_update.py` — sign-off된 run에서 자동 추출(스크립트는 요약을 *짓지 않고* seed/outline의 기존 필드만 복사).
- `scripts/series_check.py` — 새 run의 본문/키워드/메시지 후보를 최근 N편과 대조: 본문 중복, 메시지 유사(키워드 겹침 기반 — 의미 유사도 아님, stdlib 한계 정직 명시), tier 편중(예: 4주 연속 prophetic), 예화 재사용. **비점수 worklist** — "지난달에 같은 본문을 설교했습니다" 수준의 사실 신호.
- sermon-mentor Phase 0에 입력: 멘토가 회중을 추정하는 게 아니라 **설교자 자신의 산출 이력**을 비춰준다.
- (선택) 시리즈 선언: run 생성 시 `--series <name>`으로 묶으면 시리즈 내 아크(이전 편 메시지 목록)를 brief에 동봉.

**헌법 정합**: §8 위반 아님 — 회중 데이터가 아니라 설교자 자신의 과거 산출물만 본다. §9 로컬 처리.

### P2-6. 다중 렌즈 리뷰 — sermon-reviewer 확장

**무엇**: 기존 5대 차원(단일 패스)에 두 개의 독립 패스를 추가한다.

1. **콜드 리드(첫 청취 명료성)**: 아무 맥락 없이 원고만 읽고 — "이 설교의 메시지를 한 문장으로 복기할 수 있는가? 어느 단락에서 길을 잃는가? 결단 요청이 무엇인지 들리는가?" — 회중 *추정*이 아니라 텍스트 *명료성* 점검이다.
2. **반대 독해(counter-reading)**: 본문이 이 설교의 메시지에 *저항*하는 지점을 일부러 찾는다(§3의 마지막 안전망). 발견은 worklist로만.

**구현 스케치**: `skills/sermon-reviewer/SKILL.md`에 패스 2·3 규칙 추가 + 리포트 템플릿에 섹션 추가. 패스 간 독립성(앞 패스 결론을 보지 않고 시작)을 지침에 명시. 스크립트 변경 없음.

**헌법 정합**: §8(회중 추정 금지) 준수 — 페르소나 기반 '가상 회중 반응'은 **채택하지 않는다**(비범위 §5 참조). §10 판단은 설교자.

### P2-7. 설교 후 회고 루프 (retro)

**무엇**: 설교 *후* 설교자가 기록하는 회고 템플릿과, 그 축적이 보이스 프로파일 갱신으로 이어지는 신호.

**구현 스케치**:

- `tspp.py retro <run>` — `output/<run>/sermon_retro.md` 뼈대 생성(실제 전달 시간 → `--chars-per-min` 보정 제안, 가닿은/걸린 단락, 스스로 평가, 보이스 메모). **내용은 설교자가 쓴다** — AI가 회고를 대필하지 않는다.
- `ledger_update.py`가 retro의 구조화 필드(실측 시간 등)를 장부에 반영.
- retro N편 축적 시 신호: "최근 원고 N편이 모였습니다 — `voice_ingest` 재실행으로 preacher_voice를 갱신할 때입니다"(voice coverage 로직 재사용).

**헌법 정합**: §5(보이스는 살아 있는 지문 — 갱신 루프가 보존 장치) · §2(기록 주체는 설교자).

### P2-8. 계기판 고도화 + 종합 리포트

**무엇**:

- `homiletic_audit.py`에 **신호 위치**(단락 번호 + 발췌 일부)와 **섹션별 분해**(도입/논점/적용/기도) 추가 — "다시 읽어보라"를 "여기를 다시 읽어보라"로.
- ledger 연동 **추세**: 같은 신호가 최근 run들에서 반복되는지(예: 상투구 X가 3편 연속).
- `tspp.py report <run>` — preflight·binding_check·scripture_check·audit·delivery·review를 한 화면으로 수합한 읽기 전용 현황판(신규 판단 없음, 기존 산출 요약만).

**헌법 정합**: 비점수·비게이트 성격 유지(§10). report는 수합만 한다.

---

## 4. 구현 계획 (마일스톤)

> 공통 수칙: 순수 stdlib · 스크립트는 산문 금지 · 각 마일스톤 종료 시 `python3 -W error::SyntaxWarning -m py_compile scripts/*.py` + 샘플 run(matthew21_tenant) 재실행으로 검증 · MANUAL.md/START_HERE.md 갱신 동반.

### M1 — 정직성 게이트 (P0, 1차 착수)

| 순서 | 작업 | 완료 기준(검증) |
|---|---|---|
| 1 | 개역한글판 라이선스 확인 + 본문 데이터 포맷 설계 | 확인 결과를 `VENDOR.md`에 기록. 불가 시 대안 경로 확정 |
| 2 | `data/scripture/` vendoring + `scripture_pack.py` | 마태복음 21장 pericope 추출이 원문과 일치(수동 대조 3구절) |
| 3 | `scripture_check.py` + `tspp.py scripture` | matthew21_tenant 원고에 돌려 기존 인용의 일치/불일치 리포트 산출 |
| 4 | 개요 binding_map 규격 확정 + `binding_check.py` | 샘플 개요에서 anchor 전수 검출, 고의로 anchor 제거 시 BLOCKED 확인 |
| 5 | sermon-outline SKILL Phase 3을 binding_check 실행으로 갱신 + interactive-hitl.md에 체크포인트 반영 | 문서 교차 참조 일관성 확인 |

### M2 — 준비 깊이 (P1)

| 순서 | 작업 | 완료 기준 |
|---|---|---|
| 1 | `skills/exegesis-brief/` 신설(SKILL + 템플릿) + sermon-mentor 연결 | 샘플 run으로 브리프 1회 생성, 강사화 이식 금지 규율 포함 확인 |
| 2 | 예화 카드 스키마 + `illustration_index.py` + `input/illustrations/` 부트스트랩 | 카드 3장으로 검색·사용기록·동의 경고 동작 확인 |
| 3 | `sermon_ledger.json` + `ledger_update.py` + `series_check.py` | 기존 2개 run 적립 후 중복 본문 신호 발화 확인 |
| 4 | outline/expander 스킬에 예화 인용 규율(카드 id) 추가 | 스킬 문서 갱신 + 샘플 개요에 카드 인용 표기 |

### M3 — 검수·루프·가시성 (P2)

| 순서 | 작업 | 완료 기준 |
|---|---|---|
| 1 | sermon-reviewer 콜드 리드·반대 독해 패스 + 템플릿 확장 | 샘플 원고 재검수 리포트에 신규 섹션 포함 |
| 2 | `tspp.py retro` + ledger 연동 + voice 갱신 신호 | retro 뼈대 생성·실측 시간 반영 확인 |
| 3 | audit 위치·섹션·추세 + `tspp.py report` | 신호에 단락 위치 출력, report 한 화면 수합 확인 |

### 의존 관계

```
M1-1,2 (scripture 데이터) ──▶ M1-3 (인용 대조) ──▶ M2-1 (주해 브리프)
M1-4 (binding_check)      ──▶ M1-5 (스킬·HITL 갱신)
M2-3 (ledger)             ──▶ M3-2 (retro) · M3-3 (추세)
M2-2 (예화 금고)           ──▶ M2-4 (스킬 규율)
```

---

## 5. 비범위 (이번에 하지 않는 것)

- **페르소나 기반 가상 회중 반응 시뮬레이션** — §8(AI 회중 추정 금지)과 충돌 소지가 있어 채택하지 않는다. 콜드 리드는 텍스트 명료성 점검으로 한정.
- **메시지 의미 유사도(임베딩) 기반 중복 검출** — 외부 패키지/모델 필요. series_check는 키워드 겹침 수준의 정직한 한계를 명시하고 stdlib로만 간다.
- **찬송·예배 순서 추천** — 저작권·교단 변수. 향후 별도 검토.
- **외부 전송이 필요한 어떤 기능도** — TTS 클라우드 낭독, 원격 저장 등(§9).
- **자동 sign-off·게이트 완화** — 게이트는 늘리되 줄이지 않는다(§2).

---

## 6. 리스크와 정직한 한계

| 리스크 | 대응 |
|---|---|
| 개역한글판 라이선스가 예상과 다를 가능성 | M1-1을 선행 태스크로 분리. 불가 시 원어 데이터만 vendoring하고 한글 인용 대조는 worklist 전용으로 강등 |
| 인용 대조의 의역 오탐(정당한 풀어 말하기를 불일치로 표시) | hard/worklist 이원화 — 문자열 불일치는 절대 게이트화하지 않음 |
| binding_map 규격이 에이전트 작성 부담 증가 | 기존 개요 컨벤션(`**본문 뿌리**:`)을 그대로 파싱 — 작성 방식 변화 최소화 |
| ledger·금고가 비공개 자산인데 스키마는 공개 레포 | 데이터는 input/output(gitignore), 스키마·example만 커밋 — 기존 audience_profile.example 패턴 동일 |
| series_check 키워드 겹침의 낮은 정밀도 | "신호이지 판정 아님"을 출력 문구에 명시(§10 worklist 원칙) |

---

## 7. 구현 결과 (2026-06-11)

| 항목 | 구현물 | 검증 |
|---|---|---|
| P0-1 성경 인용 정합 | `data/scripture/KorRV/`(66권 31,104절, 퍼블릭 도메인 확인 — VENDOR.md) + `scripture_import.py`·`scripture_lib.py`·`scripture_pack.py`·`scripture_check.py` + `tspp.py scripture` | 마 21:33·38·39 위키문헌 독립 대조 일치. 샘플 run에서 실제 불일치 검출(개요 "유산"↔KorRV "유업" 등 worklist 5건), 존재하지 않는 절(21:47·29장) hard 차단 확인 |
| P0-2 binding 게이트 | `binding_check.py`(`**본문 뿌리**:` 앵커 파싱·pericope 범위·cross_refs 선언·eisegesis high 재정착) + `tspp.py binding` | 샘플 개요에서 적용 섹션 앵커 누락 → blocked(rc=1), 앵커 보완 시 ok 확인 |
| P1-3 주해 브리프 | `skills/exegesis-brief/`(SKILL + 템플릿) + sermon-mentor Phase 2.5 연결 | 템플릿 자체를 scripture_check로 도그푸딩 — 전 인용 verified 1.0 (작성 중 발견된 번역본 혼입 3건 교정) |
| P1-4 예화 금고 | `data/illustration_card.example.json` + `illustration_index.py`(list/search/use/check) | 카드 3장 임시 금고로 검색·사용기록·동의 미해소 차단(rc=1)·조사 흡수 검색 확인 |
| P1-5 이력 장부 | `ledger_update.py`(기존 필드 복사만) + `series_check.py` | 기존 2개 run 적립 후 passage_repeat·theme_overlap(44%) 신호 발화 확인 |
| P2-6 다중 렌즈 리뷰 | sermon-reviewer SKILL 3-pass(5차원·콜드리드·반대독해) + 템플릿 §3·§4 | 템플릿 치환 무결성 확인(격리 워크스페이스) |
| P2-7 회고 루프 | `tspp.py retro`(뼈대→실측 보정 제안→장부 적립→보이스 갱신 신호) | 실측 16분 입력 시 `--chars-per-min 268` 보정 제안·장부 반영 확인 |
| P2-8 계기판·현황판 | homiletic_audit v2(신호 위치·섹션 분해·ledger 추세) + `tspp.py report` | 오염 초안에서 단락·발췌 지목, 2편 반복 추세 보고. report 한 화면 수합 확인 |

비범위(§5)는 그대로 유지 — 가상 회중 시뮬레이션·임베딩 유사도·외부 전송은 구현하지 않았다. 원어 데이터(SBLGNT·WLC)는 미포함(향후 선택 과제, VENDOR.md 명시).

*TSPP · QUALITY_UPGRADE — 기능보다 헌법이 먼저다. 이 계획의 모든 항목은 "돕되, 대체하지 않는다"를 강화하는 방향으로만 설계되었다.*
