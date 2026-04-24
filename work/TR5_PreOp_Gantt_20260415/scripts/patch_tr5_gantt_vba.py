"""
VBA patch for TR5_PreOp_Gantt workbook.
Fixes:
  1. PhaseColorLong: add TR5 phase names (EQUIP/MARINE/MZP_OPS/AGI_OPS/KF5-MMT/ALL)
  2. MIR_OnChange: replace hardcoded RefreshGanttExactRange dates with RefreshGantt ws, False
  3. MIR_OnChange Case COL_RISK: clear direct Interior.Color on G cell so CF can apply
"""
import pathlib, pythoncom, win32com.client as win32, gc, logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

XLSM = pathlib.Path(
    r"C:\tr_dash-main\output\spreadsheet\tr5_preparation_simulation\TR5_PreOp_Gantt_20260415_162140.xlsm"
)

# ── helpers ────────────────────────────────────────────────────────────────────

def replace_in_module(module_code: str, old: str, new: str, tag: str) -> tuple[str, bool]:
    # Normalize: try exact match, then CRLF-normalized, then LF-normalized
    for sep in ["\r\n", "\r", "\n"]:
        normalized_old = old.replace("\n", sep)
        normalized_new = new.replace("\n", sep)
        if normalized_old in module_code:
            log.info("  PATCH %-40s ... OK (sep=%r)", tag, sep)
            return module_code.replace(normalized_old, normalized_new, 1), True
    log.warning("  PATCH %-40s ... NOT FOUND", tag)
    # Show context clue
    key = old.strip().splitlines()[0][:60]
    idx = module_code.find(key[:30])
    if idx >= 0:
        log.warning("    (hint: found partial match near char %d)", idx)
    return module_code, False


# ── patch definitions ───────────────────────────────────────────────────────────

# Patch 1: PhaseColorLong – add TR5 phases before "Case Else"
P1_OLD = """\
        Case Else
            PhaseColorLong = HexToLong(C_AMBER)"""

P1_NEW = """\
        Case InStr(1, s, "MZP_OPS", vbTextCompare) > 0
            PhaseColorLong = HexToLong(C_PURPLE)
        Case InStr(1, s, "AGI_OPS", vbTextCompare) > 0
            PhaseColorLong = HexToLong(C_GREEN)
        Case InStr(1, s, "KF5", vbTextCompare) > 0
            PhaseColorLong = HexToLong(C_YELLOW)
        Case InStr(1, s, "EQUIP", vbTextCompare) > 0
            PhaseColorLong = HexToLong(C_BLUE)
        Case InStr(1, s, "MARINE", vbTextCompare) > 0
            PhaseColorLong = HexToLong("3BAFB8")
        Case InStr(1, s, "ALL", vbTextCompare) > 0
            PhaseColorLong = HexToLong(C_DIM)
        Case Else
            PhaseColorLong = HexToLong(C_AMBER)"""

# Patch 2: MIR_OnChange multi-cell paste path (line ~440)
P2_OLD = "            RefreshGanttExactRange ws, DateSerial(2026, 4, 27), DateSerial(2026, 5, 17), False\n            LogMsg \"ScheduleEdit\", \"Multi-cell schedule update count=\" & hit.CountLarge, ws.Name, hit.Row, hit.Column"

P2_NEW = "            RefreshGantt ws, False\n            LogMsg \"ScheduleEdit\", \"Multi-cell schedule update count=\" & hit.CountLarge, ws.Name, hit.Row, hit.Column"

# Patch 3: MIR_OnChange single-cell Case Else path (line ~508)
P3_OLD = "            RefreshGanttExactRange ws, DateSerial(2026, 4, 27), DateSerial(2026, 5, 17), False\n    End Select"

P3_NEW = "            RefreshGantt ws, False\n    End Select"

# Patch 4: Case COL_RISK – clear direct Interior.Color on G cell before CF shows
P4_OLD = """\
        Case COL_RISK
            If IsPaintModeActive() Then
                RefreshPaintOnly ws, True
            End If"""

P4_NEW = """\
        Case COL_RISK
            ws.Cells(hit.Row, COL_RISK).Interior.ColorIndex = xlColorIndexNone
            If IsPaintModeActive() Then
                RefreshPaintOnly ws, True
            End If"""


PATCHES = [
    (P1_OLD, P1_NEW, "PhaseColorLong TR5 phases"),
    (P2_OLD, P2_NEW, "MIR_OnChange multi-cell RefreshGantt"),
    (P3_OLD, P3_NEW, "MIR_OnChange single-cell RefreshGantt"),
    (P4_OLD, P4_NEW, "COL_RISK clear G Interior.Color"),
]


def main() -> None:
    if not XLSM.exists():
        raise FileNotFoundError(XLSM)

    pythoncom.CoInitialize()
    app = win32.DispatchEx("Excel.Application")
    app.Visible = False
    app.DisplayAlerts = False
    app.EnableEvents = False
    app.AutomationSecurity = 3  # msoAutomationSecurityForceDisable

    try:
        log.info("Opening: %s", XLSM.name)
        wb = app.Workbooks.Open(str(XLSM), UpdateLinks=0, ReadOnly=False)
        cm = wb.VBProject.VBComponents("modMIR_Gantt_Unified").CodeModule

        n_lines = cm.CountOfLines
        code = cm.Lines(1, n_lines)

        applied = 0
        for old, new, tag in PATCHES:
            code, ok = replace_in_module(code, old, new, tag)
            if ok:
                applied += 1

        if applied == 0:
            log.warning("No patches applied – file may already be patched or patterns changed.")
            wb.Close(False)
            return

        # Write patched code back
        cm.DeleteLines(1, cm.CountOfLines)
        cm.InsertLines(1, code)

        # Save
        wb.Save()
        log.info("Saved. %d/%d patches applied.", applied, len(PATCHES))

        # Keep workbook open and visible for user
        app.Visible = True
        app.EnableEvents = True
        wb.Activate()
        # Trigger Init to refresh everything
        try:
            app.Run("modMIR_Gantt_Unified.Init_Unified_System")
            log.info("Init_Unified_System executed.")
        except Exception as e:
            log.warning("Init run failed (not fatal): %s", e)

        log.info("Workbook open. Done.")

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
