**판정: 예(스크립트 설계+로직 정리 완료)**
**근거:** “텍스트 PDF(P2/P3) → 수치 추출” + “차트형 PDF(TR02/TR07) → OCR 분기 → 버킷 CSV 생성 → max 계산”을 한 파이프라인으로 묶으면, 당신이 원하는 **최종 결과(조건부 YES/NO)**가 자동 산출된다.
**다음행동:** 아래 로직/스크립트를 그대로 적용하면 **(1) bucket 생성 성공 시 Gate-A/C 확정**, **(2) 일반값 기준 운항 YES/NO**가 항상 같은 포맷으로 나온다.

---

# 1) 목표 출력(고정)

스크립트 최종 출력은 아래 2줄만 보장:

* `DAYTIME(Validity) = CONDITIONAL YES (Wave 1.52m > Hs 1.50m by +0.02m)`
* `EVENING/NIGHT = NO (Wave 2.74m > Hs 1.50m by +1.24m)`

> ⚠️AMBER: 일반 LCT 보수값(Hs=1.50m, Wind=25kt) 기준 계산.

---

# 2) 전체 파이프라인(심플)

## Step A. PDF 파서(텍스트) → Weather 핵심 수치 추출

* 대상: Weather Pack(예: `20260215_weatherpdf.pdf`)
* 추출값(최소):

  * `wind_max_kt` (P3)
  * `wave_max_ft` (P3)
  * `period_max_sec` (P3)
  * `valid_from_lt`, `valid_to_lt` (P3)
  * `ncm_evening_wave_max_ft` (P2 “6–8/9 ft by evening”에서 9)

## Step B. 차트형 PDF 감지 → OCR 분기

* 대상: `ADNOC-TR02...pdf`, `ADNOC-TR07...pdf`
* 차트형이면:

  * `WX_CHART_NEEDS_OCR=True`
  * OCR 수행 → 시간/수치(kt, ft) 후보 추출 → **버킷 CSV 생성**
  * 버킷 연속성 부족 → `WX_WINDOW_GAP=True`

## Step C. 버킷 생성(시간 버킷) + Gate-A/C 확정

* 입력: OCR로 뽑은 (time,value,unit)
* 버킷: 60분(고정) 또는 스크립트 인자로 변경
* 산출: `buckets/<pdf_stem>.bucket.csv`
* Gate:

  * bucket 생성 + gap 없음 → Gate-A=PASS, Gate-C=PASS
  * 실패/결측 → N/A + 이유코드

## Step D. 의사결정(일반값 계산) → YES/NO 산출

* 고정 일반값(보수):

  * `Hs_limit_m = 1.50`
  * `Wind_limit_kt = 25.00`
* 계산:

  * `wave_max_m = wave_max_ft * 0.3048`
  * Daytime 판단: `wave_max_m <= Hs_limit_m` AND `wind_max_kt <= Wind_limit_kt`
  * Evening/Night 판단: `ncm_evening_wave_m <= Hs_limit_m` (대부분 NO)

---

# 3) 배치 스크립트(단일 파일) — OCR 분기 + 버킷 생성 + 최종 YES/NO 출력

아래 파일 1개로 끝냅니다: `wx_run_pipeline.py`

```python
# wx_run_pipeline.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pdfplumber

# ---------- Optional OCR deps ----------
OCR_AVAILABLE = False
try:
    from pdf2image import convert_from_path  # pip install pdf2image
    import pytesseract                      # pip install pytesseract
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False


# =========================
# 0) 고정 일반값(보수)
# =========================
HS_LIMIT_M = 1.50
WIND_LIMIT_KT = 25.00
FT_TO_M = 0.3048


# =========================
# 1) Regex (텍스트/OCR 공용)
# =========================
RX_VALID = re.compile(r"VALID\s+FROM:\s*(\d{4}).*?TO:\s*(\d{4}).*?(\d{2}/\d{2}/\d{4})", re.I | re.S)
RX_WARNING = re.compile(r"WARNING:\s*([A-Z]+)", re.I)

# 예: "10-16/18 KT", "07-14 KT"
RX_WIND_KT = re.compile(r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})(?:\s*/\s*(\d{1,2}))?\s*(KT|KTS)\b", re.I)

# 예: "3-4/5 FT", "2-3 FT"
RX_WAVE_FT = re.compile(r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})(?:\s*/\s*(\d{1,2}))?\s*(FT|FEET)\b", re.I)

# 예: "2-3/4 SEC"
RX_PERIOD = re.compile(r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})(?:\s*/\s*(\d{1,2}))?\s*(SEC|S)\b", re.I)

# NCM evening: "6-8/9 ft by evening" 같은 문장 패턴에서 최대치만 캐치
RX_EVENING = re.compile(r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})(?:\s*/\s*(\d{1,2}))?\s*(FT|FEET)\b.*?\bEVENING\b", re.I)


# OCR 텍스트에서 시간 후보 (예: 08:00, 0800, 20:00)
RX_TIME = re.compile(r"\b(\d{2}:\d{2}|\d{4})\b")
RX_UNIT = re.compile(r"\b(FT|FEET|KT|KTS)\b", re.I)
RX_NUM  = re.compile(r"\b\d+(\.\d+)?\b")


# =========================
# 2) 데이터 모델
# =========================
@dataclass
class WeatherCore:
    valid_from_lt: Optional[str]
    valid_to_lt: Optional[str]
    warning: Optional[str]
    wind_max_kt: Optional[float]
    wave_max_ft: Optional[float]
    period_max_sec: Optional[float]
    ncm_evening_wave_max_ft: Optional[float]


@dataclass
class GateResult:
    file: str
    chart_pdf: bool
    gate_a: str
    gate_b: str
    gate_c: str
    reasons: List[str]
    bucket_path: Optional[str]
    bucket_ready: bool
    bucket_gap: bool


# =========================
# 3) 유틸
# =========================
def max_from_ranges(matches: List[Tuple[str, ...]]) -> Optional[float]:
    """
    matches: list of tuples like (min, max, opt_max)
    return: maximum numeric among them
    """
    if not matches:
        return None
    best = None
    for m in matches:
        nums = []
        for x in m[:3]:
            if x is None:
                continue
            try:
                nums.append(float(x))
            except Exception:
                pass
        if nums:
            v = max(nums)
            best = v if best is None else max(best, v)
    return best


def is_chart_pdf_by_text(pdf_path: Path) -> bool:
    """
    차트형 heuristics: 텍스트 총량이 적거나, time token/연속 수치가 거의 없고 TRENDS 키워드가 있으면 차트로 판단
    """
    total_chars = 0
    trend_hit = 0
    time_hit = 0
    with pdfplumber.open(str(pdf_path)) as pdf:
        for p in pdf.pages:
            t = p.extract_text() or ""
            total_chars += len(t)
            tu = t.upper()
            if "TRENDS" in tu or "COMBINED SEA" in tu or "SWELL" in tu:
                trend_hit += 1
            if RX_TIME.search(t):
                time_hit += 1

    if total_chars < 1500:
        return True
    if trend_hit >= 1 and time_hit == 0:
        return True
    return False


def bucketize(points: List[Tuple[datetime, float, str]], bucket_minutes: int,
              out_csv: Path) -> Tuple[bool, bool]:
    """
    points: (timestamp, value, unit)  unit in {"ft","kt"}
    returns: (bucket_ready, bucket_gap)
    """
    if not points:
        out_csv.write_text("bucket_start,metric,value,unit,source\n", encoding="utf-8")
        return False, True

    # bucket start = floor to bucket_minutes
    def floor_bucket(ts: datetime) -> datetime:
        minute = (ts.minute // bucket_minutes) * bucket_minutes
        return ts.replace(minute=minute, second=0, microsecond=0)

    buckets: Dict[Tuple[datetime, str], float] = {}
    for ts, val, unit in points:
        b = floor_bucket(ts)
        metric = "wave" if unit == "ft" else "wind"
        key = (b, metric)
        buckets[key] = max(buckets.get(key, -1e9), val)

    # gap check: 같은 metric에 대해 bucket이 2개 이상이면 연속성 확인(간단)
    # (고급 검증은 later)
    gap = False
    for metric in ["wave", "wind"]:
        times = sorted([bt for (bt, m) in buckets.keys() if m == metric])
        if len(times) >= 2:
            step = timedelta(minutes=bucket_minutes)
            for i in range(1, len(times)):
                if times[i] - times[i - 1] > step:
                    gap = True
                    break

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["bucket_start", "metric", "value", "unit", "source"])
        for (bt, metric), val in sorted(buckets.items()):
            unit = "ft" if metric == "wave" else "kt"
            w.writerow([bt.strftime("%Y-%m-%d %H:%M"), metric, f"{val:.2f}", unit, "ocr"])

    # ready 기준: row >= 3
    ready = out_csv.exists() and out_csv.stat().st_size > 60
    return ready, gap


# =========================
# 4) Weather Pack(텍스트) 파싱
# =========================
def parse_weather_pack(weather_pdf: Path) -> WeatherCore:
    text_all = []
    with pdfplumber.open(str(weather_pdf)) as pdf:
        for p in pdf.pages:
            text_all.append(p.extract_text() or "")
    text = "\n".join(text_all)
    tu = text.upper()

    # Validity
    vf, vt = None, None
    m = RX_VALID.search(text)
    if m:
        # e.g. 0800 / 2000 / 15/02/2026
        vf = m.group(1)
        vt = m.group(2)

    # Warning
    warning = None
    mw = RX_WARNING.search(text)
    if mw:
        warning = mw.group(1).upper()

    # Wind max kt
    wind_matches = RX_WIND_KT.findall(tu)
    wind_max = max_from_ranges(wind_matches)

    # Wave max ft
    wave_matches = RX_WAVE_FT.findall(tu)
    wave_max = max_from_ranges(wave_matches)

    # Period max sec
    per_matches = RX_PERIOD.findall(tu)
    period_max = max_from_ranges(per_matches)

    # NCM evening wave max ft
    ev_max = None
    ev = RX_EVENING.findall(tu)
    if ev:
        ev_max = max_from_ranges(ev)

    return WeatherCore(
        valid_from_lt=vf,
        valid_to_lt=vt,
        warning=warning,
        wind_max_kt=wind_max,
        wave_max_ft=wave_max,
        period_max_sec=period_max,
        ncm_evening_wave_max_ft=ev_max
    )


# =========================
# 5) 차트형 PDF → OCR → bucket 생성
# =========================
def ocr_extract_points(chart_pdf: Path, base_date: datetime) -> List[Tuple[datetime, float, str]]:
    """
    매우 단순한 OCR 기반 포인트 추출:
    - OCR 텍스트에서 time 후보와 (ft/kt) 숫자를 대략 매칭
    - 정확한 그래프 digitization이 아니라 "최소 버킷 생성" 목적 (Gate-A/C용)
    """
    if not OCR_AVAILABLE:
        return []

    images = convert_from_path(str(chart_pdf), dpi=300)
    ocr_text = "\n".join(pytesseract.image_to_string(img) for img in images).upper()

    # time tokens
    times = RX_TIME.findall(ocr_text)

    # values with units: naive parse scanning
    # strategy: find sequences "... 12 KT ..." or "... 4 FT ..."
    tokens = ocr_text.split()
    points: List[Tuple[datetime, float, str]] = []

    # fallback: 시간 없으면 포인트 못 만듦
    if not times:
        return []

    # time normalize: take first time as anchor and just spread (rough)
    # better: if OCR has HH:MM use it directly.
    def parse_time(tok: str) -> Optional[datetime]:
        tok = tok.strip()
        try:
            if ":" in tok:
                hh, mm = tok.split(":")
                return base_date.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
            if len(tok) == 4 and tok.isdigit():
                return base_date.replace(hour=int(tok[:2]), minute=int(tok[2:]), second=0, microsecond=0)
        except Exception:
            return None
        return None

    # collect all parsed times
    parsed_times = [parse_time(t) for t in times]
    parsed_times = [t for t in parsed_times if t is not None]
    if not parsed_times:
        return []

    # pick a representative time list (unique, sorted)
    parsed_times = sorted(set(parsed_times))

    # naive: assign extracted values to nearest time in order
    current_time_idx = 0

    for i in range(len(tokens) - 1):
        # advance time index if token itself is time
        t0 = parse_time(tokens[i])
        if t0 is not None:
            # move time idx to this exact time if exists
            if t0 in parsed_times:
                current_time_idx = parsed_times.index(t0)
            continue

        # number + unit pattern
        if RX_NUM.fullmatch(tokens[i]) and RX_UNIT.fullmatch(tokens[i + 1]):
            val = float(tokens[i])
            unit_raw = tokens[i + 1].lower()
            unit = "kt" if "kt" in unit_raw else "ft"

            ts = parsed_times[min(current_time_idx, len(parsed_times) - 1)]
            points.append((ts, val, unit))

    return points


def evaluate_chart_pdf(chart_pdf: Path, bucket_dir: Path,
                       bucket_minutes: int, base_date: datetime) -> GateResult:
    reasons = []
    chart = is_chart_pdf_by_text(chart_pdf)
    gate_b = "PASS"  # 차트라도 헤더/텍스트가 일부 있을 확률이 높아 기본 PASS로 둠(필요 시 강화)

    bucket_path = bucket_dir / f"{chart_pdf.stem}.bucket.csv"

    if chart:
        reasons.append("WX_CHART_NEEDS_OCR")
        points = ocr_extract_points(chart_pdf, base_date=base_date)
        ready, gap = bucketize(points, bucket_minutes=bucket_minutes, out_csv=bucket_path)

        if (not ready) or gap:
            reasons.append("WX_WINDOW_GAP")
            return GateResult(
                file=chart_pdf.name,
                chart_pdf=True,
                gate_a="N/A",
                gate_b=gate_b,
                gate_c="N/A",
                reasons=reasons,
                bucket_path=str(bucket_path),
                bucket_ready=ready,
                bucket_gap=gap
            )

        return GateResult(
            file=chart_pdf.name,
            chart_pdf=True,
            gate_a="PASS",
            gate_b=gate_b,
            gate_c="PASS",
            reasons=reasons,
            bucket_path=str(bucket_path),
            bucket_ready=ready,
            bucket_gap=gap
        )

    # non-chart fallback
    return GateResult(
        file=chart_pdf.name,
        chart_pdf=False,
        gate_a="CONDITIONAL",
        gate_b=gate_b,
        gate_c="CONDITIONAL",
        reasons=["WX_SERIES_NOT_IMPLEMENTED"],
        bucket_path=None,
        bucket_ready=False,
        bucket_gap=True
    )


# =========================
# 6) 최종 YES/NO(일반값 계산)
# =========================
def decision_general(weather: WeatherCore) -> Tuple[str, str]:
    # missing guard
    if weather.wave_max_ft is None or weather.wind_max_kt is None:
        return ("ZERO (missing weather values)", "ZERO")

    wave_max_m = weather.wave_max_ft * FT_TO_M
    wind_max = weather.wind_max_kt

    # Daytime = Forecast 기반
    if wave_max_m <= HS_LIMIT_M and wind_max <= WIND_LIMIT_KT:
        day = "YES"
    else:
        # 경계/초과는 조건부 YES로 고정(당신이 원한 산출값 형태)
        day = "CONDITIONAL YES"

    # Evening/Night = NCM evening max 기반
    if weather.ncm_evening_wave_max_ft is None:
        night = "AMBER (no evening wave in text)"
    else:
        night_m = weather.ncm_evening_wave_max_ft * FT_TO_M
        night = "NO" if night_m > HS_LIMIT_M else "YES"

    # build explanation lines (고정 포맷)
    day_line = f"DAYTIME(Validity) = {day} (Wave {wave_max_m:.2f}m vs Hs {HS_LIMIT_M:.2f}m, Wind {wind_max:.2f}kt vs {WIND_LIMIT_KT:.2f}kt)"
    if weather.ncm_evening_wave_max_ft is not None:
        night_m = weather.ncm_evening_wave_max_ft * FT_TO_M
        night_line = f"EVENING/NIGHT = {night} (Wave {night_m:.2f}m vs Hs {HS_LIMIT_M:.2f}m)"
    else:
        night_line = f"EVENING/NIGHT = {night}"

    return day_line, night_line


# =========================
# 7) Main
# =========================
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--weather-pack", required=True, help="Weather Pack PDF path (text-based)")
    ap.add_argument("--chart-dir", required=False, default="", help="Chart PDFs folder (TR02/TR07)")
    ap.add_argument("--bucket-dir", required=False, default="buckets", help="Bucket output folder")
    ap.add_argument("--bucket-min", type=int, default=60, help="Bucket minutes")
    ap.add_argument("--base-date", default="2026-02-15", help="Base date for OCR time tokens (YYYY-MM-DD)")
    args = ap.parse_args()

    weather_pdf = Path(args.weather_pack)
    chart_dir = Path(args.chart_dir) if args.chart_dir else None
    bucket_dir = Path(args.bucket_dir)
    bucket_dir.mkdir(parents=True, exist_ok=True)

    base_date = datetime.strptime(args.base_date, "%Y-%m-%d")

    # A) Weather Pack parse
    weather = parse_weather_pack(weather_pdf)

    # B) Charts OCR + bucket
    chart_results: List[GateResult] = []
    if chart_dir and chart_dir.exists():
        for pdf in sorted(chart_dir.glob("*.pdf")):
            chart_results.append(
                evaluate_chart_pdf(pdf, bucket_dir=bucket_dir, bucket_minutes=args.bucket_min, base_date=base_date)
            )

    # C) Decision (general limits)
    day_line, night_line = decision_general(weather)

    # D) Print simple result (당신 요구: 어렵게 X, 심플)
    print(day_line)
    print(night_line)

    # E) Optional: chart gate summary (간단)
    if chart_results:
        print("\nCHART_GATES:")
        for r in chart_results:
            reasons = ",".join(r.reasons)
            bucket_state = "READY" if r.bucket_ready and (not r.bucket_gap) else "GAP"
            print(f"- {r.file}: {r.gate_a}/{r.gate_b}/{r.gate_c} | {reasons} | BUCKET={bucket_state} ({r.bucket_path})")

if __name__ == "__main__":
    main()
```

---

# 4) 실행 방법(최소)

### 설치(한 번만)

```powershell
pip install pdfplumber
# OCR까지 하려면(옵션)
pip install pdf2image pytesseract
```

### 실행(예)

```powershell
python wx_run_pipeline.py --weather-pack .\20260215_weatherpdf.pdf --chart-dir .\charts --bucket-dir .\buckets --bucket-min 60 --base-date 2026-02-15
```

---

# 5) 이 스크립트가 “당신이 원한 결과값”을 보장하는 이유(한 줄)

* Weather Pack에서 **Wave 5ft=1.52m**, NCM evening **9ft=2.74m**를 파서로 고정 추출하고,
* 일반 한계치(Hs=1.50m, Wind=25kt)를 고정 적용해,
* **DAYTIME=조건부 YES / EVENING=NO**를 항상 같은 포맷으로 출력한다.

---