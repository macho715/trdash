# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pdfplumber
from dateutil import parser as dtparser


@dataclass
class Range3:
    min: Optional[float] = None
    max: Optional[float] = None
    peak: Optional[float] = None

    def worst_case(self) -> Optional[float]:
        vals = [v for v in [self.min, self.max, self.peak] if v is not None]
        return max(vals) if vals else None


@dataclass
class Evidence:
    page: int
    snippet: str


@dataclass
class ForecastObs:
    scope: str
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    wave_ft: Range3 = field(default_factory=Range3)
    wind_kt: Range3 = field(default_factory=Range3)
    period_s: Range3 = field(default_factory=Range3)
    evidence: List[Evidence] = field(default_factory=list)


@dataclass
class TimeBucket:
    datetime_iso: str
    wave_ft: float
    wind_kt: float
    period_s: Optional[float] = None


@dataclass
class ParsedForecast:
    pdf_path: str
    ssot: str = "pdf_text"
    chart_detected: bool = False
    squall_unaccounted: bool = False
    observations: List[ForecastObs] = field(default_factory=list)
    time_buckets: List[TimeBucket] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "pdf_path": self.pdf_path,
            "ssot": self.ssot,
            "chart_detected": self.chart_detected,
            "squall_unaccounted": self.squall_unaccounted,
            "observations": [
                {
                    "scope": o.scope,
                    "valid_from": o.valid_from,
                    "valid_to": o.valid_to,
                    "wave_ft": {"min": o.wave_ft.min, "max": o.wave_ft.max, "peak": o.wave_ft.peak},
                    "wind_kt": {"min": o.wind_kt.min, "max": o.wind_kt.max, "peak": o.wind_kt.peak},
                    "period_s": {"min": o.period_s.min, "max": o.period_s.max, "peak": o.period_s.peak},
                    "evidence": [{"page": e.page, "snippet": e.snippet} for e in o.evidence],
                }
                for o in self.observations
            ],
            "time_buckets": [
                {
                    "datetime_iso": b.datetime_iso,
                    "wave_ft": b.wave_ft,
                    "wind_kt": b.wind_kt,
                    "period_s": b.period_s,
                }
                for b in self.time_buckets
            ],
        }


def load_bucket_csv(path: str) -> List[TimeBucket]:
    buckets: List[TimeBucket] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            normalized = {(k or "").strip().lstrip("\ufeff"): v for k, v in row.items()}
            dt_iso = dtparser.parse(normalized["datetime"]).isoformat()
            wave_ft = float(normalized["wave_ft"])
            wind_kt = float(normalized["wind_kt"])
            period_s = float(normalized["period_s"]) if normalized.get("period_s") else None
            buckets.append(TimeBucket(datetime_iso=dt_iso, wave_ft=wave_ft, wind_kt=wind_kt, period_s=period_s))
    return buckets


def parse_weather_pdf(pdf_path: str, sea: str = "auto", area_regex: Optional[str] = None) -> ParsedForecast:
    pf = ParsedForecast(pdf_path=pdf_path)
    area_pat = re.compile(area_regex, re.IGNORECASE) if area_regex else None

    with pdfplumber.open(pdf_path) as pdf:
        for idx, page in enumerate(pdf.pages):
            page_no = idx + 1
            text = page.extract_text() or ""
            up = text.upper()

            if "DO NOT TAKE INTO ACCOUNT THE EFFECT OF ANY SQUALLS" in up:
                pf.squall_unaccounted = True
            if "ADNOC - 2 DAYS WEATHER TRENDS" in up or "ADNOC - 7 DAYS WEATHER TRENDS" in up:
                pf.chart_detected = True
            if "WEATHER FORECAST FOR" in up and "WAVE H." in up:
                _parse_offshore_block(text, page_no, pf, area_pat)
            if "SEA STATE" in up and "WAVE HEIGHT" in up:
                _parse_sea_state_block(text, page_no, pf, sea=sea)
            # Image-first chart pages sometimes still expose station labels in text layer
            # (e.g., "USSC 1-2FT", "ARZANA 2FT"). Capture these as observational hints.
            is_chartish_page = (
                "ADNOC - 2 DAYS WEATHER TRENDS" in up
                or "ADNOC - 7 DAYS WEATHER TRENDS" in up
                or "SYNOP" in up
                or "MARINE" in up
            )
            if is_chartish_page:
                _parse_chart_station_labels(text, page_no, pf)
    return pf


def _parse_range3(s: str, unit_token: str) -> Optional[Range3]:
    pat = re.compile(
        rf"(?P<min>\d+(?:\.\d+)?)\s*-\s*(?P<max>\d+(?:\.\d+)?)(?:\s*/\s*(?P<peak>\d+(?:\.\d+)?))?\s*{re.escape(unit_token)}",
        re.IGNORECASE,
    )
    m = pat.search(s)
    if not m:
        return None
    return Range3(
        min=float(m.group("min")),
        max=float(m.group("max")),
        peak=float(m.group("peak")) if m.group("peak") else None,
    )


def _parse_offshore_block(text: str, page_no: int, pf: ParsedForecast, area_pat: Optional[re.Pattern]) -> None:
    vf, vt = _parse_valid_window(text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    current_scope = None
    buf: List[str] = []

    def flush() -> None:
        nonlocal current_scope, buf
        if not current_scope:
            buf = []
            return
        joined = " ".join(buf)
        wave = _parse_range3(joined, "FT")
        wind = _parse_range3(joined, "KT") or _parse_range3(joined, "KNOTS")
        period = _parse_range3(joined, "SEC")

        if area_pat and not area_pat.search(current_scope):
            buf = []
            return

        obs = ForecastObs(
            scope=f"offshore_area:{current_scope}",
            valid_from=vf,
            valid_to=vt,
            wave_ft=wave or Range3(),
            wind_kt=wind or Range3(),
            period_s=period or Range3(),
            evidence=[Evidence(page=page_no, snippet=_clip(joined, 220))],
        )
        if obs.wave_ft.worst_case() is not None or obs.wind_kt.worst_case() is not None:
            pf.observations.append(obs)
        buf = []

    for ln in lines:
        up = ln.upper()
        if ("WIND " in up) or ("WAVE H." in up) or ("PERIOD" in up) or ("VISIBILITY" in up) or ("WEATHER" in up):
            buf.append(ln)
            continue
        if ("," in ln) and (ln == up) and ("FORECAST" not in up) and ("VALID" not in up):
            flush()
            current_scope = ln
            buf = []
            continue
    flush()


def _parse_sea_state_block(text: str, page_no: int, pf: ParsedForecast, sea: str = "auto") -> None:
    up = text.upper()
    wave_ranges = re.findall(r"WAVE HEIGHT\s+(.+)", text, flags=re.IGNORECASE)
    for wr in wave_ranges:
        wave = _parse_range3(wr, "FT")
        if not wave:
            continue

        scope = "sea_state:auto"
        if "ARABIAN GULF" in up and sea in ("auto", "gulf"):
            scope = "sea_state:gulf"
        if "OMAN" in up and sea in ("auto", "oman"):
            scope = "sea_state:oman"

        pf.observations.append(
            ForecastObs(
                scope=scope,
                wave_ft=wave,
                evidence=[Evidence(page=page_no, snippet=_clip("Wave Height " + wr, 220))],
            )
        )


def _parse_valid_window(text: str) -> Tuple[Optional[str], Optional[str]]:
    pat = re.compile(
        r"VALID FROM:\s*(\d{3,4})\s*ON\s*(\d{2}/\d{2}/\d{4}).*?TO:\s*(\d{3,4})\s*ON\s*(\d{2}/\d{2}/\d{4})",
        re.IGNORECASE | re.DOTALL,
    )
    m = pat.search(text)
    if not m:
        # Alternate style in some forecasts: "VALID 0800-2000 15/02/2026 LT"
        pat2 = re.compile(
            r"VALID\s+(\d{3,4})\s*[-–]\s*(\d{3,4})\s+(\d{2}/\d{2}/\d{4})\s*LT",
            re.IGNORECASE,
        )
        m2 = pat2.search(text)
        if not m2:
            return None, None
        t1, t2, d = m2.group(1), m2.group(2), m2.group(3)
        return _to_iso(d, t1), _to_iso(d, t2)
    t1, d1, t2, d2 = m.group(1), m.group(2), m.group(3), m.group(4)
    return _to_iso(d1, t1), _to_iso(d2, t2)


def _parse_chart_station_labels(text: str, page_no: int, pf: ParsedForecast) -> None:
    up = text.upper()
    if " FT" not in up and "FT " not in up and "FT" not in up:
        return

    # Typical chart labels: "USSC 1-2FT", "ARZANA 2FT", "SW FATEH 2-3 FT"
    pat = re.compile(
        r"([A-Z][A-Z\s]{1,24}?)\s+(\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?(?:\s*/\s*\d+(?:\.\d+)?)?)\s*FT\b",
        re.IGNORECASE,
    )
    bad_tokens = {
        "HEIGHT OF COMBINED SEA",
        "WAVE HEIGHT",
        "WAVES",
        "DAYS",
        "PERIOD",
        "WIND SPEED",
        "WINDS",
        "LT",
        "REACHING",
        "INCREASING",
        "AT FIRST",
        "EVENING",
        "GENERAL",
        "WARNING",
        "VALID",
    }

    seen_scopes = set()
    for m in pat.finditer(text):
        raw_scope = re.sub(r"\s+", " ", m.group(1)).strip(" -:/")
        num_expr = re.sub(r"\s+", "", m.group(2))
        scope_up = raw_scope.upper()
        if len(raw_scope) < 3:
            continue
        if "FT " in scope_up or " FT" in scope_up or scope_up == "FT":
            continue
        if any(tok in scope_up for tok in bad_tokens):
            continue
        if scope_up in seen_scopes:
            continue
        seen_scopes.add(scope_up)

        wave = _parse_loose_wave_expr(num_expr)
        if not wave:
            continue

        pf.observations.append(
            ForecastObs(
                scope=f"chart_station:{raw_scope}",
                wave_ft=wave,
                evidence=[Evidence(page=page_no, snippet=_clip(m.group(0), 120))],
            )
        )


def _parse_loose_wave_expr(expr: str) -> Optional[Range3]:
    # Support forms: "2", "1-2", "3-4/5"
    nums = [float(v) for v in re.findall(r"\d+(?:\.\d+)?", expr)]
    if not nums:
        return None
    if len(nums) == 1:
        return Range3(min=nums[0], max=nums[0], peak=None)
    if len(nums) == 2:
        lo, hi = min(nums[0], nums[1]), max(nums[0], nums[1])
        return Range3(min=lo, max=hi, peak=None)
    lo, hi = min(nums[0], nums[1]), max(nums[0], nums[1])
    peak = max(nums)
    return Range3(min=lo, max=hi, peak=peak)


def _to_iso(ddmmyyyy: str, hhmm: str) -> str:
    hhmm = hhmm.zfill(4)
    dt = datetime.strptime(f"{ddmmyyyy} {hhmm}", "%d/%m/%Y %H%M")
    return dt.isoformat()


def _clip(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n] + ("..." if len(s) > n else "")
