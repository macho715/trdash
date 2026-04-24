from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import pythoncom
import win32com.client as win32


ROOT = Path(r"C:\tr_dash-main")
SHEET = "Gantt_BASE"
MODULE = "modMIR_Gantt_Unified"
DATE_COL_START = 11
HEADER_ROW = 3
C_AMBER = 4962536


STABLE_SUBTITLE_FORMULA = (
    '=TEXT(TODAY(),"yyyy-mm-dd")'
    '&" | Source: "&IFERROR(MIR_SOURCE_LABEL,"TR5 schedule")'
    '&" | T+0="&TEXT(IFERROR(MIR_T_PLUS_ZERO,INDEX($3:$3,1,11)),"yyyy-mm-dd")'
    '&" | Load-out="&IFERROR(TEXT(LOOKUP(2,1/($A$1:$A$100="BD2"),$D$1:$D$100),"yyyy-mm-dd"),"")'
    '&" | AGI JD="&IFERROR(TEXT(LOOKUP(2,1/($A$1:$A$100="JDC"),$D$1:$D$100),"yyyy-mm-dd"),"")'
)


WEEKEND_HELPERS = '''Private Sub ExpandTimelineToWeekendBounds(ByRef firstD As Date, ByRef lastD As Date)
    Dim startOffset As Long
    Dim endOffset As Long

    If lastD < firstD Then
        Dim tmpD As Date
        tmpD = firstD
        firstD = lastD
        lastD = tmpD
    End If

    ' Keep the visible timeline on complete Sat-Sun calendar boundaries.
    startOffset = (Weekday(firstD, vbMonday) + 1) Mod 7
    endOffset = 7 - Weekday(lastD, vbMonday)

    If startOffset > 0 Then firstD = DateAdd("d", -startOffset, firstD)
    If endOffset > 0 Then lastD = DateAdd("d", endOffset, lastD)
End Sub

Private Function StableSubtitleFormula() As String
    StableSubtitleFormula = "=TEXT(TODAY(),""yyyy-mm-dd"")" & _
        "&"" | Source: ""&IFERROR(MIR_SOURCE_LABEL,""TR5 schedule"")" & _
        "&"" | T+0=""&TEXT(IFERROR(MIR_T_PLUS_ZERO,INDEX($3:$3,1,11)),""yyyy-mm-dd"")" & _
        "&"" | Load-out=""&IFERROR(TEXT(LOOKUP(2,1/($A$1:$A$100=""BD2""),$D$1:$D$100),""yyyy-mm-dd""),"""")" & _
        "&"" | AGI JD=""&IFERROR(TEXT(LOOKUP(2,1/($A$1:$A$100=""JDC""),$D$1:$D$100),""yyyy-mm-dd""),"""")"
End Function

'''


NEW_FIX_HEADER_MERGES = '''Private Sub FixHeaderMerges(ByVal ws As Worksheet, ByVal endCol As Long)
    On Error GoTo EH
    Dim titleValue As Variant
    Dim titleStartCol As Long

    titleStartCol = COL_START
    If endCol < titleStartCol Then endCol = titleStartCol

    titleValue = ws.Cells(1, titleStartCol).Value
    If Len(CStr(titleValue)) = 0 Then titleValue = ws.Cells(1, 1).Value

    On Error Resume Next
    ws.Range(ws.Cells(1, 1), ws.Cells(1, ws.Columns.Count)).UnMerge
    ws.Range(ws.Cells(2, 1), ws.Cells(2, ws.Columns.Count)).UnMerge
    On Error GoTo EH

    ws.Range(ws.Cells(1, 1), ws.Cells(2, titleStartCol - 1)).ClearContents
    ws.Range(ws.Cells(1, titleStartCol), ws.Cells(1, endCol)).Merge
    ws.Range(ws.Cells(2, titleStartCol), ws.Cells(2, endCol)).Merge
    ws.Cells(1, titleStartCol).Value = titleValue
    ws.Cells(2, titleStartCol).Formula = StableSubtitleFormula()
    Exit Sub
EH:
    LogMsg "FixHeaderMerges", Err.Number & " - " & Err.Description, ws.Name
End Sub'''


def normalize_vba(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def denormalize_vba(text: str) -> str:
    return text.replace("\n", "\r\n")


def replace_sub(text: str, name: str, replacement: str) -> tuple[str, int]:
    pattern = re.compile(rf"Private Sub {re.escape(name)}\([^)]*\)\n.*?\nEnd Sub", re.S)
    text, count = pattern.subn(normalize_vba(replacement), text, count=1)
    if count != 1:
        raise RuntimeError(f"{name} procedure not found or not uniquely replaceable.")
    return text, count


def replace_function(text: str, name: str, replacement: str) -> tuple[str, int]:
    pattern = re.compile(rf"Private Function {re.escape(name)}\([^)]*\).*?\nEnd Function", re.S)
    text, count = pattern.subn(normalize_vba(replacement), text, count=1)
    if count != 1:
        raise RuntimeError(f"{name} function not found or not uniquely replaceable.")
    return text, count


def patch_code(code: str) -> tuple[str, dict[str, int]]:
    text = normalize_vba(code)
    stats: dict[str, int] = {}

    if "Private Sub ExpandTimelineToWeekendBounds(" not in text:
        marker = "Private Sub RefreshGantt(ByVal ws As Worksheet, ByVal includeToday As Boolean"
        if marker not in text:
            raise RuntimeError("RefreshGantt marker not found.")
        text = text.replace(marker, normalize_vba(WEEKEND_HELPERS) + marker, 1)
        stats["weekend_helpers_added"] = 1
    else:
        stats["weekend_helpers_added"] = 0

    stable_function = WEEKEND_HELPERS.split("Private Function StableSubtitleFormula()", 1)[1]
    stable_function = "Private Function StableSubtitleFormula()" + stable_function
    text, stats["stable_subtitle_function_replaced"] = replace_function(text, "StableSubtitleFormula", stable_function)

    refresh_marker = '''    If includeToday Then
        If Date < minD Then minD = Date
        If Date > maxD Then maxD = Date
    End If
    
    EnsureTimelineCovers ws, minD, maxD'''
    refresh_repl = '''    If includeToday Then
        If Date < minD Then minD = Date
        If Date > maxD Then maxD = Date
    End If
    ExpandTimelineToWeekendBounds minD, maxD
    
    EnsureTimelineCovers ws, minD, maxD'''
    if normalize_vba(refresh_marker) in text and "ExpandTimelineToWeekendBounds minD, maxD" not in text:
        text = text.replace(normalize_vba(refresh_marker), normalize_vba(refresh_repl), 1)
        stats["refresh_weekend_bounds_added"] = 1
    else:
        stats["refresh_weekend_bounds_added"] = 0

    exact_marker = '''    If includeToday Then
        If Date < firstD Then firstD = Date
        If Date > lastD Then lastD = Date
    End If
    
    EnsureTimelineMatches ws, firstD, lastD'''
    exact_repl = '''    If includeToday Then
        If Date < firstD Then firstD = Date
        If Date > lastD Then lastD = Date
    End If
    ExpandTimelineToWeekendBounds firstD, lastD
    
    EnsureTimelineMatches ws, firstD, lastD'''
    if normalize_vba(exact_marker) in text and "ExpandTimelineToWeekendBounds firstD, lastD" not in text:
        text = text.replace(normalize_vba(exact_marker), normalize_vba(exact_repl), 1)
        stats["exact_weekend_bounds_added"] = 1
    else:
        stats["exact_weekend_bounds_added"] = 0

    text, stats["fix_header_merges_replaced"] = replace_sub(text, "FixHeaderMerges", NEW_FIX_HEADER_MERGES)
    return denormalize_vba(text), stats


def find_target_workbook(app):
    for i in range(1, app.Workbooks.Count + 1):
        wb = app.Workbooks.Item(i)
        if "TR5_PreOp_Gantt" in str(wb.Name):
            return wb
    paths = [
        p for p in Path(r"C:\Users\SAMSUNG\Desktop").glob("*TR5_PreOp_Gantt_20260415_162140_macrofixed_20260424_084432.xlsm")
        if not p.name.startswith("~$")
    ]
    if not paths:
        raise FileNotFoundError("TR5 macrofixed workbook not found on Desktop.")
    return app.Workbooks.Open(str(paths[0]), UpdateLinks=0, ReadOnly=False, IgnoreReadOnlyRecommended=True, AddToMru=False)


def excel_date_number(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if hasattr(value, "timestamp"):
        return float((value.date() - dt.date(1899, 12, 30)).days)
    raise TypeError(f"Unsupported date value: {value!r}")


def validation_snapshot(wb, label: str) -> dict[str, object]:
    ws = wb.Worksheets(SHEET)
    last_col = int(ws.Cells(HEADER_ROW, ws.Columns.Count).End(-4159).Column)
    values = [excel_date_number(ws.Cells(HEADER_ROW, c).Value) for c in range(DATE_COL_START, last_col + 1)]
    texts = [str(ws.Cells(HEADER_ROW, c).Text) for c in range(DATE_COL_START, last_col + 1)]
    deltas = [round(values[i + 1] - values[i], 6) for i in range(len(values) - 1)]
    weekend_texts = [
        str(ws.Cells(HEADER_ROW, c).Text)
        for c in range(DATE_COL_START, last_col + 1)
        if int(ws.Cells(HEADER_ROW, c).Font.Color) == C_AMBER
    ]
    return {
        "label": label,
        "first": texts[0],
        "last": texts[-1],
        "count": len(texts),
        "continuous": all(delta == 1 for delta in deltas),
        "starts_saturday": dt.date(1899, 12, 30).toordinal() + int(values[0]) and dt.date.fromordinal(dt.date(1899, 12, 30).toordinal() + int(values[0])).weekday() == 5,
        "ends_sunday": dt.date.fromordinal(dt.date(1899, 12, 30).toordinal() + int(values[-1])).weekday() == 6,
        "weekends": weekend_texts,
        "subtitle_text": str(ws.Range("D2").Text),
        "subtitle_formula": str(ws.Range("D2").Formula),
        "subtitle_has_ref_error": "#REF!" in str(ws.Range("D2").Text) or "#REF!" in str(ws.Range("D2").Formula),
        "merge_d1": str(ws.Range("D1").MergeArea.Address).replace("$", ""),
        "merge_d2": str(ws.Range("D2").MergeArea.Address).replace("$", ""),
    }


def run() -> None:
    pythoncom.CoInitialize()
    report: dict[str, object] = {"started": dt.datetime.now().isoformat(timespec="seconds")}
    app = win32.GetActiveObject("Excel.Application")
    app.Visible = True
    wb = find_target_workbook(app)
    ws = wb.Worksheets(SHEET)
    wb.Activate()
    ws.Activate()

    report["target"] = str(wb.FullName)
    report["before"] = validation_snapshot(wb, "before")
    try:
        wb.Names("MIR_T_PLUS_ZERO").Delete()
    except Exception:
        pass
    t0_name = wb.Names.Add(Name="MIR_T_PLUS_ZERO", RefersTo="=DATE(2026,4,22)")
    try:
        t0_name.Visible = False
    except Exception:
        pass

    cm = wb.VBProject.VBComponents(MODULE).CodeModule
    original = cm.Lines(1, cm.CountOfLines)
    patched, stats = patch_code(original)
    report["patch_stats"] = stats
    if patched != original:
        cm.DeleteLines(1, cm.CountOfLines)
        cm.InsertLines(1, patched)

    ws.Unprotect()
    ws.Range("D2").Formula = STABLE_SUBTITLE_FORMULA
    app.Run(f"'{wb.Name}'!Init_Unified_System")
    report["validation_1_after_init"] = validation_snapshot(wb, "after_init")

    app.Run(f"'{wb.Name}'!RefreshGantt", ws, False)
    report["validation_2_after_refresh"] = validation_snapshot(wb, "after_refresh")

    wb.Save()
    report["saved"] = bool(wb.Saved)
    report["validation_3_after_save"] = validation_snapshot(wb, "after_save")
    report["finished"] = dt.datetime.now().isoformat(timespec="seconds")

    out = ROOT / "work" / "TR5_PreOp_Gantt_20260415" / "logs" / f"weekend_date_array_patch_{dt.datetime.now():%Y%m%d_%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    pythoncom.CoUninitialize()


if __name__ == "__main__":
    run()
