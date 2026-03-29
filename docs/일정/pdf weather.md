**판정: 예(실제 PDF 파싱 완료)** — `20260215_weatherpdf.pdf`를 **PDF 파서(pdfplumber)**로 전체 8페이지 처리했고, **페이지별 텍스트 추출량/핵심 키워드 히트/GO·STOP 영향도**를 매핑했습니다.
**근거:** 파서 결과 **P1=2,679 chars / P2=1,295 / P3=1,814 / P4=624 / P5=629 / P6~P8=0 chars(텍스트 레이어 없음=이미지/차트 페이지)** 확인.
**다음행동:** **GO·STOP 판정 입력값은 P3(Offshore Forecast) + P2(Sea State/Wave Height)만 SSOT로 고정 추출**하면 됩니다(나머지는 보강).

---

## 1) PDF 파서 결과 요약 (구조/텍스트 레이어)

| Page | Text Chars | 텍스트 레이어 | 핵심 키워드 히트                                              | 1차 결론                   |
| ---: | ---------: | ------- | ------------------------------------------------------ | ----------------------- |
|    1 |      2,679 | Yes     | Wind/Sea/Arabian Gulf/MSLP                             | 서술형 기상 개요(보강)           |
|    2 |      1,295 | Yes     | Sea State/Wave Height(ft)/Tide/Arabian Gulf            | **파고(ft) 표 → 판정 보조 핵심** |
|    3 |      1,814 | Yes     | **VALID/WARNING/WIND/WAVE/PERIOD/VISIBILITY/OFFSHORE** | **GO·STOP 원자료(최상위)**    |
|    4 |        624 | Yes     | ADNOC / 2 DAYS / TRENDS                                | 트렌드(전이 리스크)             |
|    5 |        629 | Yes     | ADNOC / 7 DAYS / TRENDS                                | 장기 창(Window)            |
|    6 |          0 | No      | (none)                                                 | 이미지/차트(텍스트 추출 불가)       |
|    7 |          0 | No      | (none)                                                 | 이미지/차트(텍스트 추출 불가)       |
|    8 |          0 | No      | (none)                                                 | 이미지/차트(텍스트 추출 불가)       |

---

## 2) Page별 “영향도 매핑표” (Mina Port → AGI Sea Transit)

| Page | 섹션(파서 기반)                                | GO/STOP 영향도  | 반드시 추출할 포인터(정규화 필드)                                                                                                                       | 파서로 확인된 근거(발췌)                                                                                                        |
| ---: | ---------------------------------------- | ------------ | ----------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
|    1 | NCM Daily Bulletin(서술형 Wind/Sea)         | Medium       | wind_text, sea_state_text, wind_speed_kmhr(있으면)                                                                                           | “Moderate to fresh… strong at times over the sea…”, “The sea will be very rough…”                                     |
|    2 | NCM Sea State + Wave Height(ft) + Tide   | **High**     | **wave_ft_min/max**, sea_state_gulf, tide_hi/low_time                                                                                     | “Wave Height … 6 - 8 / 9 FT …”, “Low and High Tide For Abu Dhabi Represents The Arabian Gulf…”                        |
|    3 | **Southern Gulf Offshore Forecast(수치형)** | **Critical** | **valid_from/to(LT)**, **warning**, **wind_dir + wind_kt_min/max + gust**, **wave_ft_min/max**, **period_sec_min/max**, **visibility_nm** | “VALID FROM: 0800…TO: 2000…”, “WARNING: NIL.”, “WIND … 07-14 KT…10-16/18 KT”, “WAVE H. …3-4/5 FT”, “PERIOD 2-3/4 SEC” |
|    4 | ADNOC 2-day Trends(그래프/수치)               | Medium       | trend_wind_kt_max, trend_combined_sea_swell_ft_max, turning_point                                                                         | “ADNOC - 2 DAYS WEATHER TRENDS… HEIGHT OF COMBINED SEA & SWELL… WIND SPEED (KT)”                                      |
|    5 | ADNOC 7-day Trends(그래프/수치)               | Medium       | 7d_window_risk_flag, week_max_wind/wave                                                                                                   | “ADNOC - 7 DAYS WEATHER TRENDS… HEIGHT OF COMBINED SEA & SWELL… WIND SPEED”                                           |
|    6 | 이미지/차트 페이지                               | Low~Medium   | (텍스트 파서로는 추출 불가)                                                                                                                          | **Text Chars=0** → 이미지 기반(별도 이미지 해석 필요)                                                                               |
|    7 | 이미지/차트 페이지                               | Low~Medium   | (텍스트 파서로는 추출 불가)                                                                                                                          | **Text Chars=0**                                                                                                      |
|    8 | 이미지/차트 페이지                               | Low~Medium   | (텍스트 파서로는 추출 불가)                                                                                                                          | **Text Chars=0**                                                                                                      |

---

## 3) 결론: GO/STOP 확인을 위한 “핵심 포인터” 최소셋

**필수(판정 입력값):**

* **P3:** `valid_from_lt`, `valid_to_lt`, `warning`, `wind_kt_min/max(+gust)`, `wave_ft_min/max`, `period_sec`, `visibility_nm`
* **P2:** `wave_ft_max`(NCM Sea State 표), `sea_state_gulf`, `tide_hi/low`(옵션)

**권장(리스크 보강):**

* **P4~P5:** `trend_combined_sea_swell_ft_max`, `trend_wind_kt_max`, turning point 플래그
* **P6~P8:** 이미지 판독(차트/시놉틱)로 교차검증(단, STOP 단독 근거로 쓰기엔 약함)

---

### CmdRec (바로 실행)

* `/logi-master weather-tie --KRsummary` : **P2+P3에서 SSOT 컬럼(위 필드)로 자동 추출 포맷** 만들기
* `/switch_mode ORACLE + /logi-master weather-tie` : **Outlook 악화(turning point) 기반 “Delay 권고” 플래그 포함**

**판정: 예(필수)** — P6~P8은 **이미지(차트) 기반**이라서, MZP→AGI Sea Transit GO/STOP 신뢰도를 올리려면 **차트에서 “관측/패턴” 포인터를 추가로 추출**해야 합니다.
**근거:** P6/P8은 **SYNOP/Marine chart**로 **항로 인접(USSC/Arzana/Zirku/Jebel Ali/SW Fateh)**에 **파고(ft) 라벨(예: 1–2FT, 2–3FT)**이 직접 표기되어 있고, P7은 **MSLP(등압선)**으로 바람 강화 가능성을 간접 판별합니다(업로드된 `weather_page_6/7/8.png`).
**다음행동:** 아래 “이미지 차트 핵심 포인터”를 SSOT에 추가하고, **P3(Offshore Forecast) 수치와 불일치 시 STOP/DELAY 플래그**를 걸면 됩니다.

---

## 이미지 차트도 포함한 Page별 영향도(업데이트)

| Page | 차트 종류                                           | GO/STOP 영향도        | 이미지에서 추출해야 할 “핵심 포인터”                                                                                                                        | 판정에서 쓰는 방식                                                              |
| ---: | ----------------------------------------------- | ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
|    6 | **SYNOP(Arabian Gulf 관측/표기)**                   | **Medium(교차검증)**   | ① **Timestamp(예: SYNOP 15.02.2026 00:00 UTC)** ② **항로 인접 구역 Wave(ft) 라벨**(USSC/Arzana/Zirku/Jebel Ali/SW Fateh 등) ③ 항로 주변 관측 심볼 밀도(관측 공백 여부) | **P3 예보 Wave(ft)**와 비교해서 **“현재 관측이 더 높으면” 보수적으로 STOP/DELAY 후보**         |
|    7 | **MSLP Pressure Chart(등압선)**                    | **Low~Medium(패턴)** | ① UAE/Arabian Gulf 주변 **등압선 간격(압력경도)** ② 인근 **H/L 중심 및 중심기압**(예: H 1021 등) ③ Gulf 쪽 등압선 굴곡(전선성 변화 느낌)                                        | 등압선이 조밀(압력경도↑)이면 **Wind 상승 리스크** → P3 Wind(kt) 상단값에 가중(AMBER)           |
|    8 | **Marine chart(SYNOP+METAR 기반, 기류/전선 패턴 + 관측)** | **Medium(교차검증)**   | ① **Timestamp/Valid(00 UTC)** ② **대규모 흐름(굵은 화살표 방향)** ③ **항로 인접 Wave(ft) 라벨**(1–2FT, 2–3FT 등) ④ 주요 관측점의 **Wind barb(방향/속력)**(가독 범위 내)        | “흐름 방향 + 관측 파고(ft)”로 **항로 체감 sea state**를 보강. P3/P2가 애매할 때 **결정 근거 강화** |

---

## “이미지 차트” 추출 포맷(SSOT 컬럼) — 최소셋

> 숫자 2자리 고정(필요 시 ft→m 변환은 별도)

* `synop_ts_utc` (P6/P8)
* `route_wave_ft_obs_min`, `route_wave_ft_obs_max` *(P6/P8 라벨 기반: 예 1–2FT, 2–3FT)*
* `route_areas_covered` *(USSC/ARZANA/ZIRKU/JEBEL_ALI/SW_FATEH …)*
* `mslp_gradient_flag` *(P7: LOW/MED/HIGH — 등압선 간격 정성 플래그)*
* `flow_dir_major` *(P8: 큰 흐름 방향, 예: NW→SE 등)*

---

## GO/STOP 결합 로직(이미지 포함) — “불일치 처리”만 추가

* **Rule A (예보 우선):** 기본 판정은 **P3(Offshore Forecast) 수치**로 한다.
* **Rule B (관측 상향 보수):** 이미지(P6/P8)에서 **항로 인접 관측 파고 라벨이 P3 상단값보다 높게 보이면** → `OBS>FCST` 플래그 → **STOP/DELAY 후보**로 승격.
* **Rule C (패턴 가중):** P7에서 **압력경도(등압선 조밀)**가 높으면 → Wind 상향 가능 → **P3 Wind 상단값 기준으로 리스크(AMBER) 가중**.

---

### CmdRec

* `/logi-master weather-tie` : **P2+P3 수치 + (P6~P8 관측/패턴 플래그)**까지 합쳐 **GO/STOP SSOT 1행** 생성

원하면, 지금 올려주신 **P6~P8 이미지에서 “항로 인접 Wave(ft) 라벨(1–2FT/2–3FT)만” 먼저 정확히 목록화**해서 `route_wave_ft_obs_*` 컬럼을 채운 표로 바로 보고하겠습니다.

---

## 2026-02-03 Folder Batch Parse (sea-transit-go-nogo)

- Input folder: `C:\tr_dash-main\docs\weather\20260203`
- Applied thresholds: `Hs_limit=3.0m`, `Hmax_allow=5.5m`, `Wind_limit=25kt`, `Sailing=12h`, `Reserve=0h`
- Folder decision: **CONDITIONAL**

### Per-file decisions
- `03-02-2026-EN.pdf`: `CONDITIONAL` (`WX_WINDOW_GAP`)
- `ADNOC-TR02-03-2026-01.pdf`: `ZERO` (`WX_SQUALL_BUFFER`, `WX_PARSE_FAIL`)
- `ADNOC-TR07-03-02-2026.pdf`: `ZERO` (`WX_SQUALL_BUFFER`, `WX_PARSE_FAIL`)
- `ADNOC_DAILY_FORECAST_03022026_1.pdf`: `CONDITIONAL` (`WX_WINDOW_GAP`)

### Non-PDF materials detected
- `MR.JPG`
- `SF.jpg`
- `ST.jpg`

### Generated outputs
- `out/sea_transit_docs_weather/20260203_folder/sea_transit_folder_report.md`
- `out/sea_transit_docs_weather/20260203_folder/sea_transit_folder_report.json`
- `out/sea_transit_docs_weather/20260203_folder/parsed_forecasts_by_file.json`
- `out/sea_transit_docs_weather/20260203_folder/sea_transit_reports_by_file.json`
