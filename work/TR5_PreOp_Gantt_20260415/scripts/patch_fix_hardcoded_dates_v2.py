"""
patch_fix_hardcoded_dates_v2.py
Connects to the ALREADY-RUNNING Excel instance (GetActiveObject).
Step A: Clears the Apr25/Apr26 column insertion via COM (not openpyxl)
Step B: Replaces all 6 RefreshGanttExactRange hardcoded calls with RefreshGantt ws, False
Saves without closing so the user can see the result.
"""
import pythoncom, win32com.client as win32, gc

XLSM_NAME = "TR5_PreOp_Gantt_20260415_162140.xlsm"
HEADER_ROW = 3
DATE_COL_START = 11   # column K

OLD_EXACT = "RefreshGanttExactRange ws, DateSerial(2026, 4, 27), DateSerial(2026, 5, 17), False"
NEW_GANTT = "RefreshGantt ws, False"

def normalize(s):
    return s.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")

pythoncom.CoInitialize()

# ── Connect to existing Excel OR open new hidden instance ─────────────────────
print("Connecting to Excel...")
app = None
wb  = None

try:
    app = win32.GetActiveObject("Excel.Application")
    print(f"  Connected to running Excel ({app.Version})")
    for w in app.Workbooks:
        if XLSM_NAME.lower() in w.Name.lower():
            wb = w
            print(f"  Found open workbook: {w.Name}")
            break
    if wb is None:
        print(f"  Workbook '{XLSM_NAME}' not open in active Excel — will open it")
except Exception as e:
    print(f"  GetActiveObject failed ({e}) — creating new hidden Excel instance")

if app is None:
    app = win32.DispatchEx("Excel.Application")
    app.Visible = False
    app.DisplayAlerts = False
    app.EnableEvents = False
    app.AutomationSecurity = 3

if wb is None:
    XLSM = r'C:\tr_dash-main\work\TR5_PreOp_Gantt_20260415\excel\TR5_PreOp_Gantt_20260415_162140.xlsm'
    wb = app.Workbooks.Open(XLSM, UpdateLinks=0, ReadOnly=False)
    print(f"  Opened: {wb.Name}")

ws = wb.Sheets("Gantt_BASE")
ws.Unprotect()
wb.Unprotect()

# ── Step A: Revert Apr25/Apr26 column insertion ───────────────────────────────
print("\nStep A: Checking header columns...")
k3_val = ws.Cells(HEADER_ROW, DATE_COL_START).Value
l3_val = ws.Cells(HEADER_ROW, DATE_COL_START + 1).Value
m3_val = ws.Cells(HEADER_ROW, DATE_COL_START + 2).Value
print(f"  K3={k3_val}  L3={l3_val}  M3={m3_val}")

def to_serial(v):
    """Get Excel date serial from cell value."""
    if v is None: return None
    if isinstance(v, (int, float)): return int(v)
    if hasattr(v, 'year'):
        import pywintypes
        try:
            from datetime import date
            d = date(v.year, v.month, v.day)
            # Excel serial: days since 1900-01-00 (+2 for Excel's leap year bug)
            return (d - date(1899, 12, 30)).days
        except: pass
    return None

k3_ser = to_serial(k3_val)
m3_ser = to_serial(m3_val)

APR25 = 46137; APR26 = 46138; APR27 = 46139

if k3_ser == APR25 or k3_ser == APR26:
    print(f"  K3={k3_ser} looks like Apr25/Apr26 — reverting 2 columns")
    # Delete columns K and L (2 columns at DATE_COL_START)
    ws.Columns(DATE_COL_START).Resize(1, 2).Delete(Shift=-4159)  # xlShiftToLeft = -4159
    k3_after = ws.Cells(HEADER_ROW, DATE_COL_START).Value
    print(f"  After delete: K3={k3_after}")
    print("  Column revert done.")
else:
    print(f"  K3 serial={k3_ser} — not Apr25/Apr26; no column deletion needed.")

# ── Step B: VBA patch ─────────────────────────────────────────────────────────
print("\nStep B: Patching VBA...")
app.EnableEvents = False
cm = wb.VBProject.VBComponents("modMIR_Gantt_Unified").CodeModule
n = cm.CountOfLines
raw = cm.Lines(1, n)

count_before = raw.count(OLD_EXACT)
print(f"  Found {count_before} occurrences of hardcoded DateSerial(2026,4,27)")

if count_before > 0:
    new_code = raw.replace(OLD_EXACT, NEW_GANTT)
    cm.DeleteLines(1, n)
    cm.InsertLines(1, new_code)
    final = cm.Lines(1, cm.CountOfLines)
    remaining = final.count(OLD_EXACT)
    print(f"  Patched {count_before} → remaining: {remaining}")
    print(f"  Module now {cm.CountOfLines} lines")
else:
    # Try with normalized line endings
    raw_n = normalize(raw)
    count_n = raw_n.count(OLD_EXACT)
    print(f"  After normalize: {count_n} occurrences")
    if count_n > 0:
        new_code = raw_n.replace(OLD_EXACT, NEW_GANTT)
        cm.DeleteLines(1, n)
        cm.InsertLines(1, new_code)
        print(f"  Patched (normalized). Module now {cm.CountOfLines} lines")
    else:
        # Show all RefreshGanttExactRange lines
        print("  [WARN] No match. Showing all RefreshGanttExactRange lines:")
        for i, ln in enumerate(raw.splitlines()):
            if "RefreshGanttExactRange" in ln:
                print(f"    {i+1}: {ln!r}")

# ── Save ──────────────────────────────────────────────────────────────────────
wb.Save()
print("\nWorkbook saved.")
print("Done. Click Init in Excel to see the updated timeline.")

pythoncom.CoUninitialize()
