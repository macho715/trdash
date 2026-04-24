# Invoice Verification Report - 98256434

## 1. 검증 개요

| 항목 | 내용 |
|---|---|
| 검증 대상 파일 | `C:\tr_dash-main\docs\일정\98256434.xlsx` |
| Invoice Number | `98256434` |
| Invoice Date | `16.04.2026` |
| Due Date | `15.05.2026` |
| Customer | `SAMSUNG C & T CORPORATION- ABU DHABI` |
| Contract / Customer Ref. | `OLCOF24-ALS086` |
| Vessel | `JOPETWIL 71` / `JOPETWIL71` |
| 청구 항목 | Charter Hire for March 2026 |
| 청구 기간 | `01-Mar-2026 00:00` to `31-Mar-2026 23:59` |
| 청구 수량 | `31 Days` |
| 통화 | `USD` |
| 검증 결론 | 금액 산식, 세금, 환율, Due Date, Deck Log 증빙은 적정. 단, 2026년 3월까지 계약 단가가 유효하다는 계약 기간 근거는 추가 확인 필요. |

## 2. Executive Summary

Invoice `98256434`의 청구 금액은 workbook 내부 증빙 기준으로 산술적으로 올바르다.

청구 라인은 `31 Days x USD 12,000/day = USD 372,000`으로 계산되며, Invoice 상 금액, Order Confirmation 상 Net Value, Amount in Words, AED 환산 금액이 모두 일치한다. VAT는 `0%`로 표시되어 있고 Tax Amount도 `USD 0` / `AED 0`으로 일치한다.

또한 workbook 안에 포함된 Daily Deck Log는 `MARCH 2026`의 `Day 1`부터 `Day 31`까지 모두 존재하며, Vessel은 `JOPETWIL71`, Charterer는 `ADNOC L & S`, Ops Area는 `MW4 MUSAFFAH - ZAKUM FIELD`로 일관된다. 따라서 청구 수량 `31 Days`는 Deck Log 증빙과 부합한다.

다만, workbook 내 Amendment No. 1의 rate clause는 `US$ 12,000 per day` 및 `USD 1 = AED 3.6725`를 뒷받침하지만, 같은 조항에 `extended period of 180 days (until 7th July 2025)`라는 문구가 있다. Invoice 청구 기간은 `March 2026`이므로, 이 amendment 문구만으로는 2026년 3월까지 동일 단가가 유효하다고 최종 확정하기 어렵다. 최종 승인 전에는 2026년 3월 청구를 커버하는 계약 연장, PO, variation, sales order approval 또는 별도 rate confirmation을 확인해야 한다.

## 3. Source Evidence

### 3.1 Tax Invoice Header

| 항목 | 확인 값 |
|---|---|
| Invoice Number | `98256434` |
| Invoice Date | `16.04.2026` |
| Customer Number | `10069290` |
| Customer Name | `SAMSUNG C & T CORPORATION- ABU DHABI` |
| TRN Number | `100326220900003` |
| Customer Ref No. | `OLCOF24-ALS086` |
| Contract No. | `OLCOF24-ALS086` |
| Currency | `USD` |
| Due Date | `15.05.2026` |

### 3.2 Invoice Line Item

| 항목 | 확인 값 |
|---|---|
| Item No. | `20` |
| Description | `JOPETWIL 71 - Charter Hire from 01-Mar-2026 00:00 to 31-Mar-2026 23:59 & 110013013537` |
| UOM | `Days` |
| Quantity | `31` |
| Unit Price | `USD 12,000` |
| Amount | `USD 372,000` |
| Tax Rate | `0%` |
| Tax Amount | `USD 0` |
| Amount Incl. Tax | `USD 372,000` |

### 3.3 Total Amount Section

| 항목 | AED | USD |
|---|---:|---:|
| Total Amount Before Tax | `1,366,170.00` | `372,000.00` |
| Discount | `0.00` | `0.00` |
| Tax | `0.00` | `0.00` |
| Total Amount After Tax | `1,366,170.00` | `372,000.00` |

### 3.4 Amount in Words and Exchange Rate

| 항목 | 확인 값 |
|---|---|
| USD Amount in Words | `US DOLLAR THREE HUNDRED SEVENTY TWO THOUSAND ONLY.` |
| AED Amount in Words | `UAE DIRHAM ONE MILLION THREE HUNDRED SIXTY SIX THOUSAND ONE HUNDRED SEVENTY ONLY.` |
| Exchange Rate | `3.67250`, Document Currency USD to Company Code Currency AED |

### 3.5 Order Confirmation

| 항목 | 확인 값 |
|---|---|
| Sales Order Number | `112546296` |
| Sales Order Date | `15.04.2026` |
| Sales Order Net Value | `USD 372,000.00` |
| Sales Order Currency | `USD` |
| Customer Ref No. | `OLCOF24-ALS086` |
| Contract No. | `OLCOF24-ALS086` |
| Document Date | `31.03.2026` |
| Order Line Description | `JOPETWIL 71 - Charter Hire from 01-Mar-2026 00:00 to 31-Mar-2026 23:59` |
| Material | `110013013537` |
| Quantity | `31 Days` |
| Unit Price | `USD 12,000` |
| Amount Before Tax | `USD 372,000` |
| Tax Rate | `0%` |
| Tax Amount | `USD 0` |
| Amount Incl. Tax | `USD 372,000` |

### 3.6 Deck Log Evidence

Converted workbook `98256434.xlsx` contains `31` Daily Deck Log sections.

| 항목 | 확인 결과 |
|---|---|
| Deck Log count | `31` |
| Date coverage | `Day 1` through `Day 31` |
| Month | `MARCH` |
| Year | `2026` |
| Vessel | `JOPETWIL71` |
| Charterer | `ADNOC L & S` |
| Ops Area | `MW4 MUSAFFAH - ZAKUM FIELD` |

첫 번째 Daily Deck Log:

| 항목 | 값 |
|---|---|
| Day | `1` |
| Month | `MARCH` |
| Year | `2026` |
| Vessel | `JOPETWIL71` |
| Charterer | `ADNOC L & S` |
| Ops Area | `MW4 MUSAFFAH - ZAKUM FIELD` |

마지막 Daily Deck Log:

| 항목 | 값 |
|---|---|
| Day | `31` |
| Month | `MARCH` |
| Year | `2026` |
| Vessel | `JOPETWIL71` |
| Charterer | `ADNOC L & S` |
| Ops Area | `MW4 MUSAFFAH - ZAKUM FIELD` |

### 3.7 Off Hire / Demobilization Evidence

Workbook에는 Vessel Hire Summary Report 형태의 Off Hire 증빙도 포함되어 있다.

| 항목 | 확인 값 |
|---|---|
| Status | `Off Hire` |
| Date & Time | `31/Mar/2026 23:59` |
| Diesel balance | `4,948.20 IG` |
| Water balance | `2,864.40 IG` |
| Remarks | `The vessel has been demobilized by Samsung C & T` |

이 Off Hire 시간은 Invoice 청구 종료 시각 `31-Mar-2026 23:59`와 일치한다.

## 4. Arithmetic Verification

### 4.1 Charter Hire Amount

Formula:

```text
Quantity x Unit Price = Amount
31 Days x USD 12,000/day = USD 372,000
```

Result:

| 항목 | 계산 값 | Invoice 값 | 결과 |
|---|---:|---:|---|
| Quantity | `31` | `31` | PASS |
| Unit Price | `12,000` | `12,000` | PASS |
| Amount | `372,000` | `372,000` | PASS |

### 4.2 VAT / Tax Verification

Invoice states services are subject to VAT at `0%`.

| 항목 | 계산 값 | Invoice 값 | 결과 |
|---|---:|---:|---|
| Tax Rate | `0%` | `0%` | PASS |
| Tax Amount USD | `0` | `0` | PASS |
| Amount Incl. Tax USD | `372,000` | `372,000` | PASS |

### 4.3 Exchange Rate Verification

Formula:

```text
USD 372,000 x 3.6725 = AED 1,366,170
```

Result:

| 항목 | 계산 값 | Invoice 값 | 결과 |
|---|---:|---:|---|
| Total Before Tax AED | `1,366,170.00` | `1,366,170.00` | PASS |
| Tax AED | `0.00` | `0.00` | PASS |
| Total After Tax AED | `1,366,170.00` | `1,366,170.00` | PASS |

### 4.4 Due Date Verification

Invoice payment terms:

```text
30 DAYS FROM INVOICE DATE (INVOICE DATE INCLUSIVE)
```

Invoice date is `16.04.2026`. Counting invoice date as day 1 gives due date `15.05.2026`.

| 항목 | 값 | 결과 |
|---|---|---|
| Invoice Date | `16.04.2026` | PASS |
| Payment Terms | `30 days inclusive` | PASS |
| Expected Due Date | `15.05.2026` | PASS |
| Invoice Due Date | `15.05.2026` | PASS |

## 5. Contract / Rate Verification

Workbook includes Amendment No. 1 to Supply Time Contract No. `OLCOF24-ALS086`.

The amendment section supports:

| 항목 | 확인 값 |
|---|---|
| Contract | `OLCOF24-ALS086` |
| Vessel | `JOPETWIL 71` |
| Charter Hire Rate | `US$ 12,000 per day` |
| Exclusions | Consumables such as Fuel, Water and Lubes excluded |
| Exchange Rate | `USD 1 = AED 3.6725` |

However, the same amendment text also states:

```text
Charter Hire would be applicable for the extended period of 180 days (until 7th July 2025)
```

This creates a contract-period evidence gap because Invoice `98256434` bills for `March 2026`, which is after `7th July 2025`.

### Contract Evidence Assessment

| 검증 항목 | 결과 | 비고 |
|---|---|---|
| Unit rate `USD 12,000/day` exists in workbook | PASS | Amendment No. 1 supports the daily rate. |
| Exchange rate `3.6725` exists in workbook | PASS | Amendment No. 1 and invoice both support the exchange rate. |
| Invoice amount matches sales order | PASS | Sales Order Net Value is `USD 372,000`. |
| Contract period clearly covers March 2026 | EXCEPTION | Amendment text visible in workbook mentions extended period until `7th July 2025`. |

## 6. Detailed Check Matrix

| No. | Check | Result | Evidence / Comment |
|---:|---|---|---|
| 1 | Invoice number identified | PASS | `98256434` |
| 2 | Invoice date identified | PASS | `16.04.2026` |
| 3 | Customer identified | PASS | `SAMSUNG C & T CORPORATION- ABU DHABI` |
| 4 | Contract / customer reference identified | PASS | `OLCOF24-ALS086` |
| 5 | Service period identified | PASS | `01-Mar-2026 00:00` to `31-Mar-2026 23:59` |
| 6 | Quantity matches March 2026 calendar days | PASS | `31 Days` |
| 7 | Daily Deck Logs exist for full period | PASS | Day `1-31`, Month `MARCH`, Year `2026` |
| 8 | Vessel in deck logs matches invoice | PASS | `JOPETWIL71` |
| 9 | Unit price applied correctly | PASS | `USD 12,000/day` |
| 10 | Line amount calculated correctly | PASS | `31 x 12,000 = 372,000` |
| 11 | VAT/tax calculated correctly | PASS | `0%`, `USD 0` |
| 12 | USD total matches line item | PASS | `USD 372,000` |
| 13 | AED total matches exchange rate | PASS | `AED 1,366,170` |
| 14 | Amount in words matches amount | PASS | USD and AED words match totals. |
| 15 | Due date matches payment terms | PASS | `15.05.2026` based on inclusive 30 days. |
| 16 | Sales order supports net value | PASS | Sales Order Net Value `USD 372,000`. |
| 17 | Off Hire timestamp aligns with billing end | PASS | `31/Mar/2026 23:59`. |
| 18 | Contract rate is evidenced | PASS | Amendment shows `US$ 12,000/day`. |
| 19 | Contract period covers March 2026 | EXCEPTION | Visible amendment wording says extended period until `7th July 2025`. |

## 7. Exceptions and Required Follow-up

### Exception 1 - Contract Validity Period for March 2026

The main unresolved item is the contract validity period.

The workbook supports the `USD 12,000/day` rate, but the included amendment wording appears to limit the referenced extension period to `7th July 2025`. Since this invoice bills `March 2026`, a further supporting document is needed to confirm the same rate remains valid for the invoice period.

Recommended acceptable evidence:

- Additional amendment extending `OLCOF24-ALS086` beyond July 2025
- Purchase Order or revised Sales Order approving March 2026 charter hire
- Rate confirmation from ADNOC L&S / OFCO / authorized commercial party
- Contract variation or continuation instruction covering March 2026
- Internal approval tying Sales Order `112546296` to the applicable contract/rate

### Exception 2 - Consumables Exclusion

The amendment rate clause states the `US$ 12,000/day` charter hire excludes consumables such as Fuel, Water and Lubes.

Invoice `98256434` only bills charter hire and does not separately charge consumables. This is not an invoice error, but any separate consumables settlement should be checked independently if another invoice exists.

## 8. Final Assessment

### Approved from Arithmetic and Operational Evidence Perspective

Invoice `98256434` is internally consistent:

- Quantity is supported by March 1-31 deck logs.
- Unit price and total are mathematically correct.
- VAT is consistently applied at `0%`.
- AED conversion matches the stated exchange rate.
- Due date matches inclusive 30-day payment terms.
- Sales Order Confirmation supports the invoice net value.
- Off Hire timestamp matches the invoice period end.

### Conditional from Contract Coverage Perspective

The invoice should be treated as **commercially supportable but contract-period confirmation required**.

The only material exception is whether the `USD 12,000/day` rate under `OLCOF24-ALS086` remained valid for March 2026. The workbook includes rate evidence, but the visible amendment period wording does not clearly extend to March 2026.

## 9. Recommendation

Recommended action:

1. Accept the invoice arithmetic and operational evidence as correct.
2. Before final approval/payment, obtain or reference the document that extends or approves the `USD 12,000/day` rate for March 2026.
3. If such document is already represented by Sales Order `112546296`, attach or cite the approval trail for that Sales Order.
4. No correction is required to the invoice amount unless contract coverage review finds that a different rate or period applies.

## 10. Verification Commands Run

The following local verification commands were run during the review:

| Command | Result | Purpose |
|---|---|---|
| `python -X utf8 -` workbook structure/header extraction | PASS | Confirmed workbook path, sheet, invoice header, line item, totals, order confirmation, amendment text. |
| `python -X utf8 -` invoice arithmetic/order/rate checks | PASS with exception | Confirmed line arithmetic, VAT, USD totals, AED exchange, due date, service quantity, order confirmation, and rate value. Flagged contract period coverage. |
| `python -X utf8 -` decklog coverage QA | PASS | Confirmed 31 Daily Deck Logs for March 2026, days 1-31, vessel `JOPETWIL71`. |

One earlier validation attempt timed out because `openpyxl` read-only random cell access was too slow on the converted workbook. The same checks were rerun using array-based loading and passed.

