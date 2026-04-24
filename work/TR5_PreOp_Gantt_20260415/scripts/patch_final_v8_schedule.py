from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
import time
from pathlib import Path

import pythoncom
import pywintypes
import win32com.client as win32


ROOT = Path(r"C:\tr_dash-main")
SOURCE_MD = ROOT / "work" / "TR5_Schedule_Final_v3.md"
TARGET_GLOB = "*TR5_PreOp_Gantt_20260415_162140_macrofixed_20260424_084432.xlsm"
SHEET = "Gantt_BASE"
MODULE = "modMIR_Gantt_Unified"

COL_UID = 1
COL_PHASE = 2
COL_TASK = 3
COL_START = 4
COL_END = 5
COL_DAYS = 6
COL_RISK = 7
COL_NOTE = 8
DATE_COL_START = 11
HEADER_ROW = 3
FIRST_ROW = 4
LAST_ROW = 42

PHASE_MAP = {
    "OFCO Customs and PTW": "DOC",
    "OFCO MMT Harbour Master Approval": "HM_GATE",
    "Mammoet Equipment Mobilization": "EQUIP",
    "KFS LCT Bushra": "MARINE",
    "ALL MZP Berth Ops": "MZP_OPS",
    "KFS MMT Voyage and AGI Ops": "AGI_OPS",
}

GROUP_TITLES = {
    "OFCO Customs and PTW": "> OFCO - Customs and PTW",
    "OFCO MMT Harbour Master Approval": "> OFCO+MMT - Harbour Master Approval",
    "Mammoet Equipment Mobilization": "> Mammoet - Equipment Mobilization",
    "KFS LCT Bushra": "> KFS - LCT Bushra",
    "ALL MZP Berth Ops": "> ALL - MZP Berth Ops",
    "KFS MMT Voyage and AGI Ops": "> KFS+MMT - Voyage and AGI Operations",
}

STABLE_SUBTITLE_FORMULA = (
    '=TEXT(TODAY(),"yyyy-mm-dd")'
    '&" | Source: "&IFERROR(MIR_SOURCE_LABEL,"TR5 schedule")'
    '&" | T+0="&TEXT(IFERROR(MIR_T_PLUS_ZERO,INDEX($3:$3,1,11)),"yyyy-mm-dd")'
    '&" | Load-out="&IFERROR(TEXT(LOOKUP(2,1/($A$1:$A$100="BD2"),$D$1:$D$100),"yyyy-mm-dd"),"")'
    '&" | AGI JD="&IFERROR(TEXT(LOOKUP(2,1/($A$1:$A$100="JDC"),$D$1:$D$100),"yyyy-mm-dd"),"")'
)

XL_UP = -4162
XL_TO_LEFT = -4159
C_AMBER = 4962536
ERROR_TERMS = ("#REF!", "#VALUE!", "#NAME?", "#N/A", "#DIV/0!")


def retry_com(label: str, func, attempts: int = 30, delay: float = 1.0):
    last_error = None
    for _ in range(attempts):
        try:
            return func()
        except pywintypes.com_error as exc:
            last_error = exc
            pythoncom.PumpWaitingMessages()
            time.sleep(delay)
    raise RuntimeError(f"{label} failed after {attempts} COM retries: {last_error}") from last_error


def wait_excel_ready(app, timeout: int = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if bool(app.Ready):
                return
        except pywintypes.com_error:
            pass
        pythoncom.PumpWaitingMessages()
        time.sleep(0.5)


def parse_source_tasks(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"```mermaid\s*gantt(.*?)```", text, re.S)
    if not match:
        raise RuntimeError(f"Mermaid Gantt block not found in {path}")

    tasks: list[dict[str, object]] = []
    section = ""
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("title ", "dateFormat ", "axisFormat ")):
            continue
        if line.startswith("section "):
            section = line[len("section ") :].strip()
            if section not in PHASE_MAP:
                raise RuntimeError(f"Unmapped section: {section}")
            continue

        task_match = re.match(r"^(.*?)\s*:(.*?),\s*(\d{4}-\d{2}-\d{2}),\s*(\d+)d\s*$", line)
        if not task_match:
            continue

        task = task_match.group(1).strip()
        attrs = [part.strip() for part in task_match.group(2).split(",")]
        start = dt.date.fromisoformat(task_match.group(3))
        duration = int(task_match.group(4))
        milestone = "milestone" in attrs or duration == 0
        critical = "crit" in attrs or "CRITICAL" in task.upper()
        code = ""
        for attr in reversed(attrs):
            if attr and attr not in {"crit", "milestone", "active", "done"}:
                code = attr
                break

        days = max(1, duration)
        end = start if duration == 0 else start + dt.timedelta(days=duration - 1)
        risk = "GATE" if milestone else "CRITICAL" if critical else "OK"
        tasks.append(
            {
                "section": section,
                "phase": PHASE_MAP[section],
                "task": task,
                "start": start,
                "end": end,
                "days": days,
                "risk": risk,
                "code": code,
                "milestone": milestone,
                "critical": critical,
            }
        )
    if len(tasks) != 33:
        raise RuntimeError(f"Expected 33 source tasks, parsed {len(tasks)}")
    return tasks


def group_source_rows(tasks: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen_sections: list[str] = []
    for task in tasks:
        section = str(task["section"])
        if section not in seen_sections:
            seen_sections.append(section)
            rows.append({"kind": "group", "section": section, "phase": GROUP_TITLES[section]})
        rows.append({"kind": "task", **task})
    if len(rows) != LAST_ROW - FIRST_ROW + 1:
        raise RuntimeError(f"Expected {LAST_ROW - FIRST_ROW + 1} Gantt rows, got {len(rows)}")
    return rows


def date_to_excel(value: dt.date) -> int:
    return (value - dt.date(1899, 12, 30)).days


def excel_value_to_date(value) -> dt.date:
    if isinstance(value, (int, float)):
        return dt.date(1899, 12, 30) + dt.timedelta(days=int(value))
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return dt.date(int(value.year), int(value.month), int(value.day))
    raise TypeError(f"Unsupported Excel date value: {value!r}")


def find_target_workbook(app):
    for i in range(1, app.Workbooks.Count + 1):
        wb = app.Workbooks.Item(i)
        if str(wb.Name).endswith(".xlsm") and "TR5_PreOp_Gantt" in str(wb.Name):
            return wb, True

    paths = [p for p in Path(r"C:\Users\SAMSUNG\Desktop").glob(TARGET_GLOB) if not p.name.startswith("~$")]
    if not paths:
        raise FileNotFoundError(f"Target workbook not found on Desktop: {TARGET_GLOB}")
    wb = app.Workbooks.Open(str(paths[0]), UpdateLinks=0, ReadOnly=False, IgnoreReadOnlyRecommended=True, AddToMru=False)
    return wb, False


def module_text(wb) -> str:
    cm = wb.VBProject.VBComponents(MODULE).CodeModule
    return str(cm.Lines(1, cm.CountOfLines))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def snapshot_existing_notes(ws) -> dict[str, str]:
    notes: dict[str, str] = {}
    for row in range(FIRST_ROW, LAST_ROW + 1):
        task = str(ws.Cells(row, COL_TASK).Text).strip()
        note = str(ws.Cells(row, COL_NOTE).Text).strip()
        if task and note:
            notes[task] = note
    return notes


def set_name(wb, name: str, refers_to: str, visible: bool = False) -> None:
    try:
        wb.Names(name).Delete()
    except Exception:
        pass
    new_name = wb.Names.Add(Name=name, RefersTo=refers_to)
    try:
        new_name.Visible = visible
    except Exception:
        pass


def update_uid_names(wb, task_rows: list[tuple[int, dict[str, object]]]) -> None:
    for idx, (row, item) in enumerate(task_rows, start=1):
        uid = f"{idx:04d}"
        start = item["start"]
        end = item["end"]
        days = int(item["days"])
        set_name(wb, f"MIR_UID_ROW_{uid}", f"={SHEET}!$A${row}", visible=False)
        set_name(wb, f"MIR_UID_ORIG_{uid}", f'="{start:%Y-%m-%d}|{end:%Y-%m-%d}|{days}"', visible=False)
    set_name(wb, "MIR_ORIG_TIMELINE_RANGE", '="2026-04-25|2026-05-17"', visible=False)
    set_name(wb, "MIR_SOURCE_LABEL", '="TR5_Schedule_Final_v3.md"', visible=False)
    set_name(wb, "MIR_T_PLUS_ZERO", "=DATE(2026,4,26)", visible=False)


def write_schedule(ws, rows: list[dict[str, object]], notes_by_task: dict[str, str]) -> list[tuple[int, dict[str, object]]]:
    ws.Unprotect()
    task_rows: list[tuple[int, dict[str, object]]] = []
    uid_counter = 1

    for offset, item in enumerate(rows):
        row = FIRST_ROW + offset
        ws.Range(ws.Cells(row, COL_UID), ws.Cells(row, COL_NOTE)).ClearContents()
        if item["kind"] == "group":
            ws.Cells(row, COL_PHASE).Value = str(item["phase"])
            continue

        uid = f"{uid_counter:04d}"
        uid_counter += 1
        task_code = str(item.get("code") or uid).upper()
        ws.Cells(row, COL_UID).Value = task_code
        ws.Cells(row, COL_PHASE).Value = str(item["phase"])
        ws.Cells(row, COL_TASK).Value = str(item["task"])
        ws.Cells(row, COL_START).Value = date_to_excel(item["start"])
        ws.Cells(row, COL_END).Value = date_to_excel(item["end"])
        ws.Cells(row, COL_DAYS).Value = int(item["days"])
        ws.Cells(row, COL_RISK).Value = str(item["risk"])
        ws.Cells(row, COL_NOTE).Value = notes_by_task.get(str(item["task"]), "")
        task_rows.append((row, item))

    ws.Range(ws.Cells(FIRST_ROW, COL_START), ws.Cells(LAST_ROW, COL_END)).NumberFormat = "yyyy-mm-dd"
    ws.Range(ws.Cells(FIRST_ROW, COL_DAYS), ws.Cells(LAST_ROW, COL_DAYS)).NumberFormat = "0"
    ws.Range("D2").Formula = STABLE_SUBTITLE_FORMULA
    return task_rows


def headers_snapshot(ws) -> dict[str, object]:
    last_col = int(ws.Cells(HEADER_ROW, ws.Columns.Count).End(XL_TO_LEFT).Column)
    values = [ws.Cells(HEADER_ROW, col).Value for col in range(DATE_COL_START, last_col + 1)]
    texts = [str(ws.Cells(HEADER_ROW, col).Text) for col in range(DATE_COL_START, last_col + 1)]
    dates = [excel_value_to_date(value) for value in values if value]
    return {
        "first": texts[0] if texts else "",
        "last": texts[-1] if texts else "",
        "count": len(texts),
        "continuous": all((dates[i + 1] - dates[i]).days == 1 for i in range(len(dates) - 1)),
        "starts_saturday": bool(dates and dates[0].weekday() == 5),
        "ends_sunday": bool(dates and dates[-1].weekday() == 6),
        "weekends": [
            str(ws.Cells(HEADER_ROW, col).Text)
            for col in range(DATE_COL_START, last_col + 1)
            if int(ws.Cells(HEADER_ROW, col).Font.Color) == C_AMBER
        ],
    }


def button_snapshot(ws) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name in ("mirBtnInit", "mirBtnReset", "mirBtnNotes"):
        btn = ws.Buttons(name)
        rows.append({"name": name, "caption": str(btn.Caption), "on_action": str(btn.OnAction)})
    return rows


def macro_entrypoints_present(code: str) -> dict[str, bool]:
    names = [
        "Init_Unified_System",
        "Reset_Schedule_To_Original",
        "Toggle_Notes_Action_Column",
        "MIR_OnChange",
        "MIR_OnSelectionChange",
        "RefreshGantt",
    ]
    return {name: (f"Sub {name}" in code or f"Function {name}" in code) for name in names}


def rows_from_range_value(value) -> list[list[object]]:
    if not isinstance(value, tuple):
        return [[value]]
    if not value:
        return []
    if not isinstance(value[0], tuple):
        return [list(value)]
    return [list(row) for row in value]


def validation_snapshot(wb, code_before_hash: str, label: str) -> dict[str, object]:
    ws = wb.Worksheets(SHEET)
    code = module_text(wb)
    milestones: dict[str, str] = {}
    required = {
        "G1 PTW Approved": "2026-04-29",
        "G2 HM Approval Received": "2026-05-04",
        "Bushra All Fast MZP Berth Secured": "2026-05-04",
        "Berth Day 2 RoRo Load-out Tidal1100": "2026-05-06",
        "TARGET AGI Jacking Down Complete": "2026-05-13",
    }
    for row in range(FIRST_ROW, LAST_ROW + 1):
        task = str(ws.Cells(row, COL_TASK).Text).strip()
        if task in required:
            milestones[task] = str(ws.Cells(row, COL_START).Text)

    errors: list[str] = []
    last_col = int(ws.Cells(HEADER_ROW, ws.Columns.Count).End(XL_TO_LEFT).Column)
    scan = ws.Range(ws.Cells(1, 1), ws.Cells(LAST_ROW, last_col))
    values = rows_from_range_value(scan.Value)
    formulas = rows_from_range_value(scan.Formula)
    for row_idx, value_row in enumerate(values, start=1):
        formula_row = formulas[row_idx - 1] if row_idx - 1 < len(formulas) else []
        for col_idx, value in enumerate(value_row, start=1):
            formula = formula_row[col_idx - 1] if col_idx - 1 < len(formula_row) else ""
            text = f"{value} {formula}"
            if any(term in text for term in ERROR_TERMS):
                errors.append(f"R{row_idx}C{col_idx}={text.strip()}")

    risk_validation = str(ws.Range("G5").Validation.Formula1)
    subtitle = str(ws.Range("D2").Text)
    subtitle_required = (
        "Source: TR5_Schedule_Final_v3.md",
        "T+0=2026-04-26",
        "Load-out=2026-05-06",
        "AGI JD=2026-05-13",
    )
    return {
        "label": label,
        "subtitle": subtitle,
        "subtitle_ok": all(fragment in subtitle for fragment in subtitle_required),
        "headers": headers_snapshot(ws),
        "buttons": button_snapshot(ws),
        "macro_entrypoints": macro_entrypoints_present(code),
        "vba_hash_unchanged": sha256_text(code) == code_before_hash,
        "milestones": milestones,
        "milestones_ok": all(milestones.get(task) == expected for task, expected in required.items()),
        "formula_errors": errors,
        "risk_validation": risk_validation,
        "risk_validation_ok": all(value in risk_validation for value in ("OK", "AMBER", "CRITICAL", "GATE")),
        "saved": bool(wb.Saved),
    }


def run() -> None:
    tasks = parse_source_tasks(SOURCE_MD)
    rows = group_source_rows(tasks)
    report: dict[str, object] = {
        "started": dt.datetime.now().isoformat(timespec="seconds"),
        "source": str(SOURCE_MD),
        "source_task_count": len(tasks),
    }

    pythoncom.CoInitialize()
    app = win32.GetActiveObject("Excel.Application")
    app_state = {
        "DisplayAlerts": app.DisplayAlerts,
        "EnableEvents": app.EnableEvents,
        "ScreenUpdating": app.ScreenUpdating,
    }
    app.Visible = True
    app.DisplayAlerts = False
    app.EnableEvents = False
    app.ScreenUpdating = False
    logs_dir = ROOT / "work" / "TR5_PreOp_Gantt_20260415" / "logs" / f"final_v8_patch_{dt.datetime.now():%Y%m%d_%H%M%S}"
    logs_dir.mkdir(parents=True, exist_ok=True)
    try:
        wb, was_open = find_target_workbook(app)
        wb.Activate()
        ws = wb.Worksheets(SHEET)
        ws.Activate()
        report["target"] = str(wb.FullName)
        report["attached_open_workbook"] = was_open

        if bool(getattr(wb, "ReadOnly", False)):
            raise RuntimeError("Workbook is read-only; refusing to patch.")

        backup = logs_dir / f"{Path(str(wb.FullName)).stem}.before_final_v8_patch.xlsm"
        wb.SaveCopyAs(str(backup))
        report["backup"] = str(backup)

        code_before = module_text(wb)
        code_before_hash = sha256_text(code_before)
        (logs_dir / "mod_before.bas").write_text(code_before, encoding="utf-8")
        wait_excel_ready(app)
        report["before"] = retry_com(
            "validation before patch",
            lambda: validation_snapshot(wb, code_before_hash, "before"),
        )

        notes_by_task = snapshot_existing_notes(ws)
        task_rows = write_schedule(ws, rows, notes_by_task)
        update_uid_names(wb, task_rows)

        app.EnableEvents = True
        app.ScreenUpdating = True
        retry_com("Init_Unified_System", lambda: app.Run(f"'{wb.Name}'!Init_Unified_System"))
        wait_excel_ready(app)
        report["validation_1_after_init"] = retry_com(
            "validation after init",
            lambda: validation_snapshot(wb, code_before_hash, "after_init"),
        )

        retry_com("RefreshGantt", lambda: app.Run(f"'{wb.Name}'!RefreshGantt", ws, False))
        wait_excel_ready(app)
        report["validation_2_after_refresh"] = retry_com(
            "validation after refresh",
            lambda: validation_snapshot(wb, code_before_hash, "after_refresh"),
        )

        retry_com("workbook save", lambda: wb.Save())
        wait_excel_ready(app)
        report["validation_3_after_save"] = retry_com(
            "validation after save",
            lambda: validation_snapshot(wb, code_before_hash, "after_save"),
        )

        code_after = module_text(wb)
        (logs_dir / "mod_after.bas").write_text(code_after, encoding="utf-8")
        report["vba_hash_before"] = code_before_hash
        report["vba_hash_after"] = sha256_text(code_after)
        report["vba_unchanged"] = report["vba_hash_before"] == report["vba_hash_after"]
        report["finished"] = dt.datetime.now().isoformat(timespec="seconds")
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        for prop, value in app_state.items():
            try:
                setattr(app, prop, value)
            except Exception:
                pass
        report_path = logs_dir / "validation_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    run()
