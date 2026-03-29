# SKILL.md Minimal Expansion Plan (Aligned to `weather_pipeline.md`)

## Summary
Expand `C:\tr_dash-main\.agents\skills\sea-transit-go-nogo\SKILL.md` using `C:\tr_dash-main\weather_pipeline.md` as reference, while keeping the document concise and implementation-accurate.

Chosen direction:
- Scope: `Procedure + Commands + Outputs` only
- Operating baseline: current implemented behavior first
- Language: English
- No large code blocks or full pipeline transplant into SKILL.md

This keeps SKILL.md as an operational runbook, not a design spec.

## Intent and Success Criteria
- Keep SKILL.md aligned with what currently works in repo.
- Add only actionable operator steps from weather pipeline context:
  - chart-PDF handling pathway
  - bucket evidence pathway
  - post-processing reporting pathway
- Avoid documenting unimplemented OCR automation as required/default behavior.

Success is:
1. SKILL.md clearly tells an agent/operator what to run now.
2. SKILL.md reflects current reason-code behavior (`WX_CHART_NEEDS_OCR`, `WX_WINDOW_GAP`).
3. SKILL.md stays compact and passes skill validation.

## Planned Changes (File-Level)

### 1) Update `SKILL.md` Procedure section
Add concise branch logic:
- Parse/evaluate with `sea_transit_from_pdf.py` as default.
- If chart-style PDF cannot produce usable series:
  - classify as chart-limited (`WX_CHART_NEEDS_OCR`)
  - treat Gate-C as unproven without bucket series (`WX_WINDOW_GAP`)
- Optional resolution path:
  - provide `--bucket-csv` for time-bucket evidence
  - regenerate integrated report via `files/weather_go_nogo.py --date-folder`

Do not introduce “OCR always runs” wording.

### 2) Update `SKILL.md` Commands section
Add compact command set (no long scripts):
- Existing sea-transit evaluate commands remain authoritative.
- Add explicit bucket-assisted rerun command (single PDF/folder form).
- Add integrated reporting command (already present but normalize wording and placement):
  - `python files/weather_go_nogo.py --date-folder <YYYYMMDD> --out-root out/sea_transit`

### 3) Update `SKILL.md` Outputs section
Ensure output contract is explicit and grouped:
- Core evaluator outputs:
  - `sea_transit_*` files
- Integrated report outputs:
  - `weather_go_nogo_report.md`
  - `weather_go_nogo_report.json`
  - `weather_go_nogo_report.html`
- Clarify output location by mode (`<out-dir>` vs `<out-root>/<YYYYMMDD>`).

## Public APIs / Interfaces / Types
No Python API signature changes are planned.
No schema migrations are planned.
This is documentation-only alignment.

## Validation Plan
1. Skill format validation:
- Run `quick_validate.py` against the skill folder.
2. Command consistency checks:
- Verify each command listed in SKILL.md exists and runs with `--help`.
3. Behavior consistency check:
- Ensure documented reason codes match current outputs in:
  - `out/sea_transit/<date>/sea_transit_reports_by_file.json`
  - `out/sea_transit/<date>/weather_go_nogo_report.json`

## Test Cases and Scenarios
1. Chart-limited scenario:
- Input folder contains TR02/TR07 chart PDFs with no bucket CSV.
- Expected docs state: `CONDITIONAL` with `WX_CHART_NEEDS_OCR` and `WX_WINDOW_GAP`.
2. Bucket-assisted scenario:
- Same folder with valid `--bucket-csv`.
- Expected docs state Gate-C can be proven when continuous window evidence is present.
3. Report generation scenario:
- `weather_go_nogo.py --date-folder YYYYMMDD` produces three report artifacts.
- Expected docs list exact filenames and locations.
4. Compatibility scenario:
- Existing basic commands in SKILL.md continue to work unchanged.

## Assumptions and Defaults
- Current code behavior is source of truth over design drafts.
- `weather_pipeline.md` is treated as reference for wording/flow, not as mandatory implementation spec.
- SKILL.md remains concise operational guidance (no embedded large OCR code).
- Any future OCR auto-digitization will be documented later as optional/roadmap only after implementation lands.
