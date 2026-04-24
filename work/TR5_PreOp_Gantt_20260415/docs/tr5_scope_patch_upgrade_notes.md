# TR5 Scope Patch Upgrade Notes

## What changed
- Keeps the original **sidecar → validate → promote/rollback** flow.
- Adds **CLI parameters** for target path, dates, sheet, rows, and timeline columns.
- Adds **file logger** (`scope_patch.log`) and richer `validation_report.json`.
- Adds **safe COM lifecycle** with an isolated Excel instance and workbook open retries.
- Adds **no-promote mode** (`--no-promote`) for sidecar-only validation.
- Adds **empty task-row guard** so the script fails cleanly instead of crashing.
- Replaces the fragile openpyxl private access (`_cf_rules`) with public iteration over worksheet conditional formatting.
- Strengthens package integrity checks by comparing protected ZIP parts such as:
  - `xl/vbaProject.bin`
  - `xl/drawings/drawing*.xml`
  - `xl/drawings/vmlDrawing*.vml`
  - `xl/ctrlProps/*.xml`
- Uses **atomic promotion** (`os.replace`) after copying the validated sidecar.

## Default behavior
The upgraded script preserves the original business defaults unless you override them:
- Sheet: `Gantt_BASE`
- Task rows: `4:42`
- Timeline: `K:AE`
- Timeline dates: `2026-04-27` to `2026-05-17`
- Source label: `TR5_Pre-Op_Simulation_v2_20260430.md`

## Examples

### 1) Validate sidecar only
```bash
py tr5_fix_date_and_gantt_scope_upgraded.py --no-promote
```

### 2) Promote after validation
```bash
py tr5_fix_date_and_gantt_scope_upgraded.py
```

### 3) Override target workbook
```bash
py tr5_fix_date_and_gantt_scope_upgraded.py --target "C:\tr_dash-main\output\spreadsheet\tr5_preparation_simulation\TR5_Preparation_Simulation_Gantt_MIR_Format_COM.xlsm"
```

### 4) Override subtitle dates
```bash
py tr5_fix_date_and_gantt_scope_upgraded.py ^
  --today 2026-04-16 ^
  --t-plus-zero 2026-05-01 ^
  --load-out 2026-05-10 ^
  --agi-jd 2026-05-18
```

## Outputs
Each run creates a timestamped run folder containing:
- sidecar workbook
- backup workbook
- `validation_report.json`
- `scope_patch.log`

## Companion VBA
A VBA launcher module is included as `Run_TR5_Scope_Patch.bas`.
