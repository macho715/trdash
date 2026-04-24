"""
patch_subtitle_and_timeline.py
Fix 1: Make subtitle row (Row 2) dynamic via Excel formula
Fix 2: Patch EnsureTimelineCovers to use xlShiftToRight + log actions,
       then force-run RefreshGantt to rebuild timeline covering all task dates
"""
import pythoncom, win32com.client as win32, gc, sys, time

XLSM = r'C:\tr_dash-main\work\TR5_PreOp_Gantt_20260415\excel\TR5_PreOp_Gantt_20260415_162140.xlsm'

# ── VBA patch: EnsureTimelineCovers improvements ─────────────────────────────
# 1) xlToRight → xlShiftToRight (defensive)
# 2) Add LogMsg calls so errors surface in LOG sheet
P_OLD = (
    "Private Sub EnsureTimelineCovers(ByVal ws As Worksheet, ByVal minD As Date, ByVal maxD As Date)\r\n"
    "    On Error GoTo EH\r\n"
    "    \r\n"
    "    Dim curFirst As Date, curLast As Date\r\n"
    "    Dim lastCol As Long\r\n"
    "    Dim addCols As Long\r\n"
    "    \r\n"
    "    curFirst = HeaderFirstDate(ws)\r\n"
    "    curLast = HeaderLastDate(ws)\r\n"
    "    \r\n"
    "    If IsDate(curFirst) Then\r\n"
    "        If minD < curFirst Then\r\n"
    "            addCols = DateDiff(\"d\", minD, curFirst)\r\n"
    "            ws.Columns(DATE_COL_START).Resize(, addCols).Insert Shift:=xlToRight\r\n"
    "        End If\r\n"
    "    End If\r\n"
    "    \r\n"
    "    curFirst = HeaderFirstDate(ws)\r\n"
    "    curLast = HeaderLastDate(ws)\r\n"
    "    lastCol = HeaderLastCol(ws)\r\n"
    "    \r\n"
    "    If IsDate(curLast) Then\r\n"
    "        If maxD > curLast Then\r\n"
    "            addCols = DateDiff(\"d\", curLast, maxD)\r\n"
    "            ws.Columns(lastCol + 1).Resize(, addCols).Insert Shift:=xlToRight\r\n"
    "        End If\r\n"
    "    End If\r\n"
    "    \r\n"
    "    Exit Sub\r\n"
    "EH:\r\n"
    "    LogMsg \"EnsureTimelineCovers\", Err.Number & \" - \" & Err.Description, ws.Name\r\n"
    "End Sub"
)

P_NEW = (
    "Private Sub EnsureTimelineCovers(ByVal ws As Worksheet, ByVal minD As Date, ByVal maxD As Date)\r\n"
    "    On Error GoTo EH\r\n"
    "    \r\n"
    "    Dim curFirst As Date, curLast As Date\r\n"
    "    Dim lastCol As Long\r\n"
    "    Dim addCols As Long\r\n"
    "    \r\n"
    "    curFirst = HeaderFirstDate(ws)\r\n"
    "    curLast = HeaderLastDate(ws)\r\n"
    "    \r\n"
    "    ' Extend LEFT: insert columns before DATE_COL_START\r\n"
    "    If IsDate(curFirst) Then\r\n"
    "        If minD < curFirst Then\r\n"
    "            addCols = DateDiff(\"d\", minD, curFirst)\r\n"
    "            LogMsg \"EnsureTimelineCovers\", \"LEFT expand \" & addCols & \" cols (\" & Format$(minD,\"yyyy-mm-dd\") & \")\", ws.Name\r\n"
    "            ws.Unprotect\r\n"
    "            ws.Columns(DATE_COL_START).Resize(, addCols).Insert Shift:=xlShiftToRight\r\n"
    "        End If\r\n"
    "    End If\r\n"
    "    \r\n"
    "    ' Re-read after possible left expansion\r\n"
    "    curFirst = HeaderFirstDate(ws)\r\n"
    "    curLast = HeaderLastDate(ws)\r\n"
    "    lastCol = HeaderLastCol(ws)\r\n"
    "    \r\n"
    "    ' Extend RIGHT: append columns after lastCol\r\n"
    "    If IsDate(curLast) Then\r\n"
    "        If maxD > curLast Then\r\n"
    "            addCols = DateDiff(\"d\", curLast, maxD)\r\n"
    "            LogMsg \"EnsureTimelineCovers\", \"RIGHT expand \" & addCols & \" cols (\" & Format$(maxD,\"yyyy-mm-dd\") & \")\", ws.Name\r\n"
    "            ws.Unprotect\r\n"
    "            ws.Columns(lastCol + 1).Resize(, addCols).Insert Shift:=xlShiftToRight\r\n"
    "        End If\r\n"
    "    End If\r\n"
    "    \r\n"
    "    Exit Sub\r\n"
    "EH:\r\n"
    "    LogMsg \"EnsureTimelineCovers\", \"ERROR \" & Err.Number & \" - \" & Err.Description, ws.Name\r\n"
    "End Sub"
)


def normalize(s: str) -> str:
    """Normalize line endings to CRLF."""
    return s.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")


def replace_in_module(code: str, old: str, new: str, label: str) -> str:
    old_n = normalize(old)
    new_n = normalize(new)
    code_n = normalize(code)
    if old_n not in code_n:
        print(f"  [WARN] {label}: NOT FOUND — skipping")
        return code
    result = code_n.replace(old_n, new_n, 1)
    print(f"  [OK]   {label}: patched")
    return result


pythoncom.CoInitialize()
app = win32.DispatchEx("Excel.Application")
app.Visible = False
app.DisplayAlerts = False
app.EnableEvents = False
app.AutomationSecurity = 3  # msoAutomationSecurityForceDisable

try:
    wb = app.Workbooks.Open(XLSM, UpdateLinks=0, ReadOnly=False)
    ws = wb.Sheets("Gantt_BASE")
    mod_name = "modMIR_Gantt_Unified"
    cm = wb.VBProject.VBComponents(mod_name).CodeModule
    n_lines = cm.CountOfLines
    code = cm.Lines(1, n_lines)

    # ── VBA patch ────────────────────────────────────────────────────────────
    print("Patching VBA EnsureTimelineCovers...")
    code = replace_in_module(code, P_OLD, P_NEW, "EnsureTimelineCovers")

    cm.DeleteLines(1, n_lines)
    cm.InsertLines(1, code)
    print(f"  VBA module updated ({cm.CountOfLines} lines)")

    # ── Fix 1: Subtitle dynamic formula ──────────────────────────────────────
    print("\nPatching subtitle (Row 2, Col 1)...")
    ws.Unprotect()
    # Formula: shows TODAY() + references D30 (Load-out start) + D42 (AGI JD target start)
    subtitle_formula = (
        '=TEXT(TODAY(),"yyyy-mm-dd")'
        '&" | Source: TR5_Pre-Op_Simulation_v2_20260430.md | T+0=2026-04-30 | Load-out="'
        '&TEXT(D30,"yyyy-mm-dd")'
        '&" | AGI JD="'
        '&TEXT(D42,"yyyy-mm-dd")'
    )
    ws.Cells(2, 1).Formula = subtitle_formula
    print(f"  Subtitle formula set → {ws.Cells(2, 1).Formula[:80]}")

    # ── Fix 2: Force RefreshGantt to rebuild timeline ─────────────────────────
    print("\nForce-running RefreshGantt to rebuild timeline headers...")
    app.EnableEvents = True  # allow macro execution
    app.ScreenUpdating = False
    try:
        app.Run(f"'{wb.Name}'!RefreshGantt", ws, False)
        print("  RefreshGantt completed")
        # Give Excel a moment to settle
        time.sleep(2)
        # Verify first header date
        from datetime import date
        first_hdr = ws.Cells(3, 11).Value  # HEADER_ROW=3, DATE_COL_START=11
        last_col_check = ws.Cells(3, 12).Value
        print(f"  K3 (col11) header = {first_hdr}")
        print(f"  L3 (col12) header = {last_col_check}")
    except Exception as e:
        print(f"  [WARN] RefreshGantt via app.Run failed: {e}")
        print("  Attempting direct VBA: Init_Unified_System")
        try:
            app.Run(f"'{wb.Name}'!Init_Unified_System")
            print("  Init_Unified_System completed")
        except Exception as e2:
            print(f"  [WARN] Init also failed: {e2}")
    finally:
        app.ScreenUpdating = True
        app.EnableEvents = False

    # ── Save ──────────────────────────────────────────────────────────────────
    wb.Save()
    print("\nWorkbook saved.")
    wb.Close(False)

finally:
    app.Quit()
    del app
    gc.collect()
    pythoncom.CoUninitialize()
    print("Done.")
