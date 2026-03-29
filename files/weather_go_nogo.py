#!/usr/bin/env python3
"""
Weather Go/No-Go for SEA TRANSIT (AGI Schedule Pipeline Step 4)

Evaluates marine weather conditions using 3-Gate logic:
- Gate-A: Basic wave/wind thresholds
- Gate-B: Squall buffer + Hmax estimation
- Gate-C: Continuous weather window

Part of integrated pipeline: shift(1) → daily-update(2) → pipeline-check(3) → weather-go-nogo(4)
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import os
from pathlib import Path


@dataclass
class WeatherInput:
    """Input weather data for Go/No-Go evaluation"""
    wave_ft: float  # Combined sea+swell wave height (feet)
    wind_kt: float  # Wind speed (knots)
    timestamp: datetime
    wave_period_s: Optional[float] = None  # Wave period (seconds), optional


@dataclass
class GoNoGoLimits:
    """Operational limits for sea transit"""
    Hs_limit_m: float = 3.0  # Max allowed significant wave height (meters)
    Wind_limit_kt: float = 25.0  # Max allowed wind speed (knots)
    SailingTime_hr: float = 8.0  # Expected sailing time (hours)
    Reserve_hr: float = 4.0  # Reserve time for safety (hours)
    ΔHs_squall_m: float = 0.5  # Squall wave buffer (meters)
    ΔGust_kt: float = 10.0  # Gust wind buffer (knots)
    Hmax_allow_m: float = 5.5  # Max allowed peak wave height (meters)


@dataclass
class GateResult:
    """Result from a single gate evaluation"""
    passed: bool
    reason_codes: List[str]
    details: str


@dataclass
class GoNoGoResult:
    """Final Go/No-Go decision"""
    decision: str  # "GO" | "NO-GO" | "CONDITIONAL"
    reason_codes: List[str]
    gate_a: GateResult
    gate_b: Optional[GateResult]
    gate_c: GateResult
    rationale: str
    recommendations: List[str]


def ft_to_m(feet: float) -> float:
    """Convert feet to meters"""
    return feet * 0.3048


def evaluate_gate_a(
    weather: WeatherInput, 
    limits: GoNoGoLimits
) -> GateResult:
    """
    Gate-A: Basic Threshold
    - Hs_m ≤ Hs_limit_m AND Wind_kt ≤ Wind_limit_kt → GO
    - Otherwise → NO-GO
    """
    Hs_m = ft_to_m(weather.wave_ft)
    reason_codes = []
    details_parts = []
    
    wave_ok = Hs_m <= limits.Hs_limit_m
    wind_ok = weather.wind_kt <= limits.Wind_limit_kt
    
    if not wave_ok:
        reason_codes.append("WX_WAVE")
        details_parts.append(
            f"Wave height {Hs_m:.2f}m exceeds limit {limits.Hs_limit_m}m"
        )
    
    if not wind_ok:
        reason_codes.append("WX_WIND")
        details_parts.append(
            f"Wind speed {weather.wind_kt}kt exceeds limit {limits.Wind_limit_kt}kt"
        )
    
    passed = wave_ok and wind_ok
    details = " AND ".join(details_parts) if details_parts else "All thresholds within limits"
    
    return GateResult(passed=passed, reason_codes=reason_codes, details=details)


def evaluate_gate_b(
    weather: WeatherInput,
    limits: GoNoGoLimits
) -> GateResult:
    """
    Gate-B: Squall/Peak Wave Buffer
    - Apply squall buffers to get effective values
    - Estimate Hmax = 1.86 × Hs_eff
    - Check if Hmax_est > Hmax_allow_m
    """
    Hs_m = ft_to_m(weather.wave_ft)
    Hs_eff = Hs_m + limits.ΔHs_squall_m
    Wind_eff = weather.wind_kt + limits.ΔGust_kt
    Hmax_est = 1.86 * Hs_eff
    
    reason_codes = []
    details_parts = []
    
    wave_ok = Hs_eff <= limits.Hs_limit_m
    wind_ok = Wind_eff <= limits.Wind_limit_kt
    hmax_ok = Hmax_est <= limits.Hmax_allow_m
    
    if not wave_ok:
        reason_codes.append("WX_WAVE_SQUALL")
        details_parts.append(
            f"Wave with squall buffer {Hs_eff:.2f}m exceeds limit {limits.Hs_limit_m}m"
        )
    
    if not wind_ok:
        reason_codes.append("WX_WIND_GUST")
        details_parts.append(
            f"Wind with gust {Wind_eff:.1f}kt exceeds limit {limits.Wind_limit_kt}kt"
        )
    
    if not hmax_ok:
        reason_codes.append("WX_HMAX")
        details_parts.append(
            f"Estimated Hmax {Hmax_est:.2f}m exceeds limit {limits.Hmax_allow_m}m"
        )
    
    passed = wave_ok and wind_ok and hmax_ok
    details = " AND ".join(details_parts) if details_parts else "Squall buffers within limits"
    
    return GateResult(passed=passed, reason_codes=reason_codes, details=details)


def evaluate_gate_c(
    weather_series: List[WeatherInput],
    limits: GoNoGoLimits,
    gate_a_results: List[GateResult],
    gate_b_results: Optional[List[GateResult]] = None
) -> GateResult:
    """
    Gate-C: Continuous Weather Window
    - Requires (SailingTime + Reserve) hours of continuous GO conditions
    - All time buckets in window must pass Gate-A (and Gate-B if used)
    """
    required_window_hr = limits.SailingTime_hr + limits.Reserve_hr
    
    # Find continuous GO windows
    continuous_go_hours = 0
    max_continuous = 0
    reason_codes = []
    
    for i, (weather, gate_a) in enumerate(zip(weather_series, gate_a_results)):
        gate_b = gate_b_results[i] if gate_b_results else None
        
        # Check if this time bucket is GO
        is_go = gate_a.passed
        if gate_b is not None:
            is_go = is_go and gate_b.passed
        
        if is_go:
            continuous_go_hours += 1
            max_continuous = max(max_continuous, continuous_go_hours)
        else:
            continuous_go_hours = 0
            if not gate_a.reason_codes:
                reason_codes.extend(gate_a.reason_codes)
            if gate_b and gate_b.reason_codes:
                reason_codes.extend(gate_b.reason_codes)
    
    passed = max_continuous >= required_window_hr
    
    if passed:
        details = f"Continuous window of {max_continuous:.1f}hr ≥ required {required_window_hr:.1f}hr"
    else:
        details = f"Max continuous window {max_continuous:.1f}hr < required {required_window_hr:.1f}hr"
        reason_codes.append("WX_WINDOW_INSUFFICIENT")
    
    return GateResult(
        passed=passed,
        reason_codes=list(set(reason_codes)),  # Remove duplicates
        details=details
    )


def evaluate_go_nogo(
    weather_series: List[WeatherInput],
    limits: GoNoGoLimits,
    use_gate_b: bool = True
) -> GoNoGoResult:
    """
    Complete 3-Gate Go/No-Go evaluation
    
    Args:
        weather_series: Time series of weather data (hourly)
        limits: Operational limits
        use_gate_b: Whether to apply Gate-B squall buffer logic
    
    Returns:
        GoNoGoResult with final decision
    """
    # Evaluate Gate-A for all time points
    gate_a_results = [evaluate_gate_a(w, limits) for w in weather_series]
    
    # Evaluate Gate-B if requested
    gate_b_results = None
    if use_gate_b:
        gate_b_results = [evaluate_gate_b(w, limits) for w in weather_series]
    
    # Evaluate Gate-C (continuous window)
    gate_c_result = evaluate_gate_c(
        weather_series, limits, gate_a_results, gate_b_results
    )
    
    # Aggregate all reason codes
    all_reason_codes = set()
    for result in gate_a_results:
        all_reason_codes.update(result.reason_codes)
    if gate_b_results:
        for result in gate_b_results:
            all_reason_codes.update(result.reason_codes)
    all_reason_codes.update(gate_c_result.reason_codes)
    
    # Determine final decision
    if gate_c_result.passed:
        decision = "GO"
        rationale = f"All gates passed. {gate_c_result.details}"
        recommendations = [
            "Monitor weather continuously during transit",
            "Prepare contingency plans if conditions deteriorate",
            "Confirm latest forecast before departure"
        ]
    else:
        decision = "NO-GO"
        rationale = f"Gate-C failed. {gate_c_result.details}"
        recommendations = [
            "Wait for weather window to improve",
            "Monitor 2-day hourly forecasts for next opportunity",
            "Consider alternative timing or route if available"
        ]
    
    # Check for marginal conditions (CONDITIONAL)
    marginal_conditions = False
    for gate_a in gate_a_results:
        if gate_a.passed:
            # Check if close to limits
            for weather in weather_series:
                Hs_m = ft_to_m(weather.wave_ft)
                if Hs_m > limits.Hs_limit_m * 0.85 or weather.wind_kt > limits.Wind_limit_kt * 0.85:
                    marginal_conditions = True
                    break
    
    if decision == "GO" and marginal_conditions:
        decision = "CONDITIONAL"
        recommendations.insert(0, "Weather is near operational limits - proceed with caution")
    
    return GoNoGoResult(
        decision=decision,
        reason_codes=list(all_reason_codes),
        gate_a=GateResult(
            passed=all(r.passed for r in gate_a_results),
            reason_codes=list(set(sum([r.reason_codes for r in gate_a_results], []))),
            details=f"{sum(r.passed for r in gate_a_results)}/{len(gate_a_results)} time points passed"
        ),
        gate_b=GateResult(
            passed=all(r.passed for r in gate_b_results) if gate_b_results else None,
            reason_codes=list(set(sum([r.reason_codes for r in gate_b_results], []))) if gate_b_results else [],
            details=f"{sum(r.passed for r in gate_b_results)}/{len(gate_b_results)} time points passed" if gate_b_results else "Not evaluated"
        ) if use_gate_b else None,
        gate_c=gate_c_result,
        rationale=rationale,
        recommendations=recommendations
    )


def format_html_output(result: GoNoGoResult, limits: GoNoGoLimits) -> str:
    """
    Format Go/No-Go result as HTML block for AGI TR SCHEDULE
    Following DASHBOARD_OUTPUT_SCHEMA.md format
    """
    # Color coding
    color_map = {
        "GO": "#10b981",  # Green
        "NO-GO": "#ef4444",  # Red
        "CONDITIONAL": "#eab308"  # Yellow
    }
    bg_color_map = {
        "GO": "rgba(16, 185, 129, 0.1)",
        "NO-GO": "rgba(239, 68, 68, 0.1)",
        "CONDITIONAL": "rgba(234, 179, 8, 0.1)"
    }
    
    color = color_map.get(result.decision, "#64748b")
    bg_color = bg_color_map.get(result.decision, "rgba(100, 116, 139, 0.1)")
    
    html = f"""
        <div class="weather-gonogo-section" style="
            background: {bg_color};
            border: 2px solid {color};
            border-radius: 12px;
            padding: 20px;
            margin: 20px 0;
        ">
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                <div style="
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                    background: {color};
                    box-shadow: 0 0 12px {color};
                "></div>
                <h3 style="margin: 0; font-size: 18px; font-weight: 600; color: var(--text-primary);">
                    SEA TRANSIT Weather Go/No-Go
                </h3>
            </div>
            
            <div style="
                background: {color};
                color: white;
                padding: 16px 24px;
                border-radius: 8px;
                font-size: 24px;
                font-weight: 700;
                text-align: center;
                margin-bottom: 16px;
                text-transform: uppercase;
                letter-spacing: 2px;
            ">
                {result.decision}
            </div>
            
            <div style="margin-bottom: 16px;">
                <div style="font-weight: 600; color: var(--text-secondary); margin-bottom: 8px;">
                    Rationale:
                </div>
                <div style="color: var(--text-primary); line-height: 1.6;">
                    {result.rationale}
                </div>
            </div>
            
            <div style="margin-bottom: 16px;">
                <div style="font-weight: 600; color: var(--text-secondary); margin-bottom: 8px;">
                    Gate Results:
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px;">
                    <div style="background: var(--bg-tertiary); padding: 12px; border-radius: 8px;">
                        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Gate-A (Basic)</div>
                        <div style="color: {'#10b981' if result.gate_a.passed else '#ef4444'}; font-weight: 600;">
                            {'✓ PASS' if result.gate_a.passed else '✗ FAIL'}
                        </div>
                        <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">
                            {result.gate_a.details}
                        </div>
                    </div>
"""
    
    if result.gate_b:
        html += f"""
                    <div style="background: var(--bg-tertiary); padding: 12px; border-radius: 8px;">
                        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Gate-B (Squall)</div>
                        <div style="color: {'#10b981' if result.gate_b.passed else '#ef4444'}; font-weight: 600;">
                            {'✓ PASS' if result.gate_b.passed else '✗ FAIL'}
                        </div>
                        <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">
                            {result.gate_b.details}
                        </div>
                    </div>
"""
    
    html += f"""
                    <div style="background: var(--bg-tertiary); padding: 12px; border-radius: 8px;">
                        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">Gate-C (Window)</div>
                        <div style="color: {'#10b981' if result.gate_c.passed else '#ef4444'}; font-weight: 600;">
                            {'✓ PASS' if result.gate_c.passed else '✗ FAIL'}
                        </div>
                        <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">
                            {result.gate_c.details}
                        </div>
                    </div>
                </div>
            </div>
            
            <div style="margin-bottom: 16px;">
                <div style="font-weight: 600; color: var(--text-secondary); margin-bottom: 8px;">
                    Operational Limits:
                </div>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; font-size: 13px;">
                    <div style="color: var(--text-primary);">
                        <span style="color: var(--text-muted);">Wave (Hs):</span> ≤{limits.Hs_limit_m}m
                    </div>
                    <div style="color: var(--text-primary);">
                        <span style="color: var(--text-muted);">Wind:</span> ≤{limits.Wind_limit_kt}kt
                    </div>
                    <div style="color: var(--text-primary);">
                        <span style="color: var(--text-muted);">Peak Wave (Hmax):</span> ≤{limits.Hmax_allow_m}m
                    </div>
                    <div style="color: var(--text-primary);">
                        <span style="color: var(--text-muted);">Required Window:</span> {limits.SailingTime_hr + limits.Reserve_hr}hr
                    </div>
                </div>
            </div>
            
            <div>
                <div style="font-weight: 600; color: var(--text-secondary); margin-bottom: 8px;">
                    Recommendations:
                </div>
                <ul style="margin: 0; padding-left: 20px; color: var(--text-primary); line-height: 1.8;">
"""
    
    for rec in result.recommendations:
        html += f"                    <li>{rec}</li>\n"
    
    html += """
                </ul>
            </div>
            
            <div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border-subtle); font-size: 12px; color: var(--text-muted); text-align: center;">
                Last Evaluated: """ + datetime.now().strftime("%Y-%m-%d %H:%M UTC") + """
            </div>
        </div>
"""
    
    return html


def run_gonogo_from_json(
    weather_json_path: str,
    limits: Optional[GoNoGoLimits] = None,
    use_gate_b: bool = True
) -> GoNoGoResult:
    """
    Run Go/No-Go evaluation from weather JSON file
    
    Expected JSON format:
    {
        "forecast": [
            {
                "timestamp": "2026-02-02T06:00:00Z",
                "wave_ft": 6.5,
                "wind_kt": 18.0,
                "wave_period_s": 8.0
            },
            ...
        ]
    }
    """
    if limits is None:
        limits = GoNoGoLimits()
    
    with open(weather_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    weather_series = []
    for item in data.get('forecast', []):
        weather_series.append(WeatherInput(
            wave_ft=item['wave_ft'],
            wind_kt=item['wind_kt'],
            timestamp=datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00')),
            wave_period_s=item.get('wave_period_s')
        ))
    
    return evaluate_go_nogo(weather_series, limits, use_gate_b)


def run_gonogo_manual(
    wave_ft_series: List[float],
    wind_kt_series: List[float],
    limits: Optional[GoNoGoLimits] = None,
    use_gate_b: bool = True
) -> GoNoGoResult:
    """
    Run Go/No-Go evaluation from manual input arrays
    
    Args:
        wave_ft_series: List of wave heights in feet (hourly)
        wind_kt_series: List of wind speeds in knots (hourly)
        limits: Operational limits (uses defaults if None)
        use_gate_b: Whether to apply Gate-B squall buffer logic
    """
    if limits is None:
        limits = GoNoGoLimits()
    
    if len(wave_ft_series) != len(wind_kt_series):
        raise ValueError("wave_ft_series and wind_kt_series must have same length")
    
    weather_series = []
    base_time = datetime.now()
    for i, (wave_ft, wind_kt) in enumerate(zip(wave_ft_series, wind_kt_series)):
        weather_series.append(WeatherInput(
            wave_ft=wave_ft,
            wind_kt=wind_kt,
            timestamp=base_time + timedelta(hours=i)
        ))
    
    return evaluate_go_nogo(weather_series, limits, use_gate_b)


def load_skill_outputs(out_root: str, date_folder: str) -> Dict[str, Any]:
    """
    Load skill-generated JSON outputs for a specific date folder.

    Required files under: <out_root>/<date_folder>/
      - sea_transit_folder_report.json
      - sea_transit_reports_by_file.json
      - parsed_forecasts_by_file.json
    """
    base_dir = Path(out_root) / date_folder
    paths = {
        "folder_report": base_dir / "sea_transit_folder_report.json",
        "reports_by_file": base_dir / "sea_transit_reports_by_file.json",
        "parsed_by_file": base_dir / "parsed_forecasts_by_file.json",
    }

    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing required skill output files: " + ", ".join(missing))

    loaded: Dict[str, Any] = {"base_dir": str(base_dir.resolve()), "source_paths": {k: str(v.resolve()) for k, v in paths.items()}}
    for key, path in paths.items():
        with open(path, "r", encoding="utf-8") as f:
            loaded[key] = json.load(f)
    return loaded


def _fmt_dt(dt_iso: Optional[str]) -> str:
    return dt_iso if dt_iso else "N/A"


def _status_str(value: Optional[bool]) -> str:
    if value is True:
        return "PASS"
    if value is False:
        return "FAIL"
    return "N/A"


def _collect_observed_hs_m_and_validity(parsed_by_file: Dict[str, Any]) -> Tuple[Optional[float], List[Dict[str, str]]]:
    max_hs_m: Optional[float] = None
    windows: List[Dict[str, str]] = []
    seen = set()

    for file_name, item in parsed_by_file.items():
        for obs in item.get("observations", []):
            wave = obs.get("wave_ft", {})
            for key in ("min", "max", "peak"):
                v = wave.get(key)
                if isinstance(v, (int, float)):
                    hs_m = ft_to_m(float(v))
                    max_hs_m = hs_m if max_hs_m is None else max(max_hs_m, hs_m)

            vf = obs.get("valid_from")
            vt = obs.get("valid_to")
            if vf or vt:
                token = (file_name, vf, vt)
                if token not in seen:
                    seen.add(token)
                    windows.append({"file": file_name, "valid_from": _fmt_dt(vf), "valid_to": _fmt_dt(vt)})

    return max_hs_m, windows


def _build_skill_report_model(date_folder: str, loaded: Dict[str, Any]) -> Dict[str, Any]:
    folder_report = loaded["folder_report"]
    reports_by_file = loaded["reports_by_file"]
    parsed_by_file = loaded["parsed_by_file"]

    files = folder_report.get("files", [])
    pdf_details: List[Dict[str, Any]] = []
    all_reason_codes = set()
    chart_pdf_count = 0
    window_gap_count = 0
    chart_needs_ocr_count = 0

    for row in files:
        file_name = row.get("file", "N/A")
        detail = reports_by_file.get(file_name, {})
        gates = detail.get("gates", [])
        gate_map = {g.get("gate", ""): g for g in gates}
        reason_codes = detail.get("reason_codes", row.get("reason_codes", []))
        all_reason_codes.update(reason_codes)
        if "WX_WINDOW_GAP" in reason_codes:
            window_gap_count += 1
        if "WX_CHART_NEEDS_OCR" in reason_codes:
            chart_needs_ocr_count += 1
        if row.get("chart_detected"):
            chart_pdf_count += 1

        pdf_details.append(
            {
                "file": file_name,
                "decision": row.get("decision", "N/A"),
                "reason_codes": reason_codes,
                "missing_inputs": detail.get("missing_inputs", row.get("missing_inputs", [])),
                "chart_detected": row.get("chart_detected", False),
                "squall_unaccounted": row.get("squall_unaccounted", False),
                "gate_a": gate_map.get("Gate-A"),
                "gate_b": gate_map.get("Gate-B"),
                "gate_c": gate_map.get("Gate-C"),
                "notes": detail.get("notes", []),
            }
        )

    max_observed_hs_m, validity_windows = _collect_observed_hs_m_and_validity(parsed_by_file)
    params = folder_report.get("params", {})
    folder_decision = folder_report.get("folder_decision", "N/A")

    return {
        "report_meta": {
            "date_folder": date_folder,
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_paths": loaded.get("source_paths", {}),
        },
        "folder_summary": {
            "input_dir": folder_report.get("input_dir", "N/A"),
            "folder_decision": folder_decision,
            "total_files": folder_report.get("total_files", 0),
            "pdf_files": folder_report.get("pdf_files", 0),
            "non_pdf_files": folder_report.get("non_pdf_files", 0),
            "non_pdf_materials": folder_report.get("non_pdf_materials", []),
            "params": params,
        },
        "files": pdf_details,
        "derived_insights": {
            "chart_pdf_count": chart_pdf_count,
            "window_gap_count": window_gap_count,
            "chart_needs_ocr_count": chart_needs_ocr_count,
            "max_observed_hs_m": round(max_observed_hs_m, 2) if max_observed_hs_m is not None else None,
            "validity_windows": validity_windows,
            "reason_codes": sorted(all_reason_codes),
        },
    }


def render_report_md_kr(model: Dict[str, Any]) -> str:
    meta = model["report_meta"]
    folder = model["folder_summary"]
    insights = model["derived_insights"]
    files = model["files"]

    lines: List[str] = []
    lines.append(f"# SEA TRANSIT Go/No-Go 통합 보고서 ({meta['date_folder']})")
    lines.append("")
    lines.append(f"- 생성시각(UTC): `{meta['generated_at']}`")
    lines.append(f"- 최종 판정: **{folder['folder_decision']}**")
    lines.append(f"- 입력 경로: `{folder['input_dir']}`")
    lines.append("")
    lines.append("## 0) Exec Summary")
    lines.append("")
    lines.append(f"- 폴더 판정: **{folder['folder_decision']}**")
    lines.append(f"- PDF: {folder['pdf_files']}건 / 비PDF: {folder['non_pdf_files']}건")
    lines.append(f"- 차트형 PDF: {insights['chart_pdf_count']}건")
    lines.append(f"- `WX_WINDOW_GAP`: {insights['window_gap_count']}건")
    lines.append(f"- `WX_CHART_NEEDS_OCR`: {insights['chart_needs_ocr_count']}건")
    max_hs = insights["max_observed_hs_m"]
    lines.append(f"- 관측 최대 Hs(추정): `{max_hs if max_hs is not None else 'N/A'} m`")
    lines.append("")
    lines.append("## 1) Key Inputs (SSOT)")
    lines.append("")
    params = folder["params"]
    lines.append(f"- `hs_limit_m`: `{params.get('hs_limit_m', 'N/A')}`")
    lines.append(f"- `hmax_allow_m`: `{params.get('hmax_allow_m', 'N/A')}`")
    lines.append(f"- `wind_limit_kt`: `{params.get('wind_limit_kt', 'N/A')}`")
    lines.append(f"- `sailing_time_hr`: `{params.get('sailing_time_hr', 'N/A')}`")
    lines.append(f"- `reserve_hr`: `{params.get('reserve_hr', 'N/A')}`")
    lines.append(f"- `dh_squall_m`: `{params.get('dh_squall_m', 'N/A')}`")
    lines.append(f"- `dgust_kt`: `{params.get('dgust_kt', 'N/A')}`")
    lines.append("")
    lines.append("## 2) PDF별 Gate 결과")
    lines.append("")
    lines.append("| File | Decision | Gate-A | Gate-B | Gate-C | ReasonCodes |")
    lines.append("|---|---|---|---|---|---|")
    for item in files:
        gate_a = _status_str((item.get("gate_a") or {}).get("passed") if item.get("gate_a") else None)
        gate_b = _status_str((item.get("gate_b") or {}).get("passed") if item.get("gate_b") else None)
        gate_c = _status_str((item.get("gate_c") or {}).get("passed") if item.get("gate_c") else None)
        rcs = ",".join(item.get("reason_codes", [])) or "N/A"
        lines.append(f"| {item['file']} | {item['decision']} | {gate_a} | {gate_b} | {gate_c} | {rcs} |")
    lines.append("")
    lines.append("## 3) Rules (Operational)")
    lines.append("")
    lines.append("- Rule 0: Validity window 밖이면 STOP 후보")
    lines.append("- Rule 1: `WARNING != NIL`이면 STOP 후보")
    lines.append("- Rule 2: Wave/Wind 한계 초과 시 NO-GO")
    lines.append("- Rule 3: `WX_WINDOW_GAP` 존재 시 Gate-C 확정 불가로 CONDITIONAL 유지")
    lines.append("- Rule 4: `WX_CHART_NEEDS_OCR` 존재 시 OCR 또는 `--bucket-csv` 필요")
    lines.append("")
    lines.append("## 4) Options (A/B/C)")
    lines.append("")
    lines.append("| 옵션 | 설명 |")
    lines.append("|---|---|")
    lines.append("| A | 현재 조건 유지 + `--bucket-csv` 보강 후 Gate-C 재평가 |")
    lines.append("| B | 차트형 PDF(OCR 필요) 보강 후 재판정 |")
    lines.append("| C | 보수 운항: CONDITIONAL 유지 및 출항 전 재검증 |")
    lines.append("")
    lines.append("## 5) QA Checklist")
    lines.append("")
    lines.append("- [ ] `WX_WINDOW_GAP` 해소용 시간 버킷 CSV 확보")
    lines.append("- [ ] 차트형 PDF에 대한 OCR/라벨 수치 보강")
    lines.append("- [ ] Validity window와 실제 출항 시간대 일치 확인")
    lines.append("- [ ] 선박 한계치(Hs/Wind/Hmax) 최신 값 확인")
    lines.append("")
    lines.append("## 6) Unified JSON")
    lines.append("")
    lines.append(f"- 기계용 출력: `weather_go_nogo_report.json`")
    lines.append(f"- ReasonCodes: `{','.join(insights['reason_codes']) if insights['reason_codes'] else 'N/A'}`")
    lines.append("")
    lines.append("## 7) 한계/추가 조치")
    lines.append("")
    if insights["chart_needs_ocr_count"] > 0:
        lines.append("- 차트형 PDF에서 수치 시계열이 부족합니다. OCR 또는 `--bucket-csv` 입력이 필요합니다.")
    if insights["window_gap_count"] > 0:
        lines.append("- 연속 운항 윈도우(Gate-C) 증명이 불가합니다. 시간 버킷 입력 후 재평가하세요.")
    if insights["chart_needs_ocr_count"] == 0 and insights["window_gap_count"] == 0:
        lines.append("- 주요 제약 이슈 없음.")
    lines.append("")
    return "\n".join(lines)


def render_report_json(model: Dict[str, Any]) -> Dict[str, Any]:
    folder = model["folder_summary"]
    insights = model["derived_insights"]
    meta = model["report_meta"]
    return {
        "exec_summary": {
            "verdict": folder["folder_decision"],
            "key_points": [
                f"pdf_files={folder['pdf_files']}, non_pdf_files={folder['non_pdf_files']}",
                f"chart_pdf_count={insights['chart_pdf_count']}, window_gap_count={insights['window_gap_count']}",
                f"max_observed_hs_m={insights['max_observed_hs_m'] if insights['max_observed_hs_m'] is not None else 'N/A'}",
            ],
            "required_inputs_for_final_go_stop": [
                "Hs_limit_m(or Hmax_allow_m)",
                "Wind_limit_kt",
                "Sailing_hr+Reserve_hr",
            ],
            "reason_codes": insights["reason_codes"],
        },
        "folder_summary": folder,
        "files": model["files"],
        "visuals": {
            "validity_windows": insights["validity_windows"],
            "source_paths": meta["source_paths"],
        },
        "options": [
            {"id": "A", "summary": "bucket-csv 보강 후 Gate-C 재평가"},
            {"id": "B", "summary": "차트형 PDF OCR 보강 후 재판정"},
            {"id": "C", "summary": "CONDITIONAL 유지 + 출항 전 재검증"},
        ],
        "qa": {
            "checks": [
                "window_gap_resolved",
                "chart_ocr_or_bucket_provided",
                "validity_window_confirmed",
                "vessel_limits_confirmed",
            ]
        },
        "meta": {
            "template_id": "WEATHER_GO_NOGO_SKILL_REPORT_v1",
            "generated_at": meta["generated_at"],
            "date_folder": meta["date_folder"],
            "tz": "UTC",
            "encoding": "utf-8",
        },
    }


def render_report_html_kr(model: Dict[str, Any]) -> str:
    folder = model["folder_summary"]
    insights = model["derived_insights"]
    files = model["files"]
    decision = folder["folder_decision"]
    color_map = {"GO": "#10b981", "NO-GO": "#ef4444", "CONDITIONAL": "#eab308", "ZERO": "#64748b"}
    color = color_map.get(decision, "#64748b")

    rows = []
    for item in files:
        rcs = ", ".join(item.get("reason_codes", [])) or "N/A"
        rows.append(
            f"<tr><td>{item['file']}</td><td>{item['decision']}</td>"
            f"<td>{_status_str((item.get('gate_a') or {}).get('passed') if item.get('gate_a') else None)}</td>"
            f"<td>{_status_str((item.get('gate_b') or {}).get('passed') if item.get('gate_b') else None)}</td>"
            f"<td>{_status_str((item.get('gate_c') or {}).get('passed') if item.get('gate_c') else None)}</td>"
            f"<td>{rcs}</td></tr>"
        )

    return f"""<div class="weather-gonogo-report" style="font-family:Segoe UI,Arial,sans-serif;border:1px solid #d1d5db;border-radius:10px;padding:16px;">
<h2 style="margin:0 0 8px 0;">SEA TRANSIT Go/No-Go 통합 보고서</h2>
<div style="display:inline-block;padding:6px 12px;border-radius:999px;background:{color};color:#fff;font-weight:700;">{decision}</div>
<p style="margin:12px 0 6px 0;">PDF {folder['pdf_files']}건 / 비PDF {folder['non_pdf_files']}건, WX_WINDOW_GAP {insights['window_gap_count']}건, WX_CHART_NEEDS_OCR {insights['chart_needs_ocr_count']}건</p>
<table style="width:100%;border-collapse:collapse;margin-top:10px;">
<thead><tr><th style="text-align:left;border-bottom:1px solid #e5e7eb;">File</th><th style="text-align:left;border-bottom:1px solid #e5e7eb;">Decision</th><th style="text-align:left;border-bottom:1px solid #e5e7eb;">A</th><th style="text-align:left;border-bottom:1px solid #e5e7eb;">B</th><th style="text-align:left;border-bottom:1px solid #e5e7eb;">C</th><th style="text-align:left;border-bottom:1px solid #e5e7eb;">ReasonCodes</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
<p style="margin-top:12px;font-size:12px;color:#6b7280;">Generated at {model['report_meta']['generated_at']} (UTC)</p>
</div>"""


def run_report_from_skill_outputs(date_folder: str, out_root: str = "out/sea_transit") -> Dict[str, Any]:
    """
    Generate weather go/no-go reports from skill outputs for a date folder.

    Writes:
      - weather_go_nogo_report.md
      - weather_go_nogo_report.json
      - weather_go_nogo_report.html
    """
    loaded = load_skill_outputs(out_root, date_folder)
    model = _build_skill_report_model(date_folder, loaded)
    payload = render_report_json(model)
    md = render_report_md_kr(model)
    html = render_report_html_kr(model)

    base_dir = Path(loaded["base_dir"])
    out_md = base_dir / "weather_go_nogo_report.md"
    out_json = base_dir / "weather_go_nogo_report.json"
    out_html = base_dir / "weather_go_nogo_report.html"

    out_md.write_text(md, encoding="utf-8")
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    out_html.write_text(html, encoding="utf-8")

    return {
        "folder_decision": model["folder_summary"]["folder_decision"],
        "reason_codes": model["derived_insights"]["reason_codes"],
        "outputs": {
            "markdown": str(out_md.resolve()),
            "json": str(out_json.resolve()),
            "html": str(out_html.resolve()),
        },
    }


def main():
    """
    Command-line interface for weather Go/No-Go evaluation
    
    Usage:
        python weather_go_nogo.py --json weather_forecast.json
        python weather_go_nogo.py --manual "6.5,7.0,6.8,6.2" "18,20,19,17"
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="SEA TRANSIT Weather Go/No-Go Evaluation (Pipeline Step 4)"
    )
    parser.add_argument(
        '--date-folder',
        help='Date folder under out-root (e.g., 20260203) for skill-output report mode'
    )
    parser.add_argument(
        '--out-root',
        default='out/sea_transit',
        help='Root directory containing per-date skill outputs (default: out/sea_transit)'
    )
    parser.add_argument(
        '--json',
        help='Path to weather forecast JSON file'
    )
    parser.add_argument(
        '--manual-wave',
        help='Comma-separated wave heights in feet (hourly)'
    )
    parser.add_argument(
        '--manual-wind',
        help='Comma-separated wind speeds in knots (hourly)'
    )
    parser.add_argument(
        '--hs-limit',
        type=float,
        default=3.0,
        help='Max significant wave height (m), default=3.0'
    )
    parser.add_argument(
        '--wind-limit',
        type=float,
        default=25.0,
        help='Max wind speed (kt), default=25.0'
    )
    parser.add_argument(
        '--sailing-time',
        type=float,
        default=8.0,
        help='Expected sailing time (hr), default=8.0'
    )
    parser.add_argument(
        '--reserve',
        type=float,
        default=4.0,
        help='Reserve time (hr), default=4.0'
    )
    parser.add_argument(
        '--no-gate-b',
        action='store_true',
        help='Disable Gate-B squall buffer evaluation'
    )
    parser.add_argument(
        '--output-html',
        help='Output HTML file path (for integration into AGI TR SCHEDULE)'
    )
    
    args = parser.parse_args()

    # Skill-output report mode (new)
    if args.date_folder:
        try:
            result = run_report_from_skill_outputs(args.date_folder, args.out_root)
            print("\n" + "="*60)
            print("SEA TRANSIT SKILL REPORT GENERATED")
            print("="*60)
            print(f"Folder Decision: {result['folder_decision']}")
            print(f"Reason Codes: {', '.join(result['reason_codes']) if result['reason_codes'] else 'N/A'}")
            print(f"Markdown: {result['outputs']['markdown']}")
            print(f"JSON: {result['outputs']['json']}")
            print(f"HTML: {result['outputs']['html']}")
            print("="*60 + "\n")
        except FileNotFoundError as e:
            print(f"Error: {e}")
        return
    
    # Create limits
    limits = GoNoGoLimits(
        Hs_limit_m=args.hs_limit,
        Wind_limit_kt=args.wind_limit,
        SailingTime_hr=args.sailing_time,
        Reserve_hr=args.reserve
    )
    
    # Run evaluation
    if args.json:
        if not os.path.exists(args.json):
            print(f"Error: JSON file not found: {args.json}")
            return
        result = run_gonogo_from_json(args.json, limits, not args.no_gate_b)
    elif args.manual_wave and args.manual_wind:
        wave_series = [float(x.strip()) for x in args.manual_wave.split(',')]
        wind_series = [float(x.strip()) for x in args.manual_wind.split(',')]
        result = run_gonogo_manual(wave_series, wind_series, limits, not args.no_gate_b)
    else:
        print("Error: Must provide either --json or both --manual-wave and --manual-wind")
        parser.print_help()
        return
    
    # Print result
    print("\n" + "="*60)
    print("SEA TRANSIT WEATHER GO/NO-GO EVALUATION")
    print("="*60)
    print(f"\nDecision: {result.decision}")
    print(f"\nRationale: {result.rationale}")
    
    if result.reason_codes:
        print(f"\nReason Codes: {', '.join(result.reason_codes)}")
    
    print(f"\nGate-A (Basic Threshold): {'PASS' if result.gate_a.passed else 'FAIL'}")
    print(f"  {result.gate_a.details}")
    
    if result.gate_b:
        print(f"\nGate-B (Squall Buffer): {'PASS' if result.gate_b.passed else 'FAIL'}")
        print(f"  {result.gate_b.details}")
    
    print(f"\nGate-C (Continuous Window): {'PASS' if result.gate_c.passed else 'FAIL'}")
    print(f"  {result.gate_c.details}")
    
    print("\nRecommendations:")
    for i, rec in enumerate(result.recommendations, 1):
        print(f"  {i}. {rec}")
    
    # Save HTML if requested
    if args.output_html:
        html_output = format_html_output(result, limits)
        with open(args.output_html, 'w', encoding='utf-8') as f:
            f.write(html_output)
        print(f"\nHTML output saved to: {args.output_html}")
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    main()
