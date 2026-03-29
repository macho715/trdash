**판정: 조건부(AMBER)** — PDF+이미지 차트까지 **전부(8/8p)** 파싱·판독 완료했으며, **Mina Zayed Port → AGI Sea Transit** GO/STOP 판단을 위한 “핵심 입력값(수치+관측)”을 **한 덩어리 SSOT**로 정리했습니다.
**근거:** P1~P5는 **텍스트 파서**로 추출(문장/표/헤더 확인), P6~P8은 **텍스트 레이어 0**이라 **업로드 PNG(차트) 직접 판독**으로 파고(ft)·시간(UTC)·패턴을 추가 확보했습니다.
**다음행동:** 최종 GO/STOP은 **선박 한계치(Hs_limit_m 또는 Hmax_allow_m, Wind_limit_kt, Sailing_hr)** 없이는 확정 불가 → 아래 SSOT에 한계치만 매핑하면 즉시 판정 가능합니다.

---

# 0) Exec Summary (MZP→AGI Sea Transit Weather Pack, 2026-02-15)

* **유효 예보(Offshore, P3):** `VALID 0800–2000 15/02/2026 LT`, `WARNING: NIL`, Wind **SW–NW 07–14 kt → NW 10–16/18 kt**, Wave **2–3 ft → 3–4/5 ft**, Period **2–3/4 sec**.
* **NCM Sea State/파고(연안·일반, P2):** Arabian Gulf **“Slight→Moderate, Rough→Very Rough at times by night”**, Wave Height **2–4 ft at first**, **increasing to 6–8/9 ft by evening**(표기 그대로).
* **관측/차트(SYNOP/Marine, P6/P8 @ 15.02.2026 00:00 UTC):** 항로 인접 표기 파고 **1–2 ft / 2–3 ft**(USSC, ARZANA, ZIRKU, SW FATEH, JEBEL ALI).
* **결론:** “현재 관측(1–3 ft)” vs “예보/공지(최대 5 ft 또는 9 ft)”가 **레벨이 다름** → **항로/시간대(0800–2000 LT & evening/night) 분리**해서 판단해야 함.

---

# 1) Visual-first: Page별 구조 + 영향도 + 추출 필드(SSOT)

| Page | 타입         | 핵심 내용(파서/판독)                                      | GO/STOP 영향도  | 반드시 추출(필드명)                                                                                                |
| ---: | ---------- | ------------------------------------------------- | ------------ | ---------------------------------------------------------------------------------------------------------- |
|    1 | Text       | NCM Daily Bulletin(서술형)                           | Medium       | `general_desc`, `wind_kmh_range`, `over_sea_strong_flag`                                                   |
|    2 | Text       | NCM Sea State + Wave Height(ft) + Tide Notice     | **High**     | `sea_state_gulf_text`, `wave_ft_now_range`, `wave_ft_evening_max`, `tide_times_abudhabi`                   |
|    3 | Text       | **Southern Gulf Offshore Forecast(수치형)**          | **Critical** | `valid_from_lt`, `valid_to_lt`, `warning`, `wind_kt_min/max/gust`, `wave_ft_min/max`, `period_sec_min/max` |
|    4 | Text+Graph | ADNOC 2-days Trends(그래프: 값은 시각 판독 필요)             | Medium       | `trend_ref_2d`(그래프 이미지 판독 시)                                                                               |
|    5 | Text+Graph | ADNOC 7-days Trends(with operational limits)      | Medium       | `trend_ref_7d`(그래프 이미지 판독 시)                                                                               |
|    6 | Image      | SYNOP(파고 박스+지점 라벨) @ **15.02.2026 00:00**         | Medium       | `synop_ts_utc`, `route_wave_ft_obs_labels`                                                                 |
|    7 | Image      | MSL Pressure @ **15.02.2026 00:00**               | Low~Med      | `mslp_ts_utc`, `pressure_gradient_flag`                                                                    |
|    8 | Image      | Marine chart(흐름 화살표+파고 라벨) @ **15.02.2026 00:00** | Medium       | `marine_ts_utc`, `flow_dir_major`, `route_wave_ft_obs_labels`                                              |

---

# 2) “핵심 수치” 일괄 추출 결과 (원문 기반)

## 2.1 Offshore Forecast (P3) — **GO/STOP 1순위 입력**

* **Validity:** `0800–2000 15/02/2026 LT`
* **Warning:** `NIL`
* **Inference:** `weak to moderate pressure gradient`
* **Areas(항로 인접 Offshore band):**

  * `UMM SHAIF, DAS ISLAND, NASR, ABK, ZIRKU`
  * `ZAKUM AND SARB FIELDS`
  * `SATTAH AND ARZANAH AREAS`
* **Wind:** `SW–NW 07–14 kt at first → NW 10–16/18 kt by Sunday evening`
* **Wave Height:** `2–3 ft at first → 3–4/5 ft by Sunday evening`
* **Period:** `2–3/4 sec`

> ft→m 변환(참고, 1 ft=0.3048 m)

* **2–3 ft = 0.61–0.91 m**
* **3–4/5 ft = 0.91–1.22 / 1.52 m**

---

## 2.2 NCM Sea State/Wave Height (P2) — **악화(야간/저녁) 리스크 입력**

* **Sea State(Arabian Gulf):** `Slight to Moderate, becoming Rough to Very Rough at times by night`
* **Wave Height:**

  * `2–4 ft at first`
  * `increasing to 6–8/9 ft by evening`

> ft→m 변환(참고)

* **2–4 ft = 0.61–1.22 m**
* **6–8/9 ft = 1.83–2.44 / 2.74 m**

---

## 2.3 SYNOP/Marine chart 관측 라벨 (P6 & P8, 이미지 판독) — **“현재” 교차검증**

**Timestamp:** `SYNOP 15.02.2026 00:00 (UTC 표기)`
**항로 인접 라벨(파고):**

* **P6:** `2–3`, `1–2` 박스 표기 + 지점 라벨

  * **ARZANA 2FT, ZIRKU 2FT, USSC 2FT, SW FATEH 1FT, JEBEL ALI 2FT**
* **P8:** 지점 라벨이 더 명확

  * **USSC 1–2FT, ARZANA 2–3FT, ZIRKU 1–2FT, SW FATEH 2–3FT, JEBEL ALI 2FT**

> 관측 라벨 ft→m(참고)

* **1–2 ft = 0.30–0.61 m**
* **2–3 ft = 0.61–0.91 m**

---

## 2.4 MSL Pressure (P7, 이미지 판독) — **Wind 상승 “가능성”만**

* **Timestamp:** `MSL Pressure 15.02.2026 00:00`
* 등압선 분포는 확인되나, 본 자료만으로 **Wind(kt) 직접 수치화는 불가** → **P3 Wind 상단(16/18 kt) 리스크 가중**에만 사용 권장.

---

# 3) GO/STOP 로직(해상 운항 전용) — “덩어리” 규칙 세트

## 3.1 입력(SSOT 최소셋)

* **Forecast(필수):** `valid_from/to`, `warning`, `wind_kt_max(or gust)`, `wave_ft_max`, `period_sec_max`
* **NCM 악화(필수):** `wave_ft_evening_max(=9ft)`, `night_very_rough_flag`
* **Obs(권장):** `route_wave_ft_obs_max(=3ft)` + `synop_ts_utc`
* **선박 한계치(필수):** `Hs_limit_m(or Hmax_allow_m)`, `Wind_limit_kt`, `Sailing_hr(+reserve)`

## 3.2 의사결정 규칙(안전 보수)

* **Rule 0 (Validity):** 지금 시간이 `valid_from/to` 밖이면 → **STOP(예보 무효)**
* **Rule 1 (Warning):** `WARNING != NIL` → **STOP 후보(즉시 상향)**
* **Rule 2 (Forecast Gate):** `wave_ft_max(예보)` 또는 `wind_kt_max(예보)`가 **선박 한계치 초과** → **STOP**
* **Rule 3 (Night/Evening Escalation):** NCM이 `6–8/9 ft by evening` 또는 `Very rough at times by night`이면 → **Evening/Night 구간은 별도 STOP Gate** (daytime GO라도 분리)
* **Rule 4 (OBS>FCST 보수):** 관측 라벨(예: 2–3 ft)이 예보 상단보다 높을 때 → **STOP/DELAY 후보**(이번 자료는 반대: OBS가 낮음)
* **Rule 5 (Period Penalty):** Period가 길어질수록(장주기) cargo/stability에 불리 → `period_sec_max`에 가중(현재 P3: 4 sec)

---

# 4) Options (A/B/C) — 비용/리스크/시간(ETA) 관점

| 옵션 | 개요                                                                               |                      Cost(추정) | Risk                             | Time                   |
| -- | -------------------------------------------------------------------------------- | ----------------------------: | -------------------------------- | ---------------------- |
| A  | **Offshore(P3) 기준으로 Daytime GO**, Evening/Night **STOP/DELAY** 분리 운영             | AED 0.00(운항 자체는 동일) + 대기비는 별도 | **Medium**(야간 악화 구간 회피)          | Daytime window에 맞추면 빠름 |
| B  | NCM(P2)의 **9 ft by evening**을 보수적으로 적용해 **전체 STOP**(운항 취소/연기)                    |               대기·재배치 비용 증가 가능 | **Low**(가장 보수)                   | 일정 지연 큼                |
| C  | **관측(P6/P8, 1–3 ft)**을 신뢰하고 GO하되, **2시간 단위 재검증**(update/nowcast) + Turnback plan |              운영부담(모니터링/통신) 증가 | **Medium~High**(예보가 상승 구간이면 리스크) | 가장 유연                  |

> ⚠️ AMBER: 비용(AED)은 계약/대기 단가(DSV/OFCO/Charter) 미제공이라 정량화 불가.

---

# 5) Roadmap (Prepare→Pilot→Build→Operate→Scale)

1. **Prepare (오늘):** SSOT 컬럼 고정(위 3.1) + 선박 한계치 입력 폼 배포(Owner: SCT Logistics)
2. **Pilot (1회 운항):** P3/P2/P6-8을 1행으로 묶어 **GO/STOP 결과와 실제 Sea State**를 로그(Owner: Marine/Ops)
3. **Build:** `OBS/FCST divergence` 플래그 + `evening/night split` 자동화(Owner: Automation)
4. **Operate:** 매 운항마다 `Valid/Warning/Wind/Wave/Period/Obs` 자동 리포트(Owner: Ops)
5. **Scale:** TR Voyages 전 구간 표준화 + KPI 연동(OTIF, delay alerts/day ≤ 1.00)

---

# 6) Automation Notes (RPA+LLM+Sheets/TG)

* PDF 파싱(P1~P5) + 이미지 라벨(P6~P8) → **SSOT JSON 1건**으로 합치기
* TG/WhatsApp 공지 템플릿:

  * “**Offshore valid window / Warning / Max wind / Max wave / Evening risk / Obs check**” 6줄 고정

---

# 7) QA 체크리스트(오판 방지)

* [ ] 지금 운항 예정 시간이 **P3 Validity(0800–2000 LT)** 안인가
* [ ] “Evening”이 **운항구간에 포함**되는가(출항/도착/중간 항해 포함)
* [ ] 선박 한계치(Hs/Wind) 문서 근거(스펙/운항기준) 확보했는가
* [ ] P6/P8 관측 라벨이 항로(MZP→AGI)와 실제로 겹치는가(경유/우회 고려)
* [ ] Period(최대 4 sec) + Cargo 특성(OOG/CG/Seafastening) 고려했는가

---

## CmdRec

* `/switch_mode ORACLE + /logi-master weather-tie`
* `/logi-master report --KRsummary`

---

# 8) ZERO “중단” 로그(최종 GO/STOP 확정에 필요한 입력 3개)

| 단계         | 이유         | 위험                  | 요청데이터                                                                            | 다음조치                                  |
| ---------- | ---------- | ------------------- | -------------------------------------------------------------------------------- | ------------------------------------- |
| GO/STOP 확정 | 선박 한계치 미제공 | 과소평가 시 해상 안전/일정 리스크 | 1) `Hs_limit_m(or Hmax_allow_m)` 2) `Wind_limit_kt` 3) `Sailing_hr + Reserve_hr` | 값 수령 즉시 위 SSOT에 매핑 → GO/STOP 1줄 판정 출력 |

---

## UnifiedJSON v1.2 (요약)

```json
{
  "exec_summary": {
    "verdict": "AMBER_CONDITIONAL",
    "key_points": [
      "P3 Offshore valid 0800-2000 2026-02-15 LT, Warning NIL, Wind up to 18 kt, Wave up to 5 ft, Period up to 4 sec",
      "P2 NCM Arabian Gulf wave increasing to 6-8/9 ft by evening; very rough at times by night",
      "P6/P8 SYNOP/MARINE 2026-02-15 00:00 UTC route-adjacent labels mostly 1-3 ft"
    ],
    "required_inputs_for_final_go_stop": ["Hs_limit_m(or Hmax_allow_m)", "Wind_limit_kt", "Sailing_hr+Reserve_hr"]
  },
  "visuals": {
    "page_map": [
      {"page": 3, "impact": "CRITICAL", "fields": ["valid_from_lt","valid_to_lt","warning","wind_kt_max","wave_ft_max","period_sec_max"]},
      {"page": 2, "impact": "HIGH", "fields": ["wave_ft_evening_max","sea_state_gulf_text"]},
      {"page": 6, "impact": "MED", "fields": ["synop_ts_utc","route_wave_ft_obs_labels"]},
      {"page": 8, "impact": "MED", "fields": ["marine_ts_utc","flow_dir_major","route_wave_ft_obs_labels"]},
      {"page": 7, "impact": "LOW_MED", "fields": ["mslp_ts_utc","pressure_gradient_flag"]}
    ]
  },
  "options": [
    {"id":"A","summary":"Daytime GO, Evening/Night STOP split","risk":"MED","time":"FAST"},
    {"id":"B","summary":"Conservative STOP using evening 9ft risk","risk":"LOW","time":"SLOW"},
    {"id":"C","summary":"GO with 2-hour recheck + turnback plan","risk":"MED_HIGH","time":"FLEX"}
  ],
  "qa": {
    "checks": ["within_validity", "evening_in_route", "vessel_limits_attached", "obs_route_overlap", "period+cargo_effect"]
  },
  "meta": {"template_id":"LOGI_META_v2026.02", "revision": 8, "tz":"Asia/Dubai", "numeric_precision":"2-dec"}
}
```

원하시면, 지금 단계에서 **“선박 한계치 3개”만 주시면** 위 데이터로 **GO/STOP을 1줄로 확정**(Daytime/Evening 분리 포함)해서 다시 보고하겠습니다.
    