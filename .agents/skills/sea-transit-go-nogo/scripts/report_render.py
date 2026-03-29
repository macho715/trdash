# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import List, Optional

from pdf_parser import ParsedForecast
from sea_transit_logic import Decision, EvalParams, EvalResult, ft_to_m


def _fmt(x: Optional[float]) -> str:
    return "N/A" if x is None else f"{x:.2f}"


def render_markdown_report(pdf_path: str, parsed: ParsedForecast, params: EvalParams, result: EvalResult) -> str:
    lines: List[str] = []
    lines.append("# SEA TRANSIT Go/No-Go Report")
    lines.append("")
    lines.append(f"- Source PDF: `{pdf_path}`")
    lines.append(
        f"- SSOT: `{parsed.ssot}` | chart_detected={str(parsed.chart_detected).lower()} | "
        f"squall_unaccounted={str(parsed.squall_unaccounted).lower()}"
    )
    lines.append("")

    lines.append("## Exec")
    lines.append(f"1) Decision: **{result.decision.value}**")
    if result.decision == Decision.ZERO:
        lines.append(f"2) Basis: missing mandatory inputs/evidence -> ZERO (missing={', '.join(result.missing_inputs)})")
    else:
        lines.append(f"2) Basis: gate outcomes (ReasonCodes={', '.join(result.reason_codes) if result.reason_codes else 'N/A'})")
    lines.append("3) Action: fill threshold/time/buffer inputs and re-run; use bucket CSV for robust Gate-C if needed.")
    lines.append("")

    lines.append("## Inputs")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Hs_limit_m | {_fmt(params.hs_limit_m)} |")
    lines.append(f"| Hmax_allow_m | {_fmt(params.hmax_allow_m)} |")
    lines.append(f"| Wind_limit_kt | {_fmt(params.wind_limit_kt)} |")
    lines.append(f"| SailingTime_hr | {_fmt(params.sailing_time_hr)} |")
    lines.append(f"| Reserve_hr | {_fmt(params.reserve_hr)} |")
    lines.append(f"| dH_squall_m | {_fmt(params.dh_squall_m)} |")
    lines.append(f"| dGust_kt | {_fmt(params.dgust_kt)} |")
    lines.append("")

    lines.append("## Parsed Observations")
    lines.append("")
    if not parsed.observations and not parsed.time_buckets:
        lines.append("> No extractable wave/wind values were found.")
    else:
        lines.append("| No | Scope | ValidFrom | ValidTo | Wave(ft) worst | Hs(m) worst | Wind(kt) worst | Period(s) worst | Evidence(Page) |")
        lines.append("|-:|---|---|---|---:|---:|---:|---:|---|")
        idx = 0
        for obs in parsed.observations:
            idx += 1
            wave_ft = obs.wave_ft.worst_case()
            hs_m = ft_to_m(wave_ft) if wave_ft is not None else None
            wind_kt = obs.wind_kt.worst_case()
            period_s = obs.period_s.worst_case()
            pages = ",".join(sorted({str(e.page) for e in obs.evidence})) if obs.evidence else "N/A"
            lines.append(
                f"| {idx} | {obs.scope} | {obs.valid_from or 'N/A'} | {obs.valid_to or 'N/A'} | "
                f"{_fmt(wave_ft)} | {_fmt(hs_m)} | {_fmt(wind_kt)} | {_fmt(period_s)} | {pages} |"
            )

        if parsed.time_buckets:
            lines.append("")
            lines.append("### Time Buckets (SSOT)")
            lines.append("| No | datetime | wave_ft | wind_kt | period_s |")
            lines.append("|-:|---|---:|---:|---:|")
            for i, bucket in enumerate(parsed.time_buckets, start=1):
                lines.append(f"| {i} | {bucket.datetime_iso} | {bucket.wave_ft:.2f} | {bucket.wind_kt:.2f} | {_fmt(bucket.period_s)} |")
    lines.append("")

    lines.append("## Gates")
    lines.append("")
    lines.append("| Gate | Pass | Detail | ReasonCode |")
    lines.append("|---|---:|---|---|")
    for gate in result.gates:
        lines.append(f"| {gate.gate} | {('N/A' if gate.passed is None else str(gate.passed).lower())} | {gate.detail} | {gate.reason_code or ''} |")
    lines.append("")

    lines.append("## External Basis")
    lines.append("- Hs definition: NOAA/NDBC (WVHT approximates significant wave height).")
    lines.append("- Peak-wave conservative estimate: Hmax ~= 1.86 * Hs (about 1000 waves).")
    lines.append("- Marine transport decision requires continuous weather window, not a single instant.")
    lines.append("")

    if result.decision == Decision.ZERO:
        lines.append("## ZERO Log")
        lines.append("| Step | Reason | Risk | Requested data | Next action |")
        lines.append("|---|---|---|---|---|")
        req = ", ".join(result.missing_inputs) if result.missing_inputs else "N/A"
        lines.append(f"| Threshold/Time freeze | Required inputs missing | Under/over-conservative decision | {req} | Provide data and re-run |")
        lines.append("")

    return "\n".join(lines)
