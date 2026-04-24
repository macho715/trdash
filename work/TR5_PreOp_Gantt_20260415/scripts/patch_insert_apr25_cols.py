"""
patch_insert_apr25_cols.py  (v2 - idempotent)
- If K3 is empty → columns already inserted; just fill K3=Apr25, L3=Apr26
- If K3 is Apr27 → insert 2 cols then fill
- If K3 is Apr25 → already correct; skip
"""
import pythoncom, win32com.client as win32, gc, sys
from datetime import date, datetime, timedelta

XLSM = r'C:\tr_dash-main\work\TR5_PreOp_Gantt_20260415\excel\TR5_PreOp_Gantt_20260415_162140.xlsm'
HEADER_ROW = 3
DATE_COL_START = 11   # K = 11
NEW_FIRST = date(2026, 4, 25)
TARGET_FIRST = date(2026, 4, 27)

pythoncom.CoInitialize()
app = win32.DispatchEx("Excel.Application")
app.Visible = False; app.DisplayAlerts = False; app.EnableEvents = False
app.AutomationSecurity = 3

try:
    wb = app.Workbooks.Open(XLSM, UpdateLinks=0, ReadOnly=False)
    ws = wb.Sheets("Gantt_BASE")
    ws.Unprotect(); wb.Unprotect()

    k3_val = ws.Cells(HEADER_ROW, DATE_COL_START).Value
    print(f"K3 current value: {k3_val} (type: {type(k3_val).__name__})")

    # Determine the reference column that has the Apr 27 date format/width
    def to_date(v):
        if v is None:
            return None
        try:
            if hasattr(v, 'year'):
                return date(v.year, v.month, v.day)
        except Exception:
            pass
        return None

    k3_date = to_date(k3_val)

    if k3_date == NEW_FIRST:
        print("K3 already Apr 25 — nothing to insert.")
        ref_col_for_fmt = DATE_COL_START
        cols_to_fill = 2
        need_insert = False
    elif k3_date is None or k3_date == date(2026, 4, 25):
        # Blank: columns inserted in previous run, just fill
        print("K3 is blank — columns were already inserted; filling headers only.")
        ref_col_for_fmt = DATE_COL_START + 2  # the old Apr27 is now 2 cols to right
        cols_to_fill = 2
        need_insert = False
    elif k3_date == TARGET_FIRST:
        print("K3 is Apr 27 — inserting 2 columns then filling.")
        ref_col_for_fmt = DATE_COL_START
        cols_to_fill = 2
        need_insert = True
    else:
        print(f"[WARN] Unexpected K3 date: {k3_date} — aborting.")
        wb.Close(False); sys.exit(1)

    # Read format properties from reference column (the first real Apr27 header)
    ref = ws.Cells(HEADER_ROW, ref_col_for_fmt)
    col_width = ws.Columns(ref_col_for_fmt).ColumnWidth
    bg_color  = ref.Interior.Color
    font_color = ref.Font.Color
    font_size  = ref.Font.Size
    print(f"  Ref col {ref_col_for_fmt}: width={col_width:.1f}, bg={bg_color}, font_size={font_size}")

    if need_insert:
        for i in range(cols_to_fill):
            ws.Columns(DATE_COL_START).Insert(Shift=-4161)  # xlShiftToRight
        print(f"  Inserted {cols_to_fill} columns at K (col {DATE_COL_START})")

    # Fill K3 and L3 with Apr 25 and Apr 26
    for i in range(cols_to_fill):
        target_date = NEW_FIRST + timedelta(days=i)
        cell = ws.Cells(HEADER_ROW, DATE_COL_START + i)
        cell.Value = datetime(target_date.year, target_date.month, target_date.day)
        cell.NumberFormat = "mm-dd"
        ws.Columns(DATE_COL_START + i).ColumnWidth = col_width
        cell.Font.Bold = True
        cell.Font.Size = font_size if font_size else 7
        cell.HorizontalAlignment = -4108  # xlCenter
        cell.Interior.Color = bg_color
        cell.Font.Color = font_color
        print(f"  Set col {DATE_COL_START+i} = {target_date}")

    # Verify
    print("\nVerification (cols 11..15):")
    for c in range(DATE_COL_START, DATE_COL_START + 5):
        v = ws.Cells(HEADER_ROW, c).Value
        print(f"  col {c}: {v}")

    wb.Save()
    print("\nWorkbook saved.")
    wb.Close(False)

finally:
    app.Quit(); del app; gc.collect(); pythoncom.CoUninitialize()
    print("Done.")
