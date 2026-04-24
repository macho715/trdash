# Bidirectional Schedule Cascade — Design Spec

**Date:** 2026-04-23  
**Scope:** TR5 PreOp Gantt (`TR5_PreOp_Gantt_20260415_162140.xlsm`) — `modMIR_Gantt_Unified`  
**Status:** Approved → Implementing

---

## Problem

When a task's Start date is changed, only downstream (later) tasks shift.  
Tasks BEFORE the changed row (upstream) stay fixed — breaking the sequential chain.

**Example:** Load-out Start: 5/10 → 5/5 (delta = −5d)  
- Expected: ALL rows shift −5d (both before and after Load-out)  
- Actual: Only rows after Load-out shift

---

## Decision

**Sequential chain cascade (bidirectional):**  
- COL_START change → ShiftDownstream (existing) + ShiftUpstream (new)  
- COL_END / COL_DAYS change → ShiftDownstream only (duration change doesn't affect predecessors)  
- No date floor constraint (pure simulation — free movement in any direction)  
- GATE rows participate in cascade (no special treatment)  
- Section/group header rows (`IsGroupRow`) skipped in both directions

---

## Architecture

```
User edits Start of row R
       │
       ▼
HandleShiftMode (COL_START case)
       │  delta = new_start − old_start
       ├──► ShiftDownstream(ws, R, delta)   ← existing (rows R+1 → lastRow)
       └──► ShiftUpstream(ws, R, delta)     ← NEW     (rows R-1 → FIRST_DATA_ROW)
```

---

## New Function: `ShiftUpstream`

```vba
Private Sub ShiftUpstream(ByVal ws As Worksheet, ByVal fromRow As Long, ByVal delta As Long)
    On Error GoTo EH

    Dim r As Long
    Dim st As Date, en As Date
    Dim useWD As Boolean: useWD = CfgOn("CFG_SHIFT_WORKDAYS_ONLY", False)

    For r = fromRow - 1 To FIRST_DATA_ROW Step -1
        If IsGroupRow(ws, r) Then GoTo ContinueLoop

        If TryGetCellDate(ws.Cells(r, COL_START), st) And _
           TryGetCellDate(ws.Cells(r, COL_END), en) Then

            st = AddDays(st, delta, useWD)
            en = AddDays(en, delta, useWD)

            ws.Cells(r, COL_START).Value2 = st
            ws.Cells(r, COL_END).Value2   = en
            SafeSetNumberFormat ws.Cells(r, COL_START), "yyyy-mm-dd"
            SafeSetNumberFormat ws.Cells(r, COL_END),   "yyyy-mm-dd"
            UpdateDaysFromStartEnd ws, r
        End If
ContinueLoop:
    Next r

    Exit Sub
EH:
    LogMsg "ShiftUpstream", Err.Number & " - " & Err.Description, ws.Name, fromRow
End Sub
```

---

## Modification: `HandleShiftMode` — COL_START case

**Before:**
```vba
If delta <> 0 Then ShiftDownstream ws, r, delta, False
```

**After:**
```vba
If delta <> 0 Then ShiftDownstream ws, r, delta, False
If delta <> 0 Then ShiftUpstream ws, r, delta
```

---

## Official References

| API | URL |
|-----|-----|
| `Range.Value2` | https://learn.microsoft.com/en-us/office/vba/api/excel.range.value2 |
| `DateAdd` | https://learn.microsoft.com/en-us/office/vba/language/reference/user-interface-help/dateadd-function |
| `Application.EnableEvents` | https://learn.microsoft.com/en-us/office/vba/api/excel.application.enableevents |
| `Range.NumberFormat` | https://learn.microsoft.com/en-us/office/vba/api/excel.range.numberformat |
| `Worksheet.Change` | https://learn.microsoft.com/en-us/office/vba/api/excel.worksheet.change |

---

## Files Changed

| File | Change |
|------|--------|
| `modMIR_Gantt_Unified` (VBA) | Add `ShiftUpstream` Sub; modify `HandleShiftMode` COL_START |
| `TR5_PreOp_Gantt_20260415_162140.xlsm` | Patched workbook |
