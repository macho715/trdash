"""
Patch: Add bidirectional cascade to TR5 Gantt workbook.
  1. Insert ShiftUpstream() after ShiftDownstream()
  2. Add ShiftUpstream call in HandleShiftMode COL_START case
"""
import pathlib, pythoncom, win32com.client as win32, gc, logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

XLSM = pathlib.Path(
    r"C:\tr_dash-main\work\TR5_PreOp_Gantt_20260415\excel\TR5_PreOp_Gantt_20260415_162140.xlsm"
)

# ── Patch 1: Insert ShiftUpstream right after End Sub of ShiftDownstream ───────
# Anchor: the exact closing line of ShiftDownstream
SHIFT_DOWN_END = """\
    LogMsg "ShiftDownstream", Err.Number & " - " & Err.Description, ws.Name, fromRow
End Sub"""

SHIFT_UP_FUNC = """
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
            ws.Cells(r, COL_END).Value2 = en
            SafeSetNumberFormat ws.Cells(r, COL_START), "yyyy-mm-dd"
            SafeSetNumberFormat ws.Cells(r, COL_END), "yyyy-mm-dd"
            UpdateDaysFromStartEnd ws, r
        End If
ContinueLoop:
    Next r

    Exit Sub
EH:
    LogMsg "ShiftUpstream", Err.Number & " - " & Err.Description, ws.Name, fromRow
End Sub"""

P1_OLD = SHIFT_DOWN_END
P1_NEW = SHIFT_DOWN_END + "\r\n" + SHIFT_UP_FUNC

# ── Patch 2: COL_START case — add ShiftUpstream call after ShiftDownstream ─────
P2_OLD = "                    If delta <> 0 Then ShiftDownstream ws, r, delta, False\r\n                End If\r\n            End If\r\n            UpdateDaysFromStartEnd ws, r"

P2_NEW = "                    If delta <> 0 Then ShiftDownstream ws, r, delta, False\r\n                    If delta <> 0 Then ShiftUpstream ws, r, delta\r\n                End If\r\n            End If\r\n            UpdateDaysFromStartEnd ws, r"


def patch(code: str, old: str, new: str, tag: str) -> tuple[str, bool]:
    for sep in ["\r\n", "\r", "\n"]:
        o = old.replace("\r\n", sep)
        n = new.replace("\r\n", sep)
        if o in code:
            log.info("  %-45s OK (sep=%r)", tag, sep)
            return code.replace(o, n, 1), True
    log.warning("  %-45s NOT FOUND", tag)
    # hint: show first 60 chars of first line
    hint = old.strip().splitlines()[0][:60]
    idx = code.find(hint[:30])
    if idx >= 0:
        log.warning("    (partial match near char %d: %r)", idx, code[idx:idx+80])
    return code, False


def main():
    if not XLSM.exists():
        raise FileNotFoundError(XLSM)

    pythoncom.CoInitialize()
    app = win32.DispatchEx("Excel.Application")
    app.Visible = False
    app.DisplayAlerts = False
    app.EnableEvents = False
    app.AutomationSecurity = 3

    try:
        log.info("Opening %s", XLSM.name)
        wb = app.Workbooks.Open(str(XLSM), UpdateLinks=0, ReadOnly=False)
        cm = wb.VBProject.VBComponents("modMIR_Gantt_Unified").CodeModule

        code = cm.Lines(1, cm.CountOfLines)

        applied = 0
        code, ok = patch(code, P1_OLD, P1_NEW, "Insert ShiftUpstream function")
        if ok: applied += 1

        code, ok = patch(code, P2_OLD, P2_NEW, "HandleShiftMode: add ShiftUpstream call")
        if ok: applied += 1

        if applied == 0:
            log.warning("No patches applied.")
            wb.Close(False)
            return

        cm.DeleteLines(1, cm.CountOfLines)
        cm.InsertLines(1, code)

        wb.Save()
        log.info("Saved. %d/2 patches applied.", applied)

        app.Visible = True
        app.EnableEvents = True
        wb.Activate()

        try:
            app.Run("modMIR_Gantt_Unified.Init_Unified_System")
            log.info("Init_Unified_System executed.")
        except Exception as e:
            log.warning("Init failed (not fatal): %s", e)

        log.info("Done — workbook is open.")

    except Exception:
        log.exception("Patch failed")
        try:
            app.Quit()
        except Exception:
            pass
        gc.collect()
        pythoncom.CoUninitialize()
        raise


if __name__ == "__main__":
    main()
