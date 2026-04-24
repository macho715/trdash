# TR5 Gantt Final v8 Patch Plan

Date: 2026-04-24  
Target workbook: `C:\Users\SAMSUNG\Desktop\복사본 TR5_PreOp_Gantt_20260415_162140_macrofixed_20260424_084432.xlsm`  
Primary source document: `C:\tr_dash-main\work\TR5_Schedule_Final_v3.md`  
Reference-only document: `C:\tr_dash-main\docs\일정\TR5_PreOp_Final_Schedule_v3.md`

## Purpose

Update the existing TR5 Excel Gantt chart task list and schedule dates to match the user-specified source document, while preserving every existing workbook behavior:

- Init / Reset / Show Notes buttons.
- Risk dropdown editing and repaint behavior.
- Weekend-bounded date array.
- Dynamic title/subtitle area.
- VBA event hooks, protection, named ranges, logs, validation, and saved `.xlsm` macro integrity.

## Source Selection

The requested source path is `work\TR5_Schedule_Final_v3.md`. Although the filename says `v3`, the document body is `Rev v8.0` and states:

- T+0 Go Signal: `2026-04-26`
- LCT Bushra MZP All Fast: `2026-05-04`
- Target RoRo Load-out: `2026-05-06`
- Target AGI Jacking Down Complete: `2026-05-13`

The open-tab reference `docs\일정\TR5_PreOp_Final_Schedule_v3.md` is `Rev v3.0` with T+0 `2026-04-30`. It is not the patch authority unless the user changes the source.

## Current Workbook Delta

The current workbook has the same general structure but is shifted earlier and contains items from the later v3/MWS scenario:

- Current subtitle shows T+0 `2026-04-22`, Load-out `2026-05-04`, AGI JD `2026-05-12`.
- Current Gantt first task date starts at `2026-04-25`.
- Source document requires first task date `2026-04-26`.
- Source document requires Load-out `2026-05-06`, AGI JD `2026-05-13`.
- Current workbook includes MWS-specific rows that do not appear in the requested `work\TR5_Schedule_Final_v3.md` Mermaid Gantt.

## Patch Design

Use a serial single-writer COM patch script. Do not rebuild the workbook from scratch.

1. Read the Mermaid Gantt block from `work\TR5_Schedule_Final_v3.md`.
2. Convert each task into workbook rows using the existing sheet columns:
   - `Phase`
   - `Task Description`
   - `Start`
   - `End`
   - `Days`
   - `Risk`
   - `Notes / Action`
3. Preserve the existing phase sections and workbook visual style.
4. Remove or blank workbook task rows that do not exist in the source Mermaid list, including MWS-only rows from the v3 scenario.
5. Recompute end dates from Mermaid duration:
   - `0d` milestone becomes same-day start/end.
   - `Nd` activity becomes inclusive start through `start + N - 1`.
6. Set risk values from Mermaid markers:
   - `crit` tasks become `CRITICAL`.
   - `milestone` / gate rows become `GATE`.
   - Other operational long-lead rows default to `OK` unless the source row text implies review/critical path.
7. Rebuild the visible Gantt date array after the row update:
   - must remain continuous day-by-day.
   - must expand to complete Saturday/Sunday calendar boundary.
8. Update subtitle authority:
   - T+0 `2026-04-26`.
   - Load-out from `BD2` row: `2026-05-06`.
   - AGI JD from `JDC` row: `2026-05-13`.

## VBA / Macro Preservation Contract

The existing Excel VBA must continue to work the same way after the schedule update. The patch must treat VBA behavior as a contract, not as disposable implementation detail.

Required preservation points:

- Do not delete or rebuild the VBA project.
- Do not rename public macro entrypoints.
- Do not change workbook event wiring unless a broken binding is detected and the fix is strictly equivalent.
- Preserve existing button behavior:
  - `Init` runs the existing initialization flow.
  - `Reset` remains connected to the existing reset macro.
  - `Show Notes` / `Hide Notes` still toggles the notes/action column.
- Preserve risk dropdown behavior and the existing risk repaint path.
- Preserve sheet protection behavior and editable cells.
- Preserve named ranges used by existing schedule snapshots, UID rows, source label, and timeline metadata.
- Preserve the weekend-bounded timeline behavior added in the prior patch.

Permitted VBA changes:

- Only minimal compatibility changes required to keep formulas, title/subtitle, or the regenerated date header stable after task/date replacement.
- Any VBA text change must be reported in the final result with the affected procedure names.

Preferred implementation:

- Update `Gantt_BASE` data rows and workbook names through COM.
- Avoid VBA mutation if the existing macros can process the updated rows correctly.
- If VBA must be touched, export the module before and after, then verify changed procedures only.

## Execution Mode

MStack dispatch decision: direct execution with read-only parallel analysis.

- Estimated changed files: 1 new patch script plus optional log/report output.
- Workbook mutation surface: `Gantt_BASE` rows, formulas, date headers, VBA/Named Range values only if needed.
- Coupling risk: medium-high because date rows, formula subtitle, buttons, protection, and VBA repaint all interact.
- Subagents: used only for read-only source schedule parsing and macro-preservation checklist. The workbook patch remained single-writer.

## Files To Touch

Planned repo file:

- `work/TR5_PreOp_Gantt_20260415/scripts/patch_final_v8_schedule.py`

Planned workbook:

- `C:\Users\SAMSUNG\Desktop\복사본 TR5_PreOp_Gantt_20260415_162140_macrofixed_20260424_084432.xlsm`

No destructive deletion of user files is planned.

## Validation Plan

Run three independent workbook validations after patch:

1. Init validation:
   - Run `Init_Unified_System`.
   - Verify buttons still exist and point to workbook-local macros.
   - Verify the Gantt starts/ends on complete weekend boundary.
   - Verify public macro names still exist.

2. Data validation:
   - Verify source milestones:
     - G1 PTW Approved = `2026-04-29`
     - G2 HM Approval Received = `2026-05-04`
     - Bushra All Fast = `2026-05-04`
     - RoRo Load-out = `2026-05-06`
     - AGI JD Complete = `2026-05-13`
   - Verify no `#REF!`, `#VALUE!`, `#NAME?`, or blank required dates in key range.
   - Verify risk dropdown remains attached to task rows.

3. Save/reopen validation:
   - Save workbook.
   - Reopen/read saved `.xlsm` with `keep_vba=True` where possible.
   - Verify title/subtitle, date headers, row count, task list, and formulas persisted.
   - Verify buttons still bind to the same workbook-local macro entrypoints after save.

4. Macro preservation validation:
   - Export VBA module before patch.
   - Export VBA module after patch.
   - If no VBA mutation was required, confirm module text is unchanged.
   - If VBA mutation was required, list changed procedures and confirm there are no renamed public macros.

## Stop Conditions

Stop before workbook mutation if:

- The target workbook is read-only.
- Excel reports a modal dialog or busy COM state that cannot be cleared safely.
- The requested source document cannot be parsed into a complete task list.
- Existing workbook has unsaved user edits that would be overwritten outside `Gantt_BASE`.
- Any validation macro changes would require deleting/rebuilding the VBA project.

## Approval Gate

Implementation should start only after the user approves this plan.

## Execution Result

Completed on 2026-04-24.

- Patch script: `work/TR5_PreOp_Gantt_20260415/scripts/patch_final_v8_schedule.py`
- Final validation log: `work/TR5_PreOp_Gantt_20260415/logs/final_v8_patch_20260424_114838/validation_report.json`
- Source tasks parsed: 33.
- Gantt rows written: 6 group rows plus 33 task rows.
- Timeline range: `2026-04-25` through `2026-05-17`, preserving Saturday/Sunday boundary.
- Subtitle after save: `Source: TR5_Schedule_Final_v3.md | T+0=2026-04-26 | Load-out=2026-05-06 | AGI JD=2026-05-13`.
- VBA module hash unchanged before/after patch.
- Button bindings remained workbook-local for Init, Reset, and Show Notes.
- Risk dropdown remained `OK,AMBER,HIGH,WARNING,CRITICAL,GATE`.
- Risk change smoke test passed: changing row 5 risk repainted only the task bar window and did not alter header dates or outside-window Gantt colors; original risk was restored and workbook was saved.

## Schedule Shift Validation

Completed after user confirmation that Start, Finish, and Days edits must keep automatic schedule conversion.

- VBA behavior verified in `MIR_OnChange` / `HandleShiftMode`.
- Start edit: current row duration is retained, and both upstream and downstream task rows shift by the date delta.
- Finish edit: current row start remains unchanged, Days is recalculated, and downstream task rows shift by the finish-date delta.
- Days edit: current row finish is recalculated, and downstream task rows shift by the finish-date delta.
- Smoke test row: 30, `Berth Day 2 FRA Port Ops Morning`.
- Test result: all Start, Finish, and Days cases passed.
- Restore result: schedule data restored to the pre-test snapshot, header dates unchanged, workbook saved.
- No VBA patch was required for this requirement.

## Event State Diagnosis

User reported that changing Start/End/Date data did not move adjacent schedules.

- Root cause found: Excel application-level `Application.EnableEvents` was `False`.
- Workbook event hooks were present in `ThisWorkbook`:
  - `Workbook_SheetChange` calls `modMIR_Gantt_Unified.MIR_OnChange`.
  - `Workbook_SheetSelectionChange` calls `modMIR_Gantt_Unified.MIR_OnSelectionChange`.
- Runtime fix applied: set `Application.EnableEvents=True`.
- Actual event-path smoke test passed using cell selection plus cell value entry, without direct `MIR_OnChange` invocation.
- Test result after enabling events: Start edit shifted current, upstream, and downstream rows as expected.
- Workbook data was restored to the pre-test snapshot; workbook remained unsaved because it already had unsaved state before the diagnosis.
