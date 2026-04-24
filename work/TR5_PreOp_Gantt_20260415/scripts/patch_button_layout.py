from __future__ import annotations

import datetime as dt
import json
import re
import shutil
from pathlib import Path

import pythoncom
import win32com.client as win32


ROOT = Path(r"C:\tr_dash-main")
DEFAULT_XLSM = ROOT / "work" / "TR5_PreOp_Gantt_20260415" / "excel" / "TR5_PreOp_Gantt_20260415_162140.xlsm"
MODULE = "modMIR_Gantt_Unified"
SHEET = "Gantt_BASE"

STABLE_SUBTITLE_HELPER = '''Private Function StableSubtitleFormula() As String
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
    Dim subtitleFormula As String
    Dim titleStartCol As Long

    titleStartCol = COL_START
    If endCol < titleStartCol Then endCol = titleStartCol

    titleValue = ws.Cells(1, titleStartCol).Value
    If Len(CStr(titleValue)) = 0 Then titleValue = ws.Cells(1, 1).Value

    subtitleFormula = StableSubtitleFormula()

    On Error Resume Next
    ws.Range(ws.Cells(1, 1), ws.Cells(1, ws.Columns.Count)).UnMerge
    ws.Range(ws.Cells(2, 1), ws.Cells(2, ws.Columns.Count)).UnMerge
    On Error GoTo EH

    ws.Range(ws.Cells(1, 1), ws.Cells(2, titleStartCol - 1)).ClearContents
    ws.Range(ws.Cells(1, titleStartCol), ws.Cells(1, endCol)).Merge
    ws.Range(ws.Cells(2, titleStartCol), ws.Cells(2, endCol)).Merge
    ws.Cells(1, titleStartCol).Value = titleValue
    ws.Cells(2, titleStartCol).Formula = subtitleFormula
    Exit Sub
EH:
    LogMsg "FixHeaderMerges", Err.Number & " - " & Err.Description, ws.Name
End Sub'''


NEW_ENSURE_BUTTONS = '''Private Sub EnsureGanttActionButtons(ByVal ws As Worksheet)
    On Error GoTo EH
    Dim topPos As Double
    Dim btnHeight As Double
    Dim btnGap As Double
    Dim leftBase As Double, rightEdge As Double, availableWidth As Double
    Dim initLeft As Double, resetLeft As Double, notesLeft As Double
    Dim initWidth As Double, resetWidth As Double, notesWidth As Double
    Dim totalWidth As Double

    If ws Is Nothing Then Exit Sub
    If Not IsGanttSheet(ws) Then Exit Sub

    DeleteManagedButtons ws

    topPos = ws.Rows(1).Top + 4
    btnHeight = 16
    btnGap = 4
    leftBase = ws.Cells(1, COL_PHASE).Left + 4
    rightEdge = ws.Cells(1, COL_START).Left - 4
    availableWidth = rightEdge - leftBase

    initWidth = 64
    resetWidth = 72
    notesWidth = 90
    totalWidth = initWidth + resetWidth + notesWidth + (btnGap * 2)

    If totalWidth > availableWidth Then
        notesWidth = availableWidth - initWidth - resetWidth - (btnGap * 2)
        If notesWidth < 78 Then
            notesWidth = 78
            resetWidth = availableWidth - initWidth - notesWidth - (btnGap * 2)
            If resetWidth < 58 Then resetWidth = 58
        End If
    End If

    initLeft = leftBase
    resetLeft = initLeft + initWidth + btnGap
    notesLeft = resetLeft + resetWidth + btnGap

    UpsertActionButton ws, BTN_INIT_NAME, "Init", "Init_Unified_System", initLeft, topPos, initWidth, btnHeight, C_BLUE
    UpsertActionButton ws, BTN_RESET_NAME, "Reset", "Reset_Schedule_To_Original", resetLeft, topPos, resetWidth, btnHeight, C_RED
    UpsertActionButton ws, BTN_NOTES_NAME, CurrentNotesButtonCaption(ws), "Toggle_Notes_Action_Column", notesLeft, topPos, notesWidth, btnHeight, C_AMBER
    Exit Sub
EH:
    LogMsg "EnsureGanttActionButtons", Err.Number & " - " & Err.Description, ws.Name
End Sub'''


NEW_UPSERT_ONACTION_LINE = '''        .OnAction = "'" & ThisWorkbook.Name & "'!" & macroName'''


def normalize_vba(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def denormalize_vba(text: str) -> str:
    return text.replace("\n", "\r\n")


def replace_sub(text: str, name: str, replacement: str) -> tuple[str, int]:
    pattern = re.compile(rf"Private Sub {re.escape(name)}\([^)]*\)\n.*?\nEnd Sub", re.S)
    new_text, count = pattern.subn(normalize_vba(replacement), text, count=1)
    if count != 1:
        raise RuntimeError(f"{name} procedure not found or not uniquely replaceable.")
    return new_text, count


def patch_code(code: str) -> tuple[str, dict[str, int]]:
    text = normalize_vba(code)
    stats: dict[str, int] = {}

    if "Private Function StableSubtitleFormula(" not in text:
        marker = "Private Sub FixHeaderMerges("
        if marker not in text:
            raise RuntimeError("FixHeaderMerges marker not found.")
        text = text.replace(marker, normalize_vba(STABLE_SUBTITLE_HELPER) + marker, 1)
        stats["stable_subtitle_helper_added"] = 1
    else:
        stats["stable_subtitle_helper_added"] = 0

    text, stats["fix_header_merges_replaced"] = replace_sub(text, "FixHeaderMerges", NEW_FIX_HEADER_MERGES)
    text, stats["ensure_buttons_replaced"] = replace_sub(text, "EnsureGanttActionButtons", NEW_ENSURE_BUTTONS)

    old_line = '        .OnAction = macroName'
    if old_line in text:
        text = text.replace(old_line, normalize_vba(NEW_UPSERT_ONACTION_LINE), 1)
        stats["onaction_localized"] = 1
    elif normalize_vba(NEW_UPSERT_ONACTION_LINE) in text:
        stats["onaction_localized"] = 0
    else:
        raise RuntimeError("UpsertActionButton OnAction assignment not found.")

    return denormalize_vba(text), stats


def find_target_workbook(app, requested: Path | None):
    if requested is not None:
        requested_text = str(requested).lower()
        for i in range(1, app.Workbooks.Count + 1):
            candidate = app.Workbooks(i)
            if str(candidate.FullName).lower() == requested_text:
                return candidate, True
        return None, False

    try:
        active = app.ActiveWorkbook
        if active is not None and "TR5_PreOp_Gantt" in str(active.Name):
            active.Worksheets(SHEET)
            return active, True
    except Exception:
        pass

    for i in range(1, app.Workbooks.Count + 1):
        candidate = app.Workbooks(i)
        try:
            candidate.Worksheets(SHEET)
            if "TR5_PreOp_Gantt" in str(candidate.Name):
                return candidate, True
        except Exception:
            continue
    return None, False


def button_snapshot(ws) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name in ("mirBtnInit", "mirBtnReset", "mirBtnNotes"):
        try:
            btn = ws.Buttons(name)
            rows.append(
                {
                    "name": name,
                    "caption": str(btn.Caption),
                    "on_action": str(btn.OnAction),
                    "left": round(float(btn.Left), 2),
                    "top": round(float(btn.Top), 2),
                    "width": round(float(btn.Width), 2),
                    "height": round(float(btn.Height), 2),
                }
            )
        except Exception as exc:
            rows.append({"name": name, "error": str(exc)})
    return rows


def sheet_snapshot(wb) -> dict[str, object]:
    ws = wb.Worksheets(SHEET)
    return {
        "title_d1": str(ws.Range("D1").Text),
        "subtitle_d2": str(ws.Range("D2").Text),
        "title_a1": str(ws.Range("A1").Text),
        "subtitle_a2": str(ws.Range("A2").Text),
        "title_merge": str(ws.Range("D1").MergeArea.Address).replace("$", ""),
        "subtitle_merge": str(ws.Range("D2").MergeArea.Address).replace("$", ""),
        "b_left": round(float(ws.Cells(1, 2).Left), 2),
        "d_left": round(float(ws.Cells(1, 4).Left), 2),
        "buttons": button_snapshot(ws),
    }


def apply_header_layout(wb) -> None:
    ws = wb.Worksheets(SHEET)
    last_col = ws.Cells(3, ws.Columns.Count).End(-4159).Column  # xlToLeft
    title = ws.Range("D1").Value or ws.Range("A1").Value
    subtitle_formula = ws.Range("D2").Formula or ws.Range("A2").Formula

    ws.Unprotect()
    ws.Range(ws.Cells(1, 1), ws.Cells(2, ws.Columns.Count)).UnMerge()
    ws.Range(ws.Cells(1, 1), ws.Cells(2, 3)).ClearContents()
    ws.Range(ws.Cells(1, 4), ws.Cells(1, last_col)).Merge()
    ws.Range(ws.Cells(2, 4), ws.Cells(2, last_col)).Merge()
    ws.Range("D1").Value = title
    ws.Range("D2").Formula = subtitle_formula


def run() -> None:
    requested = DEFAULT_XLSM if DEFAULT_XLSM.exists() else None
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = ROOT / "work" / "TR5_PreOp_Gantt_20260415" / "logs" / f"button_layout_patch_{stamp}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    pythoncom.CoInitialize()
    app = None
    wb = None
    live_workbook = False
    app_state: dict[str, object] = {}
    result: dict[str, object] = {"requested": str(requested) if requested else None}
    try:
        try:
            app = win32.GetActiveObject("Excel.Application")
            wb, live_workbook = find_target_workbook(app, None)
        except Exception:
            app = None

        if app is None:
            app = win32.DispatchEx("Excel.Application")
            app.Visible = False

        for prop in ("DisplayAlerts", "EnableEvents", "ScreenUpdating"):
            try:
                app_state[prop] = getattr(app, prop)
            except Exception:
                pass

        app.DisplayAlerts = False
        app.EnableEvents = False
        app.AutomationSecurity = 1

        if wb is None:
            if requested is None:
                raise FileNotFoundError(DEFAULT_XLSM)
            backup_dir = report_path.parent / f"button_layout_patch_{stamp}"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / f"{requested.stem}.before_button_layout{requested.suffix}"
            shutil.copy2(requested, backup)
            result["backup"] = str(backup)
            wb = app.Workbooks.Open(str(requested), UpdateLinks=0, ReadOnly=False, IgnoreReadOnlyRecommended=True, AddToMru=False)
            live_workbook = False

        result["target"] = str(wb.FullName)
        result["attached_live_workbook"] = live_workbook
        result["before"] = sheet_snapshot(wb)

        if bool(getattr(wb, "ReadOnly", False)):
            raise RuntimeError("Workbook opened read-only; refusing to patch.")

        cm = wb.VBProject.VBComponents(MODULE).CodeModule
        original = cm.Lines(1, cm.CountOfLines)
        patched, stats = patch_code(original)
        result["patch_stats"] = stats
        if patched != original:
            cm.DeleteLines(1, cm.CountOfLines)
            cm.InsertLines(1, patched)

        apply_header_layout(wb)
        app.Run(f"'{wb.Name}'!Init_Unified_System")
        result["init_run"] = "PASS"
        result["after_init"] = sheet_snapshot(wb)

        current_notes_hidden = bool(wb.Worksheets(SHEET).Columns(8).Hidden)
        app.Run(f"'{wb.Name}'!Toggle_Notes_Action_Column")
        app.Run(f"'{wb.Name}'!Toggle_Notes_Action_Column")
        wb.Worksheets(SHEET).Columns(8).Hidden = current_notes_hidden
        result["toggle_notes_roundtrip"] = "PASS"
        result["after_toggle_roundtrip"] = sheet_snapshot(wb)

        wb.Save()
        result["save"] = "PASS"

        if live_workbook:
            result["reopen"] = "SKIPPED_live_workbook_left_open"
        else:
            wb.Close(SaveChanges=True)
            wb = None
            reopened = app.Workbooks.Open(str(result["target"]), UpdateLinks=0, ReadOnly=True, IgnoreReadOnlyRecommended=True, AddToMru=False)
            result["reopen"] = "PASS"
            result["reopen_snapshot"] = sheet_snapshot(reopened)
            reopened.Close(SaveChanges=False)
    finally:
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        if app is not None:
            for prop, value in app_state.items():
                try:
                    setattr(app, prop, value)
                except Exception:
                    pass
            if not live_workbook:
                try:
                    app.Quit()
                except Exception:
                    pass
        pythoncom.CoUninitialize()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
