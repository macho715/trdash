---
name: sea-transit-go-nogo
description: "Parse marine weather PDFs (2-day/7-day trends, offshore forecast, sea state) and evaluate sea-transit Go/No-Go using a deterministic 3-gate method: threshold check, squall/peak-wave conservative buffer, and continuous weather-window check. Use when asked to judge sailing feasibility from PDF wave height in ft (combined sea+swell treated as Hs assumption), wind in kt, squall caveat handling, and report generation (.md + .json)."
---

# SEA TRANSIT Go/No-Go (PDF -> Gate -> Report)

Use local PDF data as SSOT for extraction.
If chart buckets cannot be parsed from images, use `--bucket-csv` as manual SSOT for Gate-C.
Use `references/SOURCES.md` for source assumptions and `references/REPORT_SCHEMA.md` for output schema details.

## Input Modes
1. Single PDF: `--pdf <path>`
2. Folder batch: `--input-dir <path>` (parse all files, evaluate every PDF, include non-PDF inventory)
3. Date-root batch: `--date-root-dir <path>` (evaluate all date folders in one run)

## Required Parameters
1. Limits:
- `--hs-limit-m <float>` or `--hmax-allow-m <float>`
- `--wind-limit-kt <float>`
2. Transit time:
- `--sailing-hr <float>`
- `--reserve-hr <float>`

## Recommended Parameters
1. Squall buffers:
- `--dh-squall-m <float>`
- `--dgust-kt <float>`

## Optional Filters
1. `--sea gulf|oman|auto`
2. `--area-regex "<regex>"`
3. `--bucket-csv <path>`

## Procedure
1. Default path: parse and evaluate with `sea_transit_from_pdf.py`.
2. Parse text blocks from PDF:
- offshore forecast lines (`WIND/WAVE/PERIOD`)
- sea-state lines
- validity window in either format:
  - `VALID FROM: 0800 ON dd/mm/yyyy TO: 2000 ON dd/mm/yyyy`
  - `VALID 0800-2000 dd/mm/yyyy LT`
- squall caveat phrase
3. Parse chart-style station wave labels when available (for chart/trend pages only):
- examples: `USSC 1-2FT`, `ARZANA 2FT`, `SW FATEH 2-3 FT`
4. Evaluate gates:
- Gate-A: check `Hs <= limit` and `Wind <= limit`
- Gate-B: if squall caveat exists, apply `Hs_eff = Hs + dH`, `Wind_eff = Wind + dGust`, then optional peak-wave check `Hmax ~= 1.86 * Hs_eff`
- Gate-C: require one continuous GO window for `SailingTime + Reserve`
5. Branch handling for chart-limited PDFs:
- if usable numeric series cannot be extracted from chart-style pages, classify as `WX_CHART_NEEDS_OCR`
- treat Gate-C as unproven without bucket evidence (`WX_WINDOW_GAP`)
- optional resolution: provide `--bucket-csv` and rerun.
6. Write core evaluator outputs:
- `sea_transit_report.md`
- `sea_transit_report.json`
- `parsed_forecast.json`
7. Optional integrated post-processing report:
- run `files/weather_go_nogo.py --date-folder <YYYYMMDD>` to generate integrated report files (`.md + .json + .html`) from `out/sea_transit/<YYYYMMDD>/...` JSON outputs.

Core evaluator outputs by mode:

Single PDF mode writes:
- `sea_transit_report.md`
- `sea_transit_report.json`
- `parsed_forecast.json`

Batch mode (`--input-dir`) writes:
- `sea_transit_folder_report.md`
- `sea_transit_folder_report.json`
- `parsed_forecasts_by_file.json`
- `sea_transit_reports_by_file.json`

Date-root mode (`--date-root-dir`) writes:
- `<out-dir>/<YYYYMMDD>/sea_transit_folder_report.md`
- `<out-dir>/<YYYYMMDD>/sea_transit_folder_report.json`
- `<out-dir>/<YYYYMMDD>/parsed_forecasts_by_file.json`
- `<out-dir>/<YYYYMMDD>/sea_transit_reports_by_file.json`
- `<out-dir>/sea_transit_date_root_report.json`
- `--report-md` path (or `<out-dir>/sea_transit_date_root_report.md`)

Integrated report mode (`weather_go_nogo.py --date-folder`) writes:
- `<out-root>/<YYYYMMDD>/weather_go_nogo_report.md`
- `<out-root>/<YYYYMMDD>/weather_go_nogo_report.json`
- `<out-root>/<YYYYMMDD>/weather_go_nogo_report.html`

## Commands
Install dependencies:
`python -m pip install -r .agents/skills/sea-transit-go-nogo/scripts/requirements.txt`

Dry run:
`python .agents/skills/sea-transit-go-nogo/scripts/sea_transit_from_pdf.py --pdf /path/to/weather.pdf --dry-run`

Folder dry run:
`python .agents/skills/sea-transit-go-nogo/scripts/sea_transit_from_pdf.py --input-dir /path/to/date-folder --hs-limit-m 3.0 --hmax-allow-m 5.5 --wind-limit-kt 25 --sailing-hr 12 --reserve-hr 0 --dry-run`

Report run:
`python .agents/skills/sea-transit-go-nogo/scripts/sea_transit_from_pdf.py --pdf /path/to/weather.pdf --hs-limit-m 1.50 --wind-limit-kt 20.00 --sailing-hr 6.00 --reserve-hr 2.00 --dh-squall-m 0.30 --dgust-kt 5.00 --out-dir out/sea_transit`

With bucket CSV:
`python .agents/skills/sea-transit-go-nogo/scripts/sea_transit_from_pdf.py --pdf /path/to/weather.pdf --bucket-csv .agents/skills/sea-transit-go-nogo/assets/example_bucket.csv --hs-limit-m 1.50 --wind-limit-kt 20.00 --sailing-hr 6.00 --reserve-hr 2.00 --dh-squall-m 0.30 --dgust-kt 5.00 --out-dir out/sea_transit`

Bucket-assisted folder rerun:
`python .agents/skills/sea-transit-go-nogo/scripts/sea_transit_from_pdf.py --input-dir /path/to/date-folder --bucket-csv /path/to/bucket.csv --hs-limit-m 3.0 --hmax-allow-m 5.5 --wind-limit-kt 25 --sailing-hr 12 --reserve-hr 0 --out-dir out/sea_transit_folder --overwrite`

Folder report:
`python .agents/skills/sea-transit-go-nogo/scripts/sea_transit_from_pdf.py --input-dir /path/to/date-folder --hs-limit-m 3.0 --hmax-allow-m 5.5 --wind-limit-kt 25 --sailing-hr 12 --reserve-hr 0 --out-dir out/sea_transit_folder --overwrite`

Date-root report to docs markdown:
`python .agents/skills/sea-transit-go-nogo/scripts/sea_transit_from_pdf.py --date-root-dir docs/weather --hs-limit-m 3.0 --hmax-allow-m 5.5 --wind-limit-kt 25 --sailing-hr 12 --reserve-hr 0 --out-dir out/sea_transit_date_root --report-md docs/weather/pdf_weather.md --overwrite`

Integrated report from skill outputs:
`python files/weather_go_nogo.py --date-folder 20260203 --out-root out/sea_transit`

## Decision Outcomes
- Missing required threshold/time inputs -> `ZERO`
- No extractable wave/wind numbers from non-chart PDF -> `ZERO` (`WX_PARSE_FAIL`)
- Chart PDF detected but no usable numeric series from text layer -> `CONDITIONAL` (`WX_CHART_NEEDS_OCR`)
- Squall caveat present but no buffer values -> `CONDITIONAL`
- No valid time buckets for window proof -> `CONDITIONAL` (`WX_WINDOW_GAP`)

## Safety
- Do not call external network services.
- Read local files only.
- For core evaluator, write outputs only under `--out-dir`.
- For integrated report mode, write outputs under `<out-root>/<YYYYMMDD>`.
- Include evidence snippets (page + text) in parsed output for audit traceability.
