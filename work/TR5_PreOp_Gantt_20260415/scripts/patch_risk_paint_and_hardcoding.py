from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path

import pythoncom
import win32com.client as win32


ROOT = Path(r"C:\tr_dash-main")
XLSM = ROOT / "work" / "TR5_PreOp_Gantt_20260415" / "excel" / "TR5_PreOp_Gantt_20260415_162140.xlsm"
MODULE = "modMIR_Gantt_Unified"


OLD_REFRESH_PAINT_ONLY = '''Private Sub RefreshPaintOnly(ByVal ws As Worksheet, ByVal includeToday As Boolean)
    On Error GoTo EH
    Dim minD As Date, maxD As Date
    Dim renderEndCol As Long
    Dim clearEndCol As Long
    
    GetMinMaxDates ws, minD, maxD
    If includeToday Then
        If Date < minD Then minD = Date
        If Date > maxD Then maxD = Date
    End If
    
    renderEndCol = DATE_COL_START + DateDiff("d", minD, maxD)
    clearEndCol = HeaderLastCol(ws)
    If clearEndCol < renderEndCol Then clearEndCol = renderEndCol
    
    PaintBars ws, minD, maxD, clearEndCol
    ResetTimelineBorders ws, clearEndCol, LastUsedRow(ws)
    DrawTodayMarker ws, minD, maxD
    Exit Sub
EH:
    LogMsg "RefreshPaintOnly", Err.Number & " - " & Err.Description, ws.Name
End Sub'''


NEW_REFRESH_PAINT_ONLY = '''Private Sub RefreshPaintOnly(ByVal ws As Worksheet, ByVal includeToday As Boolean)
    On Error GoTo EH
    Dim firstD As Date, lastD As Date
    Dim renderEndCol As Long
    Dim clearEndCol As Long
    
    ' Paint-only refresh must not move or resize the timeline.
    ' Risk edits repaint against the visible header dates to avoid bar drift.
    If Not TryParseDateValue(HeaderFirstDate(ws), firstD) Or _
       Not TryParseDateValue(HeaderLastDate(ws), lastD) Then
        GetMinMaxDates ws, firstD, lastD
        EnsureTimelineCovers ws, firstD, lastD
        BuildDateHeader ws, firstD, lastD
    End If
    
    If lastD < firstD Then
        GetMinMaxDates ws, firstD, lastD
    End If
    
    renderEndCol = DATE_COL_START + DateDiff("d", firstD, lastD)
    clearEndCol = HeaderLastCol(ws)
    If clearEndCol < renderEndCol Then clearEndCol = renderEndCol
    
    PaintBars ws, firstD, lastD, clearEndCol
    ResetTimelineBorders ws, clearEndCol, LastUsedRow(ws)
    DrawTodayMarker ws, firstD, lastD
    Exit Sub
EH:
    LogMsg "RefreshPaintOnly", Err.Number & " - " & Err.Description, ws.Name
End Sub'''


OLD_PAINT_RISK_BLOCK = '''        phase = CStr(ws.Cells(r, COL_PHASE).Value)
        risk = CStr(ws.Cells(r, COL_RISK).Value)
        
        Dim barColor As Long
        If InStr(1, risk, "HIGH", vbTextCompare) > 0 Or InStr(1, risk, "WARNING", vbTextCompare) > 0 Then
            barColor = HexToLong(C_RED)
        Else
            barColor = PhaseColorLong(phase)
        End If'''


NEW_PAINT_RISK_BLOCK = '''        phase = CStr(ws.Cells(r, COL_PHASE).Value)
        risk = CStr(ws.Cells(r, COL_RISK).Value)
        
        Dim barColor As Long
        barColor = RiskBarColorLong(risk, phase)'''


RISK_BAR_FUNCTION = '''Private Function RiskBarColorLong(ByVal risk As String, ByVal phase As String) As Long
    Select Case UCase$(Trim$(risk))
        Case "OK"
            RiskBarColorLong = HexToLong(C_BLUE)
        Case "AMBER"
            RiskBarColorLong = HexToLong(C_AMBER)
        Case "HIGH"
            RiskBarColorLong = HexToLong("F4B183")
        Case "WARNING"
            RiskBarColorLong = HexToLong("FCE4D6")
        Case "CRITICAL"
            RiskBarColorLong = HexToLong(C_RED)
        Case "GATE"
            RiskBarColorLong = HexToLong(C_YELLOW)
        Case Else
            RiskBarColorLong = PhaseColorLong(phase)
    End Select
End Function


'''


OLD_TIMELINE_MATCH_DECLARE = '''    Dim lastCol As Long
    Dim deleteCols As Long'''


NEW_TIMELINE_MATCH_DECLARE = '''    Dim lastCol As Long
    Dim deleteCols As Long
    Dim targetCols As Long
    Dim targetLastCol As Long'''


OLD_TIMELINE_MATCH_TRIM = '''    curLast = HeaderLastDate(ws)
    lastCol = HeaderLastCol(ws)
    If IsDate(curLast) Then'''


NEW_TIMELINE_MATCH_TRIM = '''    curLast = HeaderLastDate(ws)
    lastCol = HeaderLastCol(ws)
    targetCols = DateDiff("d", targetFirst, targetLast) + 1
    targetLastCol = DATE_COL_START + targetCols - 1
    If lastCol > targetLastCol Then
        deleteCols = lastCol - targetLastCol
        ws.Columns(targetLastCol + 1).Resize(, deleteCols).Delete Shift:=xlToLeft
        lastCol = HeaderLastCol(ws)
        curLast = HeaderLastDate(ws)
    End If
    If IsDate(curLast) Then'''


TRIM_TIMELINE_FUNCTION = '''Private Sub TrimTimelineToRange(ByVal ws As Worksheet, ByVal firstD As Date, ByVal lastD As Date)
    On Error GoTo EH
    Dim targetCols As Long
    Dim targetLastCol As Long
    Dim lastCol As Long
    Dim deleteCols As Long
    
    If lastD < firstD Then Exit Sub
    targetCols = DateDiff("d", firstD, lastD) + 1
    targetLastCol = DATE_COL_START + targetCols - 1
    lastCol = HeaderLastCol(ws)
    
    If lastCol > targetLastCol Then
        deleteCols = lastCol - targetLastCol
        ws.Columns(targetLastCol + 1).Resize(, deleteCols).Delete Shift:=xlToLeft
    End If
    Exit Sub
EH:
    LogMsg "TrimTimelineToRange", Err.Number & " - " & Err.Description, ws.Name
End Sub


'''


def normalize_vba(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def denormalize_vba(text: str) -> str:
    return text.replace("\n", "\r\n")


def patch_code(code: str) -> tuple[str, dict[str, int]]:
    text = normalize_vba(code)
    stats: dict[str, int] = {}

    old_exact_427 = "RefreshGanttExactRange ws, DateSerial(2026, 4, 27), DateSerial(2026, 5, 17), False"
    old_exact_422 = "RefreshGanttExactRange ws, DateSerial(2026, 4, 22), DateSerial(2026, 5, 12), False"
    stats["hardcoded_427_removed"] = text.count(old_exact_427)
    stats["hardcoded_422_removed"] = text.count(old_exact_422)
    text = text.replace(old_exact_427, "RefreshGantt ws, False")
    text = text.replace(old_exact_422, "RefreshGantt ws, False")

    stats["paint_true_calls_removed"] = text.count("RefreshPaintOnly ws, True")
    text = text.replace("RefreshPaintOnly ws, True", "RefreshPaintOnly ws, False")

    old_refresh = normalize_vba(OLD_REFRESH_PAINT_ONLY)
    new_refresh = normalize_vba(NEW_REFRESH_PAINT_ONLY)
    if old_refresh in text:
        text = text.replace(old_refresh, new_refresh, 1)
        stats["refresh_paint_only_replaced"] = 1
    elif new_refresh in text:
        stats["refresh_paint_only_replaced"] = 0
    else:
        raise RuntimeError("RefreshPaintOnly body did not match expected source.")

    old_risk = normalize_vba(OLD_PAINT_RISK_BLOCK)
    new_risk = normalize_vba(NEW_PAINT_RISK_BLOCK)
    if old_risk in text:
        text = text.replace(old_risk, new_risk, 1)
        stats["paint_risk_block_replaced"] = 1
    elif new_risk in text:
        stats["paint_risk_block_replaced"] = 0
    else:
        raise RuntimeError("PaintBars risk-color block did not match expected source.")

    if "Private Function RiskBarColorLong(" not in text:
        marker = "Private Function PhaseColorLong(ByVal phase As String) As Long\n"
        if marker not in text:
            raise RuntimeError("PhaseColorLong marker not found.")
        text = text.replace(marker, normalize_vba(RISK_BAR_FUNCTION) + marker, 1)
        stats["risk_bar_function_added"] = 1
    else:
        stats["risk_bar_function_added"] = 0

    old_declare = normalize_vba(OLD_TIMELINE_MATCH_DECLARE)
    new_declare = normalize_vba(NEW_TIMELINE_MATCH_DECLARE)
    if old_declare in text and new_declare not in text:
        text = text.replace(old_declare, new_declare, 1)
        stats["timeline_match_declare_patched"] = 1
    else:
        stats["timeline_match_declare_patched"] = 0

    old_trim = normalize_vba(OLD_TIMELINE_MATCH_TRIM)
    new_trim = normalize_vba(NEW_TIMELINE_MATCH_TRIM)
    if old_trim in text and new_trim not in text:
        text = text.replace(old_trim, new_trim, 1)
        stats["timeline_match_count_trim_added"] = 1
    elif new_trim in text:
        stats["timeline_match_count_trim_added"] = 0
    else:
        raise RuntimeError("EnsureTimelineMatches trim marker did not match expected source.")

    if "Private Sub TrimTimelineToRange(" not in text:
        marker = "Private Sub EnsureTimelineMatches(ByVal ws As Worksheet, ByVal targetFirst As Date, ByVal targetLast As Date)\n"
        if marker not in text:
            raise RuntimeError("EnsureTimelineMatches marker not found.")
        text = text.replace(marker, normalize_vba(TRIM_TIMELINE_FUNCTION) + marker, 1)
        stats["trim_timeline_function_added"] = 1
    else:
        stats["trim_timeline_function_added"] = 0

    refresh_marker = '''    EnsureTimelineCovers ws, minD, maxD
    renderEndCol = DATE_COL_START + DateDiff("d", minD, maxD)'''
    refresh_repl = '''    EnsureTimelineCovers ws, minD, maxD
    TrimTimelineToRange ws, minD, maxD
    renderEndCol = DATE_COL_START + DateDiff("d", minD, maxD)'''
    if normalize_vba(refresh_marker) in text and "TrimTimelineToRange ws, minD, maxD" not in text:
        text = text.replace(normalize_vba(refresh_marker), normalize_vba(refresh_repl), 1)
        stats["refresh_gantt_trim_call_added"] = 1
    else:
        stats["refresh_gantt_trim_call_added"] = 0

    exact_marker = '''    EnsureTimelineMatches ws, firstD, lastD
    clearEndCol = HeaderLastCol(ws)'''
    exact_repl = '''    EnsureTimelineMatches ws, firstD, lastD
    TrimTimelineToRange ws, firstD, lastD
    clearEndCol = HeaderLastCol(ws)'''
    if normalize_vba(exact_marker) in text and "TrimTimelineToRange ws, firstD, lastD" not in text:
        text = text.replace(normalize_vba(exact_marker), normalize_vba(exact_repl), 1)
        stats["exact_range_trim_call_added"] = 1
    else:
        stats["exact_range_trim_call_added"] = 0

    return denormalize_vba(text), stats


def workbook_snapshot(wb) -> dict[str, object]:
    ws = wb.Worksheets("Gantt_BASE")
    last_col = ws.Cells(3, ws.Columns.Count).End(-4159).Column  # xlToLeft
    return {
        "sheet_count": int(wb.Worksheets.Count),
        "gantt_first_header": str(ws.Cells(3, 11).Text),
        "gantt_last_header": str(ws.Cells(3, last_col).Text),
        "gantt_last_col": int(last_col),
        "risk_validation": str(ws.Range("G5").Validation.Formula1),
        "risk_before": str(ws.Range("G5").Value),
        "subtitle_formula": str(ws.Range("A2").Formula),
        "subtitle_value": str(ws.Range("A2").Value),
    }


def apply_dynamic_subtitle(wb) -> dict[str, object]:
    ws = wb.Worksheets("Gantt_BASE")
    try:
        wb.Names("MIR_SOURCE_LABEL").Delete()
    except Exception:
        pass
    source_name = wb.Names.Add(
        Name="MIR_SOURCE_LABEL",
        RefersTo='="TR5_Pre-Op_Simulation_v2_20260430.md"',
    )
    try:
        source_name.Visible = False
    except Exception:
        pass

    formula = (
        '=TEXT(TODAY(),"yyyy-mm-dd")'
        '&" | Source: "&IFERROR(MIR_SOURCE_LABEL,"TR5 schedule")'
        '&" | T+0="&TEXT($K$3,"yyyy-mm-dd")'
        '&" | Load-out="&TEXT(LOOKUP(2,1/($A$1:$A$100="BD2"),$D$1:$D$100),"yyyy-mm-dd")'
        '&" | AGI JD="&TEXT(LOOKUP(2,1/($A$1:$A$100="JDC"),$D$1:$D$100),"yyyy-mm-dd")'
    )
    ws.Range("A2").Formula = formula
    return {
        "formula": str(ws.Range("A2").Formula),
        "value": str(ws.Range("A2").Value),
        "has_d30_or_d42": ("D30" in str(ws.Range("A2").Formula) or "D42" in str(ws.Range("A2").Formula)),
        "has_hardcoded_output_dates": (
            "2026-05-04" in str(ws.Range("A2").Formula)
            or "2026-05-12" in str(ws.Range("A2").Formula)
            or "2026-04-30" in str(ws.Range("A2").Formula)
        ),
        "uses_step_lookup": ("LOOKUP" in str(ws.Range("A2").Formula) and "BD2" in str(ws.Range("A2").Formula) and "JDC" in str(ws.Range("A2").Formula)),
    }


def run() -> None:
    if not XLSM.exists():
        raise FileNotFoundError(XLSM)

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = XLSM.parent.parent / "logs" / f"risk_paint_patch_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    backup = run_dir / f"{XLSM.stem}.before_risk_paint_patch{XLSM.suffix}"
    report_path = run_dir / "validation_report.json"
    shutil.copy2(XLSM, backup)

    pythoncom.CoInitialize()
    app = None
    wb = None
    live_workbook = False
    app_state: dict[str, object] = {}
    result: dict[str, object] = {
        "target": str(XLSM),
        "backup": str(backup),
        "run_dir": str(run_dir),
    }
    try:
        try:
            app = win32.GetActiveObject("Excel.Application")
            for i in range(1, app.Workbooks.Count + 1):
                candidate = app.Workbooks(i)
                if str(candidate.FullName).lower() == str(XLSM).lower():
                    wb = candidate
                    live_workbook = True
                    result["attached_live_workbook"] = True
                    break
        except Exception:
            app = None

        if app is None:
            app = win32.DispatchEx("Excel.Application")
            app.Visible = False
            result["attached_live_workbook"] = False

        for prop in ("DisplayAlerts", "EnableEvents", "ScreenUpdating"):
            try:
                app_state[prop] = getattr(app, prop)
            except Exception:
                pass

        app.DisplayAlerts = False
        app.EnableEvents = False
        app.AutomationSecurity = 3

        if wb is None:
            wb = app.Workbooks.Open(str(XLSM), UpdateLinks=0, ReadOnly=False, IgnoreReadOnlyRecommended=True, AddToMru=False)
            result["attached_live_workbook"] = False

        if bool(getattr(wb, "ReadOnly", False)):
            raise RuntimeError("Workbook opened read-only; refusing to patch.")

        result["before"] = workbook_snapshot(wb)
        result["subtitle_patch"] = apply_dynamic_subtitle(wb)

        cm = wb.VBProject.VBComponents(MODULE).CodeModule
        original = cm.Lines(1, cm.CountOfLines)
        patched, stats = patch_code(original)
        result["patch_stats"] = stats

        if patched != original:
            cm.DeleteLines(1, cm.CountOfLines)
            cm.InsertLines(1, patched)

        final = cm.Lines(1, cm.CountOfLines)
        result["remaining_hardcoded_427"] = final.count("DateSerial(2026, 4, 27)")
        result["remaining_hardcoded_422"] = final.count("DateSerial(2026, 4, 22)")
        result["remaining_paint_true_calls"] = final.count("RefreshPaintOnly ws, True")
        result["has_header_based_paint"] = "Paint-only refresh must not move or resize the timeline." in final
        result["has_risk_bar_color"] = "Private Function RiskBarColorLong(" in final

        ws = wb.Worksheets("Gantt_BASE")
        before_header = str(ws.Cells(3, 11).Text)
        original_risk = ws.Range("G5").Value
        ws.Range("G5").Value = "CRITICAL"
        app.Run(f"'{wb.Name}'!modMIR_Gantt_Unified.MIR_OnChange", ws, ws.Range("G5"))
        after_header = str(ws.Cells(3, 11).Text)
        changed_color = int(ws.Range("K5").Interior.Color)
        ws.Range("G5").Value = original_risk
        app.Run(f"'{wb.Name}'!modMIR_Gantt_Unified.MIR_OnChange", ws, ws.Range("G5"))

        result["risk_edit_smoke"] = {
            "header_before": before_header,
            "header_after": after_header,
            "header_stable": before_header == after_header,
            "critical_bar_color_k5": changed_color,
        }

        app.Run(f"'{wb.Name}'!modMIR_Gantt_Unified.Init_Unified_System")
        result["init_run"] = "PASS"
        result["after"] = workbook_snapshot(wb)
        wb.Save()
        if not live_workbook:
            wb.Close(SaveChanges=True)
            wb = None
        result["save"] = "PASS"

        if live_workbook:
            result["reopen"] = "SKIPPED_live_workbook_left_open"
        else:
            reopened = app.Workbooks.Open(str(XLSM), UpdateLinks=0, ReadOnly=True, IgnoreReadOnlyRecommended=True, AddToMru=False)
            result["reopen"] = "PASS"
            result["reopen_snapshot"] = workbook_snapshot(reopened)
            reopened.Close(SaveChanges=False)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        if wb is not None:
            wb.Close(SaveChanges=False)
        raise
    finally:
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        if app is not None:
            for prop, value in app_state.items():
                try:
                    setattr(app, prop, value)
                except Exception:
                    pass
        if app is not None and not live_workbook:
            app.Quit()
        pythoncom.CoUninitialize()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
