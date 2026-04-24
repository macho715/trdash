정리된 파일 목록입니다:

---

## Excel 파일 (`/excel`)

| 파일 | 설명 |
|------|------|
| `TR5_PreOp_Gantt_20260415_162140.xlsm` | **최신 메인 파일** (현재 작업 대상) |
| `TR5_PreOp_Gantt_20260415_162140.xlsm.bak_vba` | VBA 패치 전 백업 |
| `TR5_PreOp_Gantt_20260415_160149.xlsm` | 이전 빌드 v1 |
| `TR5_PreOp_Gantt_20260415_160419.xlsm` | 이전 빌드 v2 |
| `TR5_PreOp_Gantt_20260415_160741.xlsm` | 이전 빌드 v3 |
| `TR5_Preparation_Simulation_Gantt_MIR_Format_COM.xlsm` | MIR 포맷 원본 템플릿 |
| `TR5_Preparation_Simulation_Gantt_MIR_Format_COM_NEW_20260415_143...xlsm` | NEW 포맷 빌드 |

---

## 주요 스크립트 (`/scripts`)

| 파일 | 목적 |
|------|------|
| `tr5_build_gantt_workbook.py` | **메인 빌드 스크립트** (템플릿 → XLSM 생성) |
| `patch_tr5_gantt_vba.py` | Risk 색상 / 날짜 클리핑 최초 패치 |
| `patch_bidirectional_cascade.py` | 양방향 일정 cascade VBA 패치 |
| `patch_subtitle_and_timeline.py` | Subtitle 수식 + EnsureTimelineCovers 패치 |
| `patch_vba_binary.py` | **바이너리 VBA 패치** (Excel 없이) — 미실행 |
| `step2_vba_patch.py` | COM VBA 패치 (RefreshGanttExactRange 교체) — 미완료 |
| `step1_revert_cols.py` | Apr25/Apr26 컬럼 되돌리기 (완료 - 불필요) |
| `patch_fix_hardcoded_dates.py` | 하드코딩 날짜 통합 패치 (미실행) |
| `patch_fix_hardcoded_dates_v2.py` | v2 통합 패치 (미실행) |
| `patch_insert_apr25_openpyxl.py` | Apr25/Apr26 컬럼 삽입 (완료) |
| `patch_insert_apr25_cols.py` | Apr25/Apr26 컬럼 삽입 (구버전) |
| `patch_fix_apr25_format.py` | Apr25/Apr26 포맷 수정 (완료) |

---

## 설계 문서 (`/docs`)

| 파일 | 설명 |
|------|------|
| `PLAN3.MD` | 설계 명세서 (MIR 템플릿 복사 방식) |
| `TR5_Pre-Op_Simulation_v2_20260430.md` | **SSOT 일정 데이터** (Mermaid Gantt) |
| `TR5_Pre-Op_Simulation_Gantt_A3_v8.pdf` | 최신 PDF 출력본 |
| `TR5_Pre-Op_Simulation_Gantt.html` | HTML 간트 차트 |

---

## VBA 소스 (`/vba`)

| 파일 | 설명 |
|------|------|
| `Run_TR5_Gantt_Build.bas` | Excel에서 Python 빌드 실행 매크로 |
| `Run_TR5_Scope_Patch.bas` | 스코프 패치 실행 매크로 |

---

**현재 미적용 패치**: `patch_vba_binary.py` (Excel 없이 VBA 6곳 `RefreshGanttExactRange` → `RefreshGantt ws, False` 바이너리 교체). 실행하면 되나요?