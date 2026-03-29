# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from pdf_parser import ParsedForecast, TimeBucket

_FT_TO_M = 0.3048
_HMAX_FACTOR = 1.86


class Decision(str, Enum):
    GO = "GO"
    NO_GO = "NO-GO"
    CONDITIONAL = "CONDITIONAL"
    ZERO = "ZERO"


@dataclass
class EvalParams:
    hs_limit_m: Optional[float]
    hmax_allow_m: Optional[float]
    wind_limit_kt: Optional[float]
    sailing_time_hr: Optional[float]
    reserve_hr: Optional[float]
    dh_squall_m: Optional[float]
    dgust_kt: Optional[float]


@dataclass
class GateResult:
    gate: str
    passed: Optional[bool]
    detail: str
    reason_code: Optional[str] = None


@dataclass
class EvalResult:
    decision: Decision
    reason_codes: List[str] = field(default_factory=list)
    missing_inputs: List[str] = field(default_factory=list)
    gates: List[GateResult] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "decision": self.decision.value,
            "reason_codes": self.reason_codes,
            "missing_inputs": self.missing_inputs,
            "gates": [g.__dict__ for g in self.gates],
            "notes": self.notes,
        }


def ft_to_m(ft: float) -> float:
    return ft * _FT_TO_M


def evaluate_sea_transit(parsed: ParsedForecast, p: EvalParams) -> EvalResult:
    result = EvalResult(decision=Decision.ZERO)

    missing = []
    if p.wind_limit_kt is None:
        missing.append("Wind_limit_kt")
    if p.sailing_time_hr is None or p.reserve_hr is None:
        missing.append("SailingTime_hr+Reserve_hr")
    if p.hs_limit_m is None and p.hmax_allow_m is None:
        missing.append("Hs_limit_m(or Hmax_allow_m)")

    if missing:
        result.missing_inputs = missing
        result.reason_codes.append("WX_THRESHOLD_MISSING")
        result.notes.append("Required threshold/time inputs are missing. Final decision cannot be made.")
        return result

    need_window_hr = (p.sailing_time_hr or 0.0) + (p.reserve_hr or 0.0)
    result.notes.append(f"NeedWindow_hr={need_window_hr:.2f}")

    if parsed.squall_unaccounted and (p.dh_squall_m is None or p.dgust_kt is None):
        result.decision = Decision.CONDITIONAL
        result.reason_codes.append("WX_SQUALL_BUFFER")
        result.gates.append(
            GateResult(
                gate="Gate-B",
                passed=None,
                detail="Squall caveat detected in PDF, but dH_squall or dGust is missing.",
                reason_code="WX_SQUALL_BUFFER",
            )
        )
    else:
        result.gates.append(GateResult(gate="Gate-B", passed=True, detail="Squall buffer state is acceptable."))

    if not parsed.observations and not parsed.time_buckets:
        if parsed.chart_detected:
            result.decision = Decision.CONDITIONAL
            result.reason_codes.append("WX_CHART_NEEDS_OCR")
            result.gates.append(
                GateResult(
                    gate="Gate-A",
                    passed=None,
                    detail="Chart-only PDF detected; no numeric wave/wind series extracted from text layer.",
                    reason_code="WX_CHART_NEEDS_OCR",
                )
            )
            result.gates.append(
                GateResult(
                    gate="Gate-C",
                    passed=None,
                    detail="No time buckets available for continuous-window proof. Provide --bucket-csv.",
                    reason_code="WX_WINDOW_GAP",
                )
            )
            result.reason_codes.append("WX_WINDOW_GAP")
            result.notes.append("Use OCR/image parsing or --bucket-csv for chart pages.")
            return result

        result.decision = Decision.ZERO
        result.reason_codes.append("WX_PARSE_FAIL")
        result.notes.append("No wave/wind values extracted from PDF.")
        return result

    if parsed.time_buckets:
        gate_a_ok, rc = _gate_a_buckets(parsed.time_buckets, parsed.squall_unaccounted, p)
        result.gates.append(GateResult(gate="Gate-A", passed=gate_a_ok, detail="Threshold check on time buckets.", reason_code=rc))
        if not gate_a_ok:
            result.decision = Decision.NO_GO
            result.reason_codes.append(rc or "WX_THRESHOLD")
            result.gates.append(GateResult(gate="Gate-C", passed=False, detail="Skipped due to Gate-A failure.", reason_code="WX_WINDOW_GAP"))
            result.reason_codes.append("WX_WINDOW_GAP")
            return result

        window_ok, detail, rc2 = _gate_c_window(parsed.time_buckets, parsed.squall_unaccounted, p, need_window_hr)
        result.gates.append(GateResult(gate="Gate-C", passed=window_ok, detail=detail, reason_code=rc2))
        if window_ok:
            result.decision = Decision.GO if result.decision != Decision.CONDITIONAL else Decision.CONDITIONAL
        else:
            result.decision = Decision.NO_GO if result.decision != Decision.CONDITIONAL else Decision.CONDITIONAL
            result.reason_codes.append(rc2 or "WX_WINDOW_GAP")

        return _finalize_peak_wave_gate(result, parsed.time_buckets, parsed.squall_unaccounted, p)

    gate_a_ok, rc_a, max_hs_m, max_wind_kt = _gate_a_observations(parsed, p)
    result.gates.append(
        GateResult(
            gate="Gate-A",
            passed=gate_a_ok,
            detail=f"Observation worst-case check: maxHs={max_hs_m:.2f}m, maxWind={max_wind_kt:.2f}kt.",
            reason_code=rc_a,
        )
    )
    if not gate_a_ok:
        result.decision = Decision.NO_GO
        result.reason_codes.append(rc_a or "WX_THRESHOLD")
        result.gates.append(GateResult(gate="Gate-C", passed=False, detail="No time buckets and Gate-A failed.", reason_code="WX_WINDOW_GAP"))
        result.reason_codes.append("WX_WINDOW_GAP")
        return result

    result.gates.append(
        GateResult(
            gate="Gate-C",
            passed=None,
            detail="No time buckets available for continuous-window proof. Provide --bucket-csv.",
            reason_code="WX_WINDOW_GAP",
        )
    )
    if result.decision != Decision.CONDITIONAL:
        result.decision = Decision.CONDITIONAL
    result.reason_codes.append("WX_WINDOW_GAP")
    return _finalize_peak_wave_gate(result, None, parsed.squall_unaccounted, p, max_hs_m=max_hs_m)


def _hs_limit_m(p: EvalParams) -> float:
    if p.hs_limit_m is not None:
        return p.hs_limit_m
    return (p.hmax_allow_m or 0.0) / _HMAX_FACTOR


def _apply_squall(hs_m: float, wind_kt: float, squall_unaccounted: bool, p: EvalParams) -> Tuple[float, float]:
    if squall_unaccounted:
        return hs_m + (p.dh_squall_m or 0.0), wind_kt + (p.dgust_kt or 0.0)
    return hs_m, wind_kt


def _gate_a_observations(parsed: ParsedForecast, p: EvalParams) -> Tuple[bool, str, float, float]:
    hs_lim = _hs_limit_m(p)
    wind_lim = p.wind_limit_kt or 0.0
    max_hs = 0.0
    max_wind = 0.0

    for obs in parsed.observations:
        wave_ft = obs.wave_ft.worst_case()
        wind_kt = obs.wind_kt.worst_case()
        if wave_ft is None and wind_kt is None:
            continue
        hs_m = ft_to_m(wave_ft) if wave_ft is not None else 0.0
        wind = wind_kt if wind_kt is not None else 0.0
        hs_eff, wind_eff = _apply_squall(hs_m, wind, parsed.squall_unaccounted, p)
        max_hs = max(max_hs, hs_eff)
        max_wind = max(max_wind, wind_eff)

    if max_hs > hs_lim:
        return False, "WX_WAVE", max_hs, max_wind
    if max_wind > wind_lim:
        return False, "WX_WIND", max_hs, max_wind
    return True, "", max_hs, max_wind


def _gate_a_buckets(buckets: List[TimeBucket], squall_unaccounted: bool, p: EvalParams) -> Tuple[bool, str]:
    hs_lim = _hs_limit_m(p)
    wind_lim = p.wind_limit_kt or 0.0
    for bucket in buckets:
        hs_m = ft_to_m(bucket.wave_ft)
        hs_eff, wind_eff = _apply_squall(hs_m, bucket.wind_kt, squall_unaccounted, p)
        if hs_eff > hs_lim:
            return False, "WX_WAVE"
        if wind_eff > wind_lim:
            return False, "WX_WIND"
    return True, ""


def _gate_c_window(
    buckets: List[TimeBucket],
    squall_unaccounted: bool,
    p: EvalParams,
    need_window_hr: float,
) -> Tuple[bool, str, str]:
    ordered = sorted(buckets, key=lambda b: b.datetime_iso)
    if len(ordered) < 2:
        return False, "Less than 2 buckets; cannot evaluate continuous window.", "WX_WINDOW_GAP"

    from dateutil import parser as dtparser

    step_hr = (dtparser.parse(ordered[1].datetime_iso) - dtparser.parse(ordered[0].datetime_iso)).total_seconds() / 3600.0
    if step_hr <= 0:
        step_hr = 6.0

    need_steps = int((need_window_hr / step_hr) + 0.999999)
    hs_lim = _hs_limit_m(p)
    wind_lim = p.wind_limit_kt or 0.0

    for i in range(0, len(ordered) - need_steps + 1):
        window = ordered[i : i + need_steps]
        ok = True
        for bucket in window:
            hs_eff, wind_eff = _apply_squall(ft_to_m(bucket.wave_ft), bucket.wind_kt, squall_unaccounted, p)
            if hs_eff > hs_lim or wind_eff > wind_lim:
                ok = False
                break
        if ok:
            return True, f"Continuous GO window found at {window[0].datetime_iso} (steps={need_steps}, step_hr~={step_hr:.2f}).", ""

    return False, "No continuous GO window found.", "WX_WINDOW_GAP"


def _finalize_peak_wave_gate(
    result: EvalResult,
    buckets: Optional[List[TimeBucket]],
    squall_unaccounted: bool,
    p: EvalParams,
    max_hs_m: Optional[float] = None,
) -> EvalResult:
    if p.hmax_allow_m is None:
        return result

    worst_hs = 0.0
    if buckets:
        for bucket in buckets:
            hs_eff, _ = _apply_squall(ft_to_m(bucket.wave_ft), bucket.wind_kt, squall_unaccounted, p)
            worst_hs = max(worst_hs, hs_eff)
    elif max_hs_m is not None:
        worst_hs = max_hs_m

    hmax_est = _HMAX_FACTOR * worst_hs
    ok = hmax_est <= p.hmax_allow_m
    result.gates.append(
        GateResult(
            gate="Gate-B2(Hmax)",
            passed=ok,
            detail=f"Hmax_est~=1.86*Hs_eff => {hmax_est:.2f}m (allow {p.hmax_allow_m:.2f}m).",
            reason_code=None if ok else "WX_PEAK_WAVE",
        )
    )
    if not ok:
        if result.decision == Decision.GO:
            result.decision = Decision.NO_GO
        result.reason_codes.append("WX_PEAK_WAVE")
    return result
