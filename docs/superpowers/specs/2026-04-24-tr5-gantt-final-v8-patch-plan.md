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

## Execution Mode

MStack dispatch decision: direct execution.

- Estimated changed files: 1 new patch script plus optional log/report output.
- Workbook mutation surface: `Gantt_BASE` rows, formulas, date headers, VBA/Named Range values only if needed.
- Coupling risk: medium-high because date rows, formula subtitle, buttons, protection, and VBA repaint all interact.
- Subagents: not used. The task is workbook-contract sensitive and should remain single-writer.

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

2. Data validation:
   - Verify source milestones:
     - G1 PTW Approved = `2026-04-29`
     - G2 HM Approval Received = `2026-05-04`
     - Bushra All Fast = `2026-05-04`
     - RoRo Load-out = `2026-05-06`
     - AGI JD Complete = `2026-05-13`
   - Verify no `#REF!`, `#VALUE!`, `#NAME?`, or blank required dates in key range.

3. Save/reopen validation:
   - Save workbook.
   - Reopen/read saved `.xlsm` with `keep_vba=True` where possible.
   - Verify title/subtitle, date headers, row count, task list, and formulas persisted.

## Stop Conditions

Stop before workbook mutation if:

- The target workbook is read-only.
- Excel reports a modal dialog or busy COM state that cannot be cleared safely.
- The requested source document cannot be parsed into a complete task list.
- Existing workbook has unsaved user edits that would be overwritten outside `Gantt_BASE`.
- Any validation macro changes would require deleting/rebuilding the VBA project.

## Approval Gate

Implementation should start only after the user approves this plan.
