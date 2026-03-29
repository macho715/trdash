#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SEA TRANSIT Go/No-Go (PDF -> Gate -> Report)
Exit codes:
  0: GO
 10: CONDITIONAL
 20: NO-GO
 90: ZERO
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from pdf_parser import load_bucket_csv, parse_weather_pdf
from report_render import render_markdown_report
from sea_transit_logic import Decision, EvalParams, evaluate_sea_transit


def _float_or_none(v: Optional[str]) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sea_transit_from_pdf.py",
        description="Parse weather PDF and evaluate sea-transit Go/No-Go using 3-gate logic.",
    )
    parser.add_argument("--pdf", default=None, help="Path to weather PDF")
    parser.add_argument("--input-dir", default=None, help="Directory that contains weather materials (PDF/JPG/PNG/etc).")
    parser.add_argument("--date-root-dir", default=None, help="Root directory containing date folders (e.g., docs/weather).")
    parser.add_argument("--report-md", default=None, help="Optional markdown output path for aggregated date-root report.")
    parser.add_argument("--out-dir", default="out/sea_transit", help="Output directory")

    parser.add_argument("--hs-limit-m", default=None, help="Hs limit in meters")
    parser.add_argument("--hmax-allow-m", default=None, help="Hmax allow in meters")
    parser.add_argument("--wind-limit-kt", default=None, help="Wind limit in knots")
    parser.add_argument("--sailing-hr", default=None, help="Sailing duration in hours")
    parser.add_argument("--reserve-hr", default=None, help="Reserve duration in hours")

    parser.add_argument("--dh-squall-m", default=None, help="Additive Hs buffer for squall uncertainty")
    parser.add_argument("--dgust-kt", default=None, help="Additive wind buffer for squall uncertainty")

    parser.add_argument("--sea", choices=["gulf", "oman", "auto"], default="auto")
    parser.add_argument("--area-regex", default=None, help="Regex to filter offshore forecast areas")
    parser.add_argument("--bucket-csv", default=None, help="Optional bucket CSV: datetime,wave_ft,wind_kt,period_s")

    parser.add_argument("--dry-run", action="store_true", help="Do not write files, print summary only")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting output files")
    return parser


def _exit_code(decision: Decision) -> int:
    if decision == Decision.GO:
        return 0
    if decision == Decision.CONDITIONAL:
        return 10
    if decision == Decision.NO_GO:
        return 20
    return 90


def main() -> int:
    args = build_arg_parser().parse_args()

    selected = [bool(args.pdf), bool(args.input_dir), bool(args.date_root_dir)]
    if selected.count(True) != 1:
        print("[ERROR] Provide exactly one of --pdf, --input-dir, --date-root-dir", file=sys.stderr)
        return 90

    params = EvalParams(
        hs_limit_m=_float_or_none(args.hs_limit_m),
        hmax_allow_m=_float_or_none(args.hmax_allow_m),
        wind_limit_kt=_float_or_none(args.wind_limit_kt),
        sailing_time_hr=_float_or_none(args.sailing_hr),
        reserve_hr=_float_or_none(args.reserve_hr),
        dh_squall_m=_float_or_none(args.dh_squall_m),
        dgust_kt=_float_or_none(args.dgust_kt),
    )

    if args.input_dir:
        return _run_for_directory(args, params)
    if args.date_root_dir:
        return _run_for_date_root(args, params)

    pdf_path = Path(args.pdf or "").expanduser().resolve()
    if not pdf_path.exists() or not pdf_path.is_file():
        print(f"[ERROR] PDF not found: {pdf_path}", file=sys.stderr)
        return 90

    parsed = parse_weather_pdf(pdf_path=str(pdf_path), sea=args.sea, area_regex=args.area_regex)
    if args.bucket_csv:
        parsed.time_buckets = load_bucket_csv(args.bucket_csv)
        parsed.ssot = "bucket_csv"
    result = evaluate_sea_transit(parsed, params)

    if args.dry_run:
        print(
            json.dumps(
                {
                    "decision": result.decision.value,
                    "reason_codes": result.reason_codes,
                    "notes": result.notes,
                    "missing_inputs": result.missing_inputs,
                    "ssot": parsed.ssot,
                    "chart_detected": parsed.chart_detected,
                    "squall_unaccounted": parsed.squall_unaccounted,
                },
                indent=2,
            )
        )
        return _exit_code(result.decision)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "sea_transit_report.md"
    json_path = out_dir / "sea_transit_report.json"
    parsed_path = out_dir / "parsed_forecast.json"

    for f in [md_path, json_path, parsed_path]:
        if f.exists() and not args.overwrite:
            print(f"[ERROR] Output file exists (use --overwrite): {f}", file=sys.stderr)
            return 90

    parsed_path.write_text(json.dumps(parsed.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    json_path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown_report(str(pdf_path), parsed, params, result), encoding="utf-8")

    print(f"[OK] Wrote:\n- {md_path}\n- {json_path}\n- {parsed_path}")
    return _exit_code(result.decision)


def _run_for_directory(args: argparse.Namespace, params: EvalParams) -> int:
    bundle, exit_code = _evaluate_directory(Path(args.input_dir).expanduser().resolve(), args, params)
    if args.dry_run:
        print(json.dumps(bundle, indent=2, ensure_ascii=False))
        return exit_code

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    parsed_json = out_dir / "parsed_forecasts_by_file.json"
    gates_json = out_dir / "sea_transit_reports_by_file.json"
    report_json = out_dir / "sea_transit_folder_report.json"
    report_md = out_dir / "sea_transit_folder_report.md"

    for f in [report_json, parsed_json, gates_json, report_md]:
        if f.exists() and not args.overwrite:
            print(f"[ERROR] Output file exists (use --overwrite): {f}", file=sys.stderr)
            return 90

    report_json.write_text(json.dumps(bundle["folder_report"], indent=2, ensure_ascii=False), encoding="utf-8")
    parsed_json.write_text(json.dumps(bundle["parsed_by_file"], indent=2, ensure_ascii=False), encoding="utf-8")
    gates_json.write_text(json.dumps(bundle["reports_by_file"], indent=2, ensure_ascii=False), encoding="utf-8")
    report_md.write_text(_render_folder_markdown(bundle["folder_report"]), encoding="utf-8")
    print(f"[OK] Wrote:\n- {report_md}\n- {report_json}\n- {parsed_json}\n- {gates_json}")
    return exit_code


def _evaluate_directory(
    input_dir: Path, args: argparse.Namespace, params: EvalParams, strict_no_pdf: bool = True
) -> tuple[Dict, int]:
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"[ERROR] Input directory not found: {input_dir}", file=sys.stderr)
        return {}, 90

    all_files = sorted([p for p in input_dir.rglob("*") if p.is_file()])
    pdf_files = [p for p in all_files if p.suffix.lower() == ".pdf"]
    other_files = [p for p in all_files if p.suffix.lower() != ".pdf"]

    if not pdf_files:
        if strict_no_pdf:
            print(f"[ERROR] No PDF files found in: {input_dir}", file=sys.stderr)
        else:
            print(f"[SKIP] No PDF files found in: {input_dir}")
        return {}, 90

    per_file_rows: List[Dict] = []
    parsed_bundle: Dict[str, Dict] = {}
    gate_bundle: Dict[str, Dict] = {}

    for pdf_path in pdf_files:
        parsed = parse_weather_pdf(pdf_path=str(pdf_path), sea=args.sea, area_regex=args.area_regex)
        if args.bucket_csv:
            parsed.time_buckets = load_bucket_csv(args.bucket_csv)
            parsed.ssot = "bucket_csv"
        result = evaluate_sea_transit(parsed, params)

        rel = str(pdf_path.relative_to(input_dir))
        per_file_rows.append(
            {
                "file": rel,
                "decision": result.decision.value,
                "reason_codes": result.reason_codes,
                "missing_inputs": result.missing_inputs,
                "chart_detected": parsed.chart_detected,
                "squall_unaccounted": parsed.squall_unaccounted,
            }
        )
        parsed_bundle[rel] = parsed.to_dict()
        gate_bundle[rel] = result.to_dict()

    folder_decision = _aggregate_folder_decision([row["decision"] for row in per_file_rows])
    folder_report = {
        "input_dir": str(input_dir),
        "folder_decision": folder_decision,
        "total_files": len(all_files),
        "pdf_files": len(pdf_files),
        "non_pdf_files": len(other_files),
        "files": per_file_rows,
        "non_pdf_materials": [str(p.relative_to(input_dir)) for p in other_files],
        "params": {
            "hs_limit_m": params.hs_limit_m,
            "hmax_allow_m": params.hmax_allow_m,
            "wind_limit_kt": params.wind_limit_kt,
            "sailing_time_hr": params.sailing_time_hr,
            "reserve_hr": params.reserve_hr,
            "dh_squall_m": params.dh_squall_m,
            "dgust_kt": params.dgust_kt,
        },
    }

    return {
        "folder_report": folder_report,
        "parsed_by_file": parsed_bundle,
        "reports_by_file": gate_bundle,
    }, _exit_code_from_value(folder_decision)


def _run_for_date_root(args: argparse.Namespace, params: EvalParams) -> int:
    root_dir = Path(args.date_root_dir).expanduser().resolve()
    if not root_dir.exists() or not root_dir.is_dir():
        print(f"[ERROR] Date root directory not found: {root_dir}", file=sys.stderr)
        return 90

    date_dirs = sorted([p for p in root_dir.iterdir() if p.is_dir()])
    if not date_dirs:
        print(f"[ERROR] No date folders found under: {root_dir}", file=sys.stderr)
        return 90

    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    summaries: List[Dict] = []
    root_decisions: List[str] = []
    for date_dir in date_dirs:
        date_args = argparse.Namespace(**vars(args))
        date_args.input_dir = str(date_dir)
        date_args.date_root_dir = None
        date_args.dry_run = False
        date_args.out_dir = str(out_root / date_dir.name)
        bundle, code = _evaluate_directory(date_dir, date_args, params, strict_no_pdf=False)
        if code == 90:
            continue

        folder_report = bundle["folder_report"]
        (out_root / date_dir.name).mkdir(parents=True, exist_ok=True)
        (out_root / date_dir.name / "sea_transit_folder_report.json").write_text(
            json.dumps(folder_report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (out_root / date_dir.name / "parsed_forecasts_by_file.json").write_text(
            json.dumps(bundle["parsed_by_file"], indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (out_root / date_dir.name / "sea_transit_reports_by_file.json").write_text(
            json.dumps(bundle["reports_by_file"], indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (out_root / date_dir.name / "sea_transit_folder_report.md").write_text(
            _render_folder_markdown(folder_report), encoding="utf-8"
        )
        summaries.append(
            {
                "date_folder": date_dir.name,
                "folder_decision": folder_report["folder_decision"],
                "pdf_files": folder_report["pdf_files"],
                "non_pdf_files": folder_report["non_pdf_files"],
                "output_dir": str((out_root / date_dir.name).resolve()),
            }
        )
        root_decisions.append(folder_report["folder_decision"])

    overall = {
        "date_root_dir": str(root_dir),
        "overall_decision": _aggregate_folder_decision(root_decisions) if root_decisions else "ZERO",
        "date_folders_processed": len(summaries),
        "items": summaries,
    }

    root_json = out_root / "sea_transit_date_root_report.json"
    root_md = Path(args.report_md) if args.report_md else out_root / "sea_transit_date_root_report.md"
    for f in [root_json, root_md]:
        if f.exists() and not args.overwrite:
            print(f"[ERROR] Output file exists (use --overwrite): {f}", file=sys.stderr)
            return 90

    root_json.write_text(json.dumps(overall, indent=2, ensure_ascii=False), encoding="utf-8")
    root_md.write_text(_render_date_root_markdown(overall), encoding="utf-8")

    print(f"[OK] Wrote:\n- {root_md}\n- {root_json}")
    return _exit_code_from_value(overall["overall_decision"])


def _aggregate_folder_decision(decisions: List[str]) -> str:
    # Conservative ordering for ops: NO-GO > CONDITIONAL > ZERO > GO
    if "NO-GO" in decisions:
        return "NO-GO"
    if "CONDITIONAL" in decisions:
        return "CONDITIONAL"
    if "ZERO" in decisions:
        return "ZERO"
    return "GO"


def _exit_code_from_value(value: str) -> int:
    if value == "GO":
        return 0
    if value == "CONDITIONAL":
        return 10
    if value == "NO-GO":
        return 20
    return 90


def _render_folder_markdown(bundle: Dict) -> str:
    lines: List[str] = []
    lines.append("# SEA TRANSIT Folder Report")
    lines.append("")
    lines.append(f"- InputDir: `{bundle['input_dir']}`")
    lines.append(f"- FolderDecision: **{bundle['folder_decision']}**")
    lines.append(f"- Files: total={bundle['total_files']} / pdf={bundle['pdf_files']} / non_pdf={bundle['non_pdf_files']}")
    lines.append("")
    lines.append("## Per-PDF Decisions")
    lines.append("")
    lines.append("| File | Decision | ReasonCodes | MissingInputs | Chart | SquallUnaccounted |")
    lines.append("|---|---|---|---|---:|---:|")
    for row in bundle["files"]:
        lines.append(
            f"| {row['file']} | {row['decision']} | {','.join(row['reason_codes']) or 'N/A'} | "
            f"{','.join(row['missing_inputs']) or 'N/A'} | {str(row['chart_detected']).lower()} | {str(row['squall_unaccounted']).lower()} |"
        )
    lines.append("")
    lines.append("## Non-PDF Materials")
    lines.append("")
    if not bundle["non_pdf_materials"]:
        lines.append("- None")
    else:
        for item in bundle["non_pdf_materials"]:
            lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def _render_date_root_markdown(report: Dict) -> str:
    lines: List[str] = []
    lines.append("# SEA TRANSIT Date-Root Report")
    lines.append("")
    lines.append(f"- DateRootDir: `{report['date_root_dir']}`")
    lines.append(f"- OverallDecision: **{report['overall_decision']}**")
    lines.append(f"- DateFoldersProcessed: {report['date_folders_processed']}")
    lines.append("")
    lines.append("## Folder Summaries")
    lines.append("")
    lines.append("| DateFolder | Decision | PDF Files | Non-PDF Files | OutputDir |")
    lines.append("|---|---|---:|---:|---|")
    for item in report["items"]:
        lines.append(
            f"| {item['date_folder']} | {item['folder_decision']} | {item['pdf_files']} | "
            f"{item['non_pdf_files']} | {item['output_dir']} |"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
