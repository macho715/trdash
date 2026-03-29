# Report Schema (JSON)

## sea_transit_report.json
{
  "decision": "GO|NO-GO|CONDITIONAL|ZERO",
  "reason_codes": [
    "WX_WAVE",
    "WX_WIND",
    "WX_SQUALL_BUFFER",
    "WX_PEAK_WAVE",
    "WX_WINDOW_GAP",
    "WX_THRESHOLD_MISSING",
    "WX_PARSE_FAIL"
  ],
  "missing_inputs": [
    "Hs_limit_m(or Hmax_allow_m)",
    "Wind_limit_kt",
    "SailingTime_hr+Reserve_hr"
  ],
  "gates": [
    {"gate": "Gate-A", "passed": true, "detail": "...", "reason_code": ""},
    {"gate": "Gate-B", "passed": null, "detail": "...", "reason_code": "WX_SQUALL_BUFFER"},
    {"gate": "Gate-C", "passed": false, "detail": "...", "reason_code": "WX_WINDOW_GAP"}
  ],
  "notes": ["..."]
}

## parsed_forecast.json
{
  "pdf_path": "...",
  "ssot": "pdf_text|bucket_csv",
  "chart_detected": true,
  "squall_unaccounted": true,
  "observations": [
    {
      "scope": "offshore_area:...",
      "valid_from": "YYYY-MM-DDTHH:MM:SS",
      "valid_to": "YYYY-MM-DDTHH:MM:SS",
      "wave_ft": {"min": 2.0, "max": 4.0, "peak": 6.0},
      "wind_kt": {"min": 10.0, "max": 16.0, "peak": 18.0},
      "period_s": {"min": 2.0, "max": 3.0, "peak": 4.0},
      "evidence": [{"page": 3, "snippet": "..."}]
    }
  ],
  "time_buckets": [
    {"datetime_iso": "...", "wave_ft": 3.0, "wind_kt": 12.0, "period_s": 3.0}
  ]
}
