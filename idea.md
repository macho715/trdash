
Doc-first와 외부 리서치를 반영해 **project-upgrade Full Pipeline** 결과를 정리했습니다. (Ask 모드라 파일 생성/수정은 하지 않았고, 아래 내용을 그대로 복사해 `UPGRADE_REPORT.md` 등으로 저장해 쓰시면 됩니다.)

---

# UPGRADE_REPORT — TR Dashboard + Standalone AI Package

**Scope:** tr_dash-main (HVDC TR Transport Dashboard) + standalone-package-20260311T084247Z-1-001 (myagent-copilot-standalone) 연동 관점  
**Mode:** Full Pipeline (Doc-first → Stack → External Research → Top10 → Best3 → Verification)  
**Constraints:** EN-only evidence, 2025-06-01 이후 게시/업데이트 우선, Evidence 없으면 AMBER_BUCKET

---

## 1. Executive Summary

- **Current state:** Next.js 16, React 19, SSOT(option_c.json), 3열(Where→When/What→Evidence), AI Command Palette(Ollama/OpenAI), Preview→Apply, Live/History/Approval/Compare.
- **Standalone 패키지:** `GET /api/ai/health`, `POST /api/ai/chat` (로컬 3010), DLP·CORS·토큰 인증; 대시보드는 “요약 JSON만” 전송하는 설계 권장.
- **Upgrade 방향:** (1) Standalone AI 프록시 정식 연동(엔드포인트·요약 페이로드·CORS), (2) Next.js 16/React 19 권장 패턴 적용(RSC·캐시·번들), (3) 보안·거버넌스(env/secret·감사 로그) 강화.
- **Best3:** Standalone AI Proxy 연동, Next.js 16 RSC/캐시 전략, React 19 Compiler 도입 검토. (아래 Evidence는 2025-06+ 확정된 것만 채택, 미확인 시 AMBER.)

---

## 2. Current State Snapshot

| 항목 | 내용 |
|------|------|
| **Repo** | tr_dash-main (HVDC TR Transport Dashboard) |
| **SSOT** | option_c.json, Activity 단일 진실원, Trip/TR 참조만 |
| **Stack** | Next.js 16.0.10, React 19.2.0, TypeScript 5.x, Tailwind 4.1.9, Radix UI, vis-timeline, Leaflet |
| **AI (현재)** | Ctrl+K Command Palette → POST /api/nl-command, Ollama/OpenAI, 8 intent (explain_why, navigate_query 등) |
| **Standalone (참조)** | myagent-copilot-standalone: GET /api/ai/health, POST /api/ai/chat, 127.0.0.1:3010, DLP·라우팅·토큰 |
| **CI** | quality-gate (typecheck, lint, test, build), secret-guard, release-policy, deploy-smoke, dependency-maintenance |
| **보안** | AGENTS.md: .env* 커밋 금지, Vercel env만 사용; SECURITY_REMEDIATION_REPORT_20260206 존재 |
| **테스트** | Vitest, 395 tests, 75 files; validate_optionc.py, smoke:nl-intent |
| **evidence_paths** | README.md, AGENTS.md, patch.md, docs/LAYOUT.md, docs/SYSTEM_ARCHITECTURE.md, docs/innovation-scout-dashboard-upgrade-ideas-20260211.md, package.json, .github/workflows/*.yml, config/env.example, standalone-package README/OPERATIONS |

---

## 3. Stack / Constraints

| 구분 | 내용 |
|------|------|
| **Build** | Node 20+, pnpm, `next build`, Turbo 기본 |
| **Test** | Vitest, typecheck, lint, SSOT validate_optionc.py |
| **CI** | PR/push to main|develop → typecheck, lint, test, build |
| **Deploy** | Vercel (docs/VERCEL.md), release-general / release-mobile 스크립트 |
| **Runtime** | Next.js 16 App Router, React 19, 브라우저 호환 |
| **제약** | SSOT·Preview→Apply·모드 분리·2-click Why·env/secret 미커밋 |

---

## 4. External Research (요약)

- **Next.js 16:** RSC 기본, Route Handlers, Server Actions, revalidateTag/ISR, 동적 import·번들 절감, Turbopack 기본, NEXT_PUBLIC_ 외 비노출. (출처: Next 16 가이드·블로그 2025; 일부 정확 published_date 미기재 → AMBER 가능.)
- **AI Proxy 보안:** Split-key·프록시 토큰·디바이스 검증, DLP·감사·rate limit. (출처: Proxed.AI, AIProxy, AgentKeys 등 2025; 제품 문서라 exact date AMBER.)
- **React 19:** Compiler로 메모이제이션 자동화, 불필요 re-render 감소. (출처: Medium “Feb, 2026” 등 → 2025-06+ 충족.)
- **Vercel/Env:** 서버/클라이언트 구분, Sensitive 변수, 로테이션, .env.local 미커밋. (출처: HashBuilds 2025, Vercel Docs.)
- **AI 요약/페이로드:** 스트리밍·최소 컨텍스트·요약 전송 패턴. (출처: GetStream, OpenAI cookbook, Vercel AI SDK; 일부 날짜 미명시 → AMBER.)

---

## 5. Upgrade Ideas Top 10 (6 buckets)

PriorityScore = (Impact × Confidence) / (Effort × Risk). Evidence ≥1, 날짜 충족 또는 AMBER 명시.

| # | Bucket | Idea | Evidence | Note |
|---|--------|------|----------|------|
| 1 | **Architecture** | **Standalone AI Proxy 연동** — NEXT_PUBLIC_AI_CHAT_URL, 요약 JSON만 POST /api/ai/chat, health 체크, CORS origin 등록 | Internal: standalone README·server.ts; External: AI proxy security 2025 (AMBER if date unverified) | 08번 문서(요약만 전송) 준수 |
| 2 | **Performance** | **Next.js 16 RSC·캐시** — /api/ssot·schedule revalidateTag, fetch cache, ISR 60s, 무거운 Gantt/Map dynamic import | Next 16 가이드 2025, 실시간 대시보드 가이드 (AMBER if date unverified) | AGENTS §5.1 데이터 소스 정합 |
| 3 | **Performance** | **React 19 Compiler** — babel-plugin-react-compiler 활성화, 불필요 memo/useCallback 정리 | React 19 Performance 2026 (Feb 2026), React Compiler stable 2025 | devDependencies 이미 있음 |
| 4 | **Security** | **Env/Secret 검증** — Vercel Sensitive 변수, 로테이션 문서화, server-only 경계 점검 | HashBuilds 2025, Vercel env/security docs | AGENTS 1.5 보안 위생 |
| 5 | **Reliability** | **Reflow fail-soft** — previewScheduleReflow 예외 시 toast + “이전 유지”/“초기화” 버튼 | Internal: innovation-scout T4 | patch §5 핵심 위젯 fail-soft |
| 6 | **DX** | **2-click Why 경로 표시** — Collision 배지 “1/2”, Why 패널 “2/2”, 포커스 이동 | Internal: innovation-scout U2 | patch 2-click 불변 |
| 7 | **Architecture** | **SSOT/스케줄 캐시** — scheduleActivities 메모이제이션, /api/ssot stale-while-revalidate | Internal: innovation-scout T2; External: Next caching 2025 (AMBER) | 중복 fetch 감소 |
| 8 | **Docs** | **AI 연동 runbook** — Standalone 기동·CORS·토큰·요약 스키마를 docs/ai-proxy 또는 OPERATIONS에 고정 | Internal: standalone OPERATIONS.md, README | 적용 08번 반영 |
| 9 | **Security** | **AI 요청 DLP 정책** — 클라이언트에서 raw option_c·PII 미전송, sensitivity 헤더·요약 스키마만 허용 | Internal: standalone DLP; External: AI proxy DLP 2025 (AMBER) | 08번·AGENTS 1.5 |
| 10 | **Reliability** | **Gantt/Map ErrorBoundary·skeleton** — dynamic import + fallback 리스트/표 + 스켈레톤 | Internal: innovation-scout T1, AGENTS §5 | 무중단 요구사항 |

---

## 6. Best 3 Deep Report

### BEST #1 — Standalone AI Proxy 연동

| 항목 | 내용 |
|------|------|
| **Goal** | tr_dash에서 myagent-copilot-standalone을 “요약만 보내는” 방식으로 사용해, Why 요약·질의 보조를 Copilot 쪽에서 제공. |
| **Design** | (1) `NEXT_PUBLIC_AI_CHAT_URL`(기본 `http://127.0.0.1:3010`), (2) 요약 JSON 스키마 정의(선택 TR/Activity, 충돌 요약, viewMode), (3) `lib/ai/summary-payload.ts` + `lib/ai/chat.ts`에서 POST /api/ai/chat, (4) UI: Detail 하단 접이식 “AI 요약” 또는 WhyPanel “AI로 원인 요약” 또는 툴바 “Ask AI” 중 1곳. (5) Health: GET /api/ai/health로 사용 전 확인. (6) CORS: MYAGENT_PROXY_CORS_ORIGINS에 `http://localhost:3000` 등 추가. |
| **PR Plan** | (1) env.example + 문서에 AI_CHAT_URL·CORS 설명, (2) summary-payload 타입·빌더, (3) chat.ts fetch + 에러/로딩, (4) 선택한 UI 위치에 컴포넌트 + 연동, (5) smoke 또는 단위 테스트(모의 health/chat). |
| **Tests** | Health 200 응답, chat 요청 본문 스키마 검증, 에러 시 fallback UI(비활성/메시지). |
| **Rollout/Rollback** | 기능 플래그 또는 AI_CHAT_URL 미설정 시 AI 블록 비노출; 롤백 시 env 제거 또는 플래그 off. |
| **Risks** | CORS·토큰(퍼블릭 시), DLP 미준수 시 차단. |
| **KPIs** | Health 성공률, 요청 실패 시 사용자 경험(에러 메시지/숨김). |
| **Evidence** | Standalone README·server.ts (internal); AI proxy security/DLP 2025 (external, AMBER if date unverified). |

---

### BEST #2 — Next.js 16 RSC·캐시 전략

| 항목 | 내용 |
|------|------|
| **Goal** | /api/ssot·스케줄 데이터 로딩을 RSC·캐시로 정리해 중복 fetch·리렌더 감소. |
| **Design** | (1) SSOT/스케줄 fetch에 revalidateTag 또는 revalidate=60, (2) fetch(..., { cache: 'force-cache' }) 또는 적절한 cache 옵션, (3) 무거운 Gantt/Map은 dynamic import + ErrorBoundary·skeleton 유지. |
| **PR Plan** | (1) /api/ssot 또는 데이터 로딩 레이어에 캐시 정책 추가, (2) scheduleActivities 사용처 메모이제이션 점검, (3) 문서(docs/LAYOUT.md 또는 SYSTEM_ARCHITECTURE)에 캐시 전략 한 줄 추가. |
| **Tests** | 기존 typecheck·lint·test·build 유지, 필요 시 SSOT 응답 캐시 동작 수동/통합 검증. |
| **Rollout/Rollback** | 점진적; 캐시 키/태그 변경으로 롤백. |
| **Risks** | stale 데이터 노출; revalidate 값·태그 설계 필요. |
| **KPIs** | 중복 요청 감소, LCP/TTI 개선(선택). |
| **Evidence** | Next.js 16 production guide 2025, Real-Time Analytics Dashboard guide (AMBER if exact date unverified). |

---

### BEST #3 — React 19 Compiler 검토·활성화

| 항목 | 내용 |
|------|------|
| **Goal** | React Compiler로 불필요 re-render·수동 메모이제이션 감소, Gantt/타임라인 체감 성능 개선. |
| **Design** | (1) babel-plugin-react-compiler 이미 있음 → 빌드에서 활성화 여부·설정 확인, (2) React 19 권장 패턴(Server Components·Actions)과 충돌 없는지 점검, (3) 점진 적용(레이아웃·리스트 먼저). |
| **PR Plan** | (1) Compiler 옵션 문서화·CI에서 noEmit/빌드 검증, (2) 문제 구역만 제외(allowList 등), (3) 성능 비교(선택). |
| **Tests** | typecheck, test:run, build 통과; 시각 회귀 없음. |
| **Rollout/Rollback** | 기능 플래그 또는 패키지 버전 고정; 롤백 시 compiler 비활성화. |
| **Risks** | 일부 패턴에서 예기치 않은 동작 가능; 공식 호환성 확인 필요. |
| **KPIs** | 리렌더 수·체감 지연 감소(선택). |
| **Evidence** | React 19 finally fixes performance optimization (Feb 2026, Medium); React 19 Performance Guide (2025). |

---

## 7. Options

| Option | 내용 |
|--------|------|
| **A** | Full: Best3 모두 진행(Standalone 연동 → RSC/캐시 → React Compiler 검토). |
| **B** | AI only: Standalone 연동만(엔드포인트·요약·UI·runbook). |
| **C** | Performance only: RSC/캐시 + React Compiler 검토, AI 연동 제외. |

---

## 8. 30/60/90-day Roadmap (요약)

- **30일:** Standalone AI Proxy 연동(env·요약 스키마·chat 유틸·한 곳 UI)·runbook, Reflow fail-soft(toast+버튼), 2-click Why “1/2”·“2/2” 표시.
- **60일:** /api/ssot·스케줄 캐시 전략, Gantt/Map ErrorBoundary·skeleton 점검, Env/Secret 문서화·검증.
- **90일:** React 19 Compiler 활성화 검토·점진 적용, AI DLP 정책·요청 스키마 고정, 30/60 항목 모니터링·문서 정리.

---

## 9. Evidence Table (요약)

| ID | URL/Source | published/updated | accessed | Note |
|----|------------|-------------------|----------|------|
| E1 | Next.js 16 Best Practices (dharmsy, makerkit, shsxnk 등) | 2025 (exact date unverified) | 2026-02 | AMBER_BUCKET if date &lt; 2025-06 |
| E2 | Next.js Upgrading Version 16 (nextjs.org) | official docs | 2026-02 | OK |
| E3 | Proxed.AI, AIProxy, AgentKeys (AI proxy security) | 2025 (product) | 2026-02 | AMBER_BUCKET if no date |
| E4 | React 19 Performance (Secret Dev, Medium “Feb, 2026”) | 2026-02 | 2026-02 | 2025-06+ OK |
| E5 | HashBuilds Next.js Env Security 2025 | 2025 | 2026-02 | AMBER if exact date unverified |
| E6 | Vercel env/secrets/rotating docs | official | 2026-02 | OK |
| E7 | GetStream/OpenAI/Vercel AI SDK (summary/streaming) | various | 2026-02 | AMBER if date unverified |
| Internal | README, AGENTS.md, patch.md, LAYOUT.md, innovation-scout, standalone README/server.ts | 2026-02-12 등 | 2026-02 | Doc-first |

---

## 10. AMBER_BUCKET

- **날짜 미충족:** “2025-06-01 이후” 미확인 출처(E1, E3, E5, E7) → Top10/Best3에서 채택 시 “Evidence ≥1 but AMBER”로 표기.
- **Best3:** Internal(standalone·AGENTS·innovation-scout) + External(날짜 충족 또는 AMBER)로 각 2개 이상 확보했으므로 Best3 Gate 충족. 3개 미만이면 BEST3_INCOMPLETE 아님.

---

## 11. Verification (PASS/AMBER/FAIL)

| Best | Stack/제약 충돌 | Verdict |
|------|------------------|---------|
| #1 Standalone AI | SSOT·Preview→Apply·모드 분리와 무충돌; env 미커밋 준수 필요 | PASS (runbook·env 관리 시) |
| #2 RSC/캐시 | 기존 SSOT·클라이언트 편집(Apply)과 공존 가능; 캐시 무효화 설계 필요 | PASS |
| #3 React Compiler | Next 16·React 19와 호환; 기존 테스트·빌드 유지 필요 | PASS (점진 적용 시) |

---

## 12. Open Questions (≤3)

1. **Standalone 패키지 배치:** tr_dash 레포 내 `kits/` 또는 `tools/`로 포함할지, 별도 레포·배포로 유지할지 결정 필요.
2. **CORS 기본값:** 로컬 개발용으로 `http://localhost:3000`을 standalone 기본 허용 origin에 넣을지, 팀 정책 확인 필요.
3. **React Compiler:** Next.js 16 공식 지원 상태·권장 설정(allowList 등) 최신 문서로 한 번 더 확인 권장.

---

**한 줄:** project-upgrade Full Pipeline 적용 결과, Standalone 패키지 기준으로 “요약 JSON + health/chat” 연동을 Best #1로 두고, Next.js 16 캐시·React 19 Compiler를 Best #2·#3으로 정리했으며, Evidence는 2025-06+ 확정 또는 AMBER로 구분해 두었습니다. 실제 반영은 Agent 모드에서 단계별로 적용하시면 됩니다.