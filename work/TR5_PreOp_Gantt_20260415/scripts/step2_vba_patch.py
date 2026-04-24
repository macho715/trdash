"""
step2_vba_patch.py  — Excel 완전히 닫힌 후 실행
COM으로 VBA 6곳 패치: RefreshGanttExactRange -> RefreshGantt ws, False
- Visible=True: 숨겨진 대화상자 방지
- AutomationSecurity=1: 매크로 허용 (VBProject 접근 필요)
- Unblock-File 먼저 실행 권장 (MOTW 제거)
"""
import pythoncom, win32com.client as win32, gc, sys

XLSM = r'C:\tr_dash-main\work\TR5_PreOp_Gantt_20260415\excel\TR5_PreOp_Gantt_20260415_162140.xlsm'
OLD = "RefreshGanttExactRange ws, DateSerial(2026, 4, 27), DateSerial(2026, 5, 17), False"
NEW = "RefreshGantt ws, False"

print("Starting Excel COM...", flush=True)
pythoncom.CoInitialize()
app = win32.DispatchEx("Excel.Application")
app.Visible = True
app.DisplayAlerts = False
app.EnableEvents = False
app.AutomationSecurity = 1
print(f"Excel {app.Version} ready.", flush=True)

try:
    print(f"Opening workbook...", flush=True)
    wb = app.Workbooks.Open(XLSM, UpdateLinks=0, ReadOnly=False)
    print(f"Opened: {wb.Name}", flush=True)

    cm = wb.VBProject.VBComponents("modMIR_Gantt_Unified").CodeModule
    n = cm.CountOfLines
    code = cm.Lines(1, n)
    count = code.count(OLD)
    print(f"Hardcoded occurrences found: {count}", flush=True)

    if count == 0:
        print("[WARN] Pattern not found. All RefreshGanttExactRange lines:", flush=True)
        for i, ln in enumerate(code.splitlines()):
            if "RefreshGanttExactRange" in ln:
                print(f"  {i+1}: {ln!r}", flush=True)
    else:
        new_code = code.replace(OLD, NEW)
        remaining = new_code.count(OLD)
        cm.DeleteLines(1, n)
        cm.InsertLines(1, new_code)
        print(f"Replaced {count} -> remaining {remaining}. Module: {cm.CountOfLines} lines.", flush=True)

    wb.Save()
    print("Saved.", flush=True)
    app.Visible = False
    wb.Close(False)
    print("Workbook closed.", flush=True)

except Exception as e:
    print(f"ERROR: {e}", flush=True)
finally:
    try:
        app.Quit()
    except Exception:
        pass
    del app
    gc.collect()
    pythoncom.CoUninitialize()

print("Step 2 done.", flush=True)
