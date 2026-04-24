Option Explicit

' ============================================================
' MIR Reactor Repair Gantt - SINGLE BASE MANUAL MODE
' Office: LTSC 2021 compatible
'
' Workbook contract:
'   - Summary
'   - LOG
'   - Gantt_BASE
'
' User-editable columns:
'   - Start / End / Days / Risk / Notes
'
' Scheduling behavior:
'   - Start edit keeps current-row duration and shifts all lower task rows
'   - End edit keeps current-row start, recalculates days, and shifts all lower task rows
'   - Days edit keeps current-row start, recalculates end, and shifts all lower task rows
' ============================================================

' ---- Sheet constants
Public Const SHEET_PREFIX As String = "Gantt_"
Public Const SHEET_BASE As String = "Gantt_BASE"
Public Const HEADER_ROW As Long = 3
Public Const FIRST_DATA_ROW As Long = 4

' ---- Columns (A:J meta, K~ date columns) - UNIFIED 10 columns
Public Const COL_STEP As Long = 1
Public Const COL_PHASE As Long = 2
Public Const COL_TASK As Long = 3
Public Const COL_START As Long = 4
Public Const COL_END As Long = 5
Public Const COL_DAYS As Long = 6
Public Const COL_RISK As Long = 7
Public Const COL_NOTE As Long = 8
Public Const COL_PRED As Long = 9
Public Const COL_LAG As Long = 10

Public Const META_COLS As Long = 10
Public Const DATE_COL_START As Long = 11 ' K

Private Const UID_ROW_NAME_PREFIX As String = "MIR_UID_ROW_"
Private Const UID_ORIG_NAME_PREFIX As String = "MIR_UID_ORIG_"
Private Const HOLIDAY_CFG_NAME As String = "MIR_CFG_HOLIDAYS"
Private Const ORIG_TIMELINE_RANGE_NAME As String = "MIR_ORIG_TIMELINE_RANGE"
Private Const BUILD_TIMESTAMP_NAME As String = "MIR_BUILD_TIMESTAMP"
Private Const BUILD_BAS_TIMESTAMP_NAME As String = "MIR_BUILD_BAS_TIMESTAMP"
Private Const BUILD_HOOK_TIMESTAMP_NAME As String = "MIR_BUILD_EVENTHOOK_TIMESTAMP"
Private Const BUILD_TOKEN_NAME As String = "MIR_BUILD_TOKEN"
Private Const SHEET_SUMMARY As String = "Summary"
Private Const DASHBOARD_START_ROW As Long = 30
Private Const DASHBOARD_RECENT_HEADER_ROW As Long = 38
Private Const DASHBOARD_RECENT_FIRST_ROW As Long = 39
Private Const DASHBOARD_RECENT_LAST_ROW As Long = 43

' ---- Theme colors (HEX)
Private Const BG_DARK As String = "0D0F14"
Private Const BG_WEEKEND As String = "0D1020"
Private Const BG_SURFACE2 As String = "1A1E2A"
Private Const BG_HEADER As String = "0B1120"
Private Const BORDER_HEX As String = "232840"

Private Const C_AMBER As String = "E8B84B"
Private Const C_BLUE As String = "5EB8FF"
Private Const C_GREEN As String = "6BDFB0"
Private Const C_PINK As String = "F472B6"
Private Const C_ORANGE As String = "FB923C"
Private Const C_PURPLE As String = "A78BFA"
Private Const C_YELLOW As String = "FACC15"
Private Const C_RED As String = "FF5F5F"
Private Const C_DIM As String = "5A6480"
Private Const C_TEXT_BRIGHT As String = "EEFCFF"

' ---- Managed action buttons
Private Const BTN_PREFIX As String = "mirBtn"
Private Const BTN_INIT_NAME As String = "mirBtnInit"
Private Const BTN_RESET_NAME As String = "mirBtnReset"
Private Const BTN_NOTES_NAME As String = "mirBtnNotes"

' ---- Previous edit snapshot (for PROD shift mode)
Public gPrevSheet As String
Public gPrevRow As Long
Public gPrevCol As Long
Public gPrevStart As Variant
Public gPrevEnd As Variant
Public gPrevDays As Variant
Public gPrevRisk As Variant
Public gPrevNote As Variant
Public gPrevValue As Variant

' ---- Re-entry prevention flag
Private gEventProcessing As Boolean
Private gDisableConditionalFormatting As Boolean
Private gLegacySheetsReported As Boolean
Private gHolidayLookup As Object
Private gHolidayLookupSource As String

Private Type EditSnapshot
    sheetName As String
    rowNum As Long
    colNum As Long
    oldValue As Variant
    ts As Date
End Type

Private gUndoStack(1 To 10) As EditSnapshot
Private gUndoIndex As Long
Private gUndoCount As Long

Private Sub BeginOptimizedBlock(ByRef prevEvents As Boolean, ByRef prevScreenUpdating As Boolean, ByRef prevCalc As XlCalculation)
    prevEvents = Application.EnableEvents
    prevScreenUpdating = Application.ScreenUpdating
    prevCalc = Application.Calculation
    Application.EnableEvents = False
    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual
End Sub

Private Sub EndOptimizedBlock(ByVal prevEvents As Boolean, ByVal prevScreenUpdating As Boolean, ByVal prevCalc As XlCalculation)
    Application.Calculation = prevCalc
    Application.ScreenUpdating = prevScreenUpdating
    Application.EnableEvents = prevEvents
End Sub

Private Sub BeginSheetWrite(ByVal ws As Worksheet, ByRef wasProtected As Boolean)
    On Error GoTo EH
    wasProtected = False
    If ws Is Nothing Then Exit Sub
    
    wasProtected = ws.ProtectContents
    If wasProtected Then ws.Unprotect
    Exit Sub
EH:
    On Error Resume Next
    LogMsg "BeginSheetWrite", Err.Number & " - " & Err.Description, ws.Name
    Err.Clear
End Sub

Private Sub EndSheetWrite(ByVal ws As Worksheet, ByVal wasProtected As Boolean)
    On Error GoTo EH
    If ws Is Nothing Then Exit Sub
    If wasProtected Then ApplyProtection ws, True
    Exit Sub
EH:
    On Error Resume Next
    LogMsg "EndSheetWrite", Err.Number & " - " & Err.Description, ws.Name
    Err.Clear
End Sub

' ============================================================
' PUBLIC MACROS
' ============================================================
Public Sub Init_Unified_System()
    On Error GoTo EH
    
    Dim hadWarning As Boolean
    Dim prevEvents As Boolean
    Dim prevScreenUpdating As Boolean
    Dim prevCalc As XlCalculation
    Dim ws As Worksheet
    Dim foundBase As Boolean
    
    BeginOptimizedBlock prevEvents, prevScreenUpdating, prevCalc
    EnsureBuildMetadataDefaults
    ReportLegacySheetsOnce
    
    For Each ws In ThisWorkbook.Worksheets
        If IsGanttSheet(ws) Then
            foundBase = True
            ' Ensure unprotected for initialization
            On Error Resume Next
            ws.Unprotect
            If Err.Number <> 0 Then
                hadWarning = True
                LogMsg "Init_Unified_System", "Unprotect warning: " & Err.Number & " - " & Err.Description, ws.Name
                Err.Clear
            End If
            On Error GoTo EH
            
            RefreshGantt ws, False
            EnsureUidScheduleSnapshot ws, False
            EnsureOriginalTimelineRangeSnapshot ws, False
            ApplyStaticColumnVisibility ws
            EnsureGanttActionButtons ws
            ApplyProtection ws, True
        End If
    Next ws
    
    Set ws = Nothing
    
    EndOptimizedBlock prevEvents, prevScreenUpdating, prevCalc
    
    If Not foundBase Then
        MsgBox SHEET_BASE & " sheet not found.", vbExclamation
        LogMsg "Init_Unified_System", "Missing " & SHEET_BASE
    ElseIf hadWarning Then
        LogMsg "Init_Unified_System", "Completed with warnings"
    Else
        LogMsg "Init_Unified_System", "Single-base manual mode initialized", SHEET_BASE
    End If
    RefreshSummaryDashboard "Init_Unified_System"
    Exit Sub
EH:
    hadWarning = True
    LogMsg "Init_Unified_System", "Warning: " & Err.Number & " - " & Err.Description
    Err.Clear
    Resume Next
End Sub

Private Sub Recalculate_Active_Scenario()
    On Error GoTo EH
    Dim ws As Worksheet
    Set ws = ActiveSheet
    If Not IsGanttSheet(ws) Then
        MsgBox "Active sheet is not " & SHEET_BASE & ".", vbExclamation
        Exit Sub
    End If
    
    RefreshGantt ws, False
    LogMsg "Recalculate_Active_Scenario", "Base sheet recalculated", ws.Name
    Exit Sub
EH:
    LogMsg "Recalculate_Active_Scenario", Err.Number & " - " & Err.Description
End Sub

Private Sub Recalculate_All_Scenarios()
    On Error GoTo EH
    Dim ws As Worksheet
    ReportLegacySheetsOnce
    For Each ws In ThisWorkbook.Worksheets
        If IsGanttSheet(ws) Then
            RefreshGantt ws, False
        End If
    Next ws
    LogMsg "Recalculate_All_Scenarios", "Base sheet recalculated", SHEET_BASE
    Exit Sub
EH:
    LogMsg "Recalculate_All_Scenarios", Err.Number & " - " & Err.Description
End Sub

Public Sub Reset_Schedule_To_Original(Optional ByVal silent As Boolean = False)
    On Error GoTo EH
    Dim ws As Worksheet
    Dim prevEvents As Boolean, prevScreen As Boolean, prevCalc As XlCalculation
    Dim optimizationOn As Boolean
    Dim wasProtected As Boolean
    Dim restoredCount As Long
    Dim origFirst As Date
    Dim origLast As Date
    
    Set ws = Nothing
    On Error Resume Next
    Set ws = ThisWorkbook.Worksheets(SHEET_BASE)
    On Error GoTo EH
    
    If ws Is Nothing Then
        MsgBox SHEET_BASE & " sheet not found.", vbExclamation
        Exit Sub
    End If
    
    BeginOptimizedBlock prevEvents, prevScreen, prevCalc
    optimizationOn = True
    BeginSheetWrite ws, wasProtected
    
    restoredCount = RestoreOriginalSchedule(ws)
    If restoredCount = 0 Then
        If Not silent Then MsgBox "Original schedule snapshot was not found. Reopen the workbook once to initialize the reset point.", vbExclamation
        LogMsg "Reset_Schedule_To_Original", "No original schedule snapshot found", ws.Name
        GoTo SafeExit
    End If
    
    If Not TryGetOriginalTimelineRange(origFirst, origLast) Then
        GetMinMaxDates ws, origFirst, origLast
    End If
    
    RefreshGanttExactRange ws, origFirst, origLast, False
    If Not silent Then MsgBox "Original schedule restored on " & ws.Name & ".", vbInformation
    LogMsg "Reset_Schedule_To_Original", "Restored " & restoredCount & " task rows", ws.Name
    
SafeExit:
    If wasProtected Then EndSheetWrite ws, wasProtected
    If optimizationOn Then EndOptimizedBlock prevEvents, prevScreen, prevCalc
    RefreshSummaryDashboard "Reset_Schedule_To_Original"
    Exit Sub
EH:
    If wasProtected Then EndSheetWrite ws, wasProtected
    If optimizationOn Then EndOptimizedBlock prevEvents, prevScreen, prevCalc
    LogMsg "Reset_Schedule_To_Original", Err.Number & " - " & Err.Description
End Sub

Public Sub Reset_Active_Scenario_To_Baseline(Optional ByVal invokedBy As String = "")
    Reset_Schedule_To_Original
    LogMsg "Reset_Active_Scenario_To_Baseline", "Compatibility wrapper invoked" & IIf(Len(invokedBy) > 0, " by " & invokedBy, "")
End Sub

Public Sub Reset_All_Scenarios_To_Baseline(Optional ByVal invokedBy As String = "")
    Reset_Schedule_To_Original
    LogMsg "Reset_All_Scenarios_To_Baseline", "Compatibility wrapper invoked" & IIf(Len(invokedBy) > 0, " by " & invokedBy, "")
End Sub

Public Sub Toggle_Notes_Action_Column(Optional ByVal silent As Boolean = False)
    On Error GoTo EH
    Dim ws As Worksheet
    Dim wasProtected As Boolean
    Dim notesHidden As Boolean
    
    Set ws = ActiveSheet
    If Not IsGanttSheet(ws) Then
        MsgBox "Active sheet is not " & SHEET_BASE & ".", vbExclamation
        Exit Sub
    End If
    
    BeginSheetWrite ws, wasProtected
    ws.Columns(COL_NOTE).Hidden = Not ws.Columns(COL_NOTE).Hidden
    notesHidden = ws.Columns(COL_NOTE).Hidden
    EnsureGanttActionButtons ws
    
    If wasProtected Then EndSheetWrite ws, wasProtected
    
    If Not silent Then MsgBox "Notes / Action column " & IIf(notesHidden, "hidden", "shown") & " on " & ws.Name & ".", vbInformation
    LogMsg "Toggle_Notes_Action_Column", "Notes column " & IIf(notesHidden, "hidden", "shown"), ws.Name
    RefreshSummaryDashboard "Toggle_Notes_Action_Column"
    Exit Sub
EH:
    If wasProtected Then EndSheetWrite ws, wasProtected
    LogMsg "Toggle_Notes_Action_Column", Err.Number & " - " & Err.Description
End Sub

Private Sub Protect_All_Gantt()
    On Error GoTo EH
    Dim ws As Worksheet
    For Each ws In ThisWorkbook.Worksheets
        If IsGanttSheet(ws) Then ApplyProtection ws, True
    Next ws
    MsgBox "Sheets protected (inputs still editable).", vbInformation
    Exit Sub
EH:
    LogMsg "Protect_All_Gantt", Err.Number & " - " & Err.Description
End Sub

Private Sub Unprotect_All_Gantt()
    On Error GoTo EH
    Dim ws As Worksheet
    For Each ws In ThisWorkbook.Worksheets
        If IsGanttSheet(ws) Then
            On Error Resume Next
            ws.Unprotect
            On Error GoTo EH
        End If
    Next ws
    MsgBox "Sheets unprotected.", vbInformation
    Exit Sub
EH:
    LogMsg "Unprotect_All_Gantt", Err.Number & " - " & Err.Description
End Sub

' ============================================================
' EVENT HOOKS (called from ThisWorkbook)
' ============================================================
Public Sub MIR_OnSelectionChange(ByVal ws As Worksheet, ByVal Target As Range)
    On Error GoTo EH
    Dim hit As Range
    Dim logRow As Long
    Dim logCol As Long
    
    If Not IsGanttSheet(ws) Then Exit Sub
    If Target Is Nothing Then Exit Sub
    
    Set hit = Intersect(Target, ws.Range(ws.Cells(FIRST_DATA_ROW, COL_START), ws.Cells(ws.Rows.Count, COL_NOTE)))
    If hit Is Nothing Then GoTo SafeExit
    If hit.CountLarge <> 1 Then GoTo SafeExit
    Set hit = hit.Cells(1, 1)
    logRow = hit.Row
    logCol = hit.Column
    
    ' Capture previous values for shift mode
    If hit.Column >= COL_START And hit.Column <= COL_NOTE Then
        gPrevSheet = ws.Name
        gPrevRow = hit.Row
        gPrevCol = hit.Column
        gPrevStart = ws.Cells(hit.Row, COL_START).Value2
        gPrevEnd = ws.Cells(hit.Row, COL_END).Value2
        gPrevDays = ws.Cells(hit.Row, COL_DAYS).Value2
        gPrevRisk = ws.Cells(hit.Row, COL_RISK).Value2
        gPrevNote = ws.Cells(hit.Row, COL_NOTE).Value2
        gPrevValue = ws.Cells(hit.Row, hit.Column).Value2
    End If

SafeExit:
    Set hit = Nothing
    Exit Sub
EH:
    LogMsg "MIR_OnSelectionChange", Err.Number & " - " & Err.Description, ws.Name, logRow, logCol
    Set hit = Nothing
End Sub

Public Sub MIR_OnChange(ByVal ws As Worksheet, ByVal Target As Range)
    On Error GoTo EH
    Dim prevEvents As Boolean, prevScreen As Boolean, prevCalc As XlCalculation
    Dim optimizationOn As Boolean
    Dim wasProtected As Boolean
    Dim logRow As Long
    Dim logCol As Long
    Dim beforeStart As Variant
    Dim beforeEnd As Variant
    Dim beforeDays As Variant
    Dim beforeRisk As Variant
    Dim beforeNote As Variant
    Dim beforeValue As Variant
    Dim useSnapshot As Boolean
    
    If Not IsGanttSheet(ws) Then Exit Sub
    If Target Is Nothing Then Exit Sub
    
    ' Re-entry prevention
    If gEventProcessing Then
        LogMsg "MIR_OnChange", "Re-entry blocked", ws.Name, Target.Row, Target.Column
        Exit Sub
    End If
    
    Dim hit As Range
    Set hit = Intersect(Target, ws.Range(ws.Cells(FIRST_DATA_ROW, COL_START), ws.Cells(ws.Rows.Count, COL_NOTE)))
    If hit Is Nothing Then
        Set hit = Nothing
        Exit Sub
    End If
    logRow = hit.Row
    logCol = hit.Column
    
    gEventProcessing = True
    BeginSheetWrite ws, wasProtected
    BeginOptimizedBlock prevEvents, prevScreen, prevCalc
    optimizationOn = True
    
    ' Multi-cell paste: normalize dates only when the schedule changed.
    If hit.CountLarge <> 1 Then
        If Not Intersect(hit, ws.Range(ws.Cells(FIRST_DATA_ROW, COL_START), ws.Cells(ws.Rows.Count, COL_DAYS))) Is Nothing Then
            NormalizeSheetDates ws
            ValidateSheetRows ws
            RefreshGantt ws, False
            LogMsg "ScheduleEdit", "Multi-cell schedule update count=" & hit.CountLarge, ws.Name, hit.Row, hit.Column
            RefreshSummaryDashboard "MIR_OnChange"
        ElseIf Not Intersect(hit, ws.Range(ws.Cells(FIRST_DATA_ROW, COL_RISK), ws.Cells(ws.Rows.Count, COL_RISK))) Is Nothing Then
            If IsPaintModeActive() Then
                RefreshPaintOnly ws, True
            End If
            LogMsg "ScheduleEdit", "Multi-cell risk update count=" & hit.CountLarge, ws.Name, hit.Row, hit.Column
            RefreshSummaryDashboard "MIR_OnChange"
        End If
        GoTo SafeExit
    End If
    
    Set hit = hit.Cells(1, 1)
    logRow = hit.Row
    logCol = hit.Column
    useSnapshot = (gPrevSheet = ws.Name And gPrevRow = hit.Row)
    If useSnapshot Then
        beforeStart = gPrevStart
        beforeEnd = gPrevEnd
        beforeDays = gPrevDays
        beforeRisk = gPrevRisk
        beforeNote = gPrevNote
        If gPrevCol = hit.Column Then
            beforeValue = gPrevValue
        Else
            beforeValue = ws.Cells(hit.Row, hit.Column).Value2
        End If
    Else
        beforeStart = ws.Cells(hit.Row, COL_START).Value2
        beforeEnd = ws.Cells(hit.Row, COL_END).Value2
        beforeDays = ws.Cells(hit.Row, COL_DAYS).Value2
        beforeRisk = ws.Cells(hit.Row, COL_RISK).Value2
        beforeNote = ws.Cells(hit.Row, COL_NOTE).Value2
        beforeValue = ws.Cells(hit.Row, hit.Column).Value2
    End If
    
    If IsGroupRow(ws, hit.Row) Then GoTo SafeExit

    If gPrevSheet = ws.Name And gPrevRow = hit.Row And gPrevCol = hit.Column Then
        CaptureSnapshot ws, hit.Row, hit.Column, gPrevValue
    End If

    ' Normalize/coerce dates before validation so manual refresh is not skipped on text entry.
    If hit.Column >= COL_START And hit.Column <= COL_END Then
        NormalizeRowDates ws, hit.Row
    End If

    PrimeRowDefaults ws, hit.Row, hit.Column
    NormalizeRowDates ws, hit.Row

    HandleShiftMode ws, hit
    
    ' Validate after the edit logic runs.
    ' This prevents Start edits from being blocked by a temporary Start > old End state
    ' before KeepDurationOnStartChange recalculates End and shifts lower rows.
    If hit.Column <= COL_DAYS Then
        If Not ValidateTaskRow(ws, hit.Row) Then GoTo SafeExit
    End If
    
    Select Case hit.Column
        Case COL_NOTE
            ' Notes do not affect schedule or bar colors.
        Case COL_RISK
            If IsPaintModeActive() Then
                RefreshPaintOnly ws, True
            End If
        Case Else
            RefreshGantt ws, False
    End Select

    LogScheduleEdit ws, hit.Row, hit.Column, beforeValue, beforeStart, beforeEnd, beforeDays, beforeRisk, beforeNote
    RefreshSummaryDashboard "MIR_OnChange"
    
SafeExit:
    If wasProtected Then EndSheetWrite ws, wasProtected
    If optimizationOn Then EndOptimizedBlock prevEvents, prevScreen, prevCalc
    gEventProcessing = False
    Set hit = Nothing
    Exit Sub
    
EH:
    LogMsg "MIR_OnChange", Err.Number & " - " & Err.Description, ws.Name, logRow, logCol
    If wasProtected Then EndSheetWrite ws, wasProtected
    If optimizationOn Then EndOptimizedBlock prevEvents, prevScreen, prevCalc
    gEventProcessing = False
    Set hit = Nothing
End Sub

Private Sub CaptureSnapshot(ByVal ws As Worksheet, ByVal r As Long, ByVal c As Long, ByVal oldValue As Variant)
    gUndoIndex = (gUndoIndex Mod 10) + 1
    gUndoCount = WorksheetFunction.Min(gUndoCount + 1, 10)
    With gUndoStack(gUndoIndex)
        .sheetName = ws.Name
        .rowNum = r
        .colNum = c
        .oldValue = oldValue
        .ts = Now
    End With
End Sub



Private Sub PrimeRowDefaults(ByVal ws As Worksheet, ByVal r As Long, ByVal editedCol As Long)
    On Error GoTo EH

    Dim hasStart As Boolean, hasEnd As Boolean
    Dim startDate As Date
    Dim endDate As Date
    hasStart = TryGetCellDate(ws.Cells(r, COL_START), startDate)
    hasEnd = TryGetCellDate(ws.Cells(r, COL_END), endDate)

    Select Case editedCol
        Case COL_START
            If hasStart Then
                If LongOrDefault(ws.Cells(r, COL_DAYS).Value, 0) < 1 Then
                    If LongOrDefault(gPrevDays, 0) > 0 Then
                        ws.Cells(r, COL_DAYS).Value = LongOrDefault(gPrevDays, 1)
                    Else
                        ws.Cells(r, COL_DAYS).Value = 1
                    End If
                End If
                If Not hasEnd Then UpdateEndFromStartDays ws, r
            End If

        Case COL_DAYS
            If hasStart Then UpdateEndFromStartDays ws, r

        Case COL_END
            If hasEnd And Not hasStart Then
                ws.Cells(r, COL_START).Value2 = endDate
                SafeSetNumberFormat ws.Cells(r, COL_START), "yyyy-mm-dd"
            End If
            If hasStart And hasEnd Then
                UpdateDaysFromStartEnd ws, r
            End If
    End Select

    Exit Sub
EH:
    LogMsg "PrimeRowDefaults", Err.Number & " - " & Err.Description, ws.Name, r, editedCol
End Sub

Private Sub Undo_LastEdit()
    On Error GoTo EH
    If gUndoCount = 0 Or gUndoIndex = 0 Then
        MsgBox "No undo history.", vbInformation
        Exit Sub
    End If
    
    Dim ws As Worksheet
    Dim prevEvents As Boolean, prevScreen As Boolean, prevCalc As XlCalculation
    Dim optimizationOn As Boolean
    Dim wasProtected As Boolean
    BeginOptimizedBlock prevEvents, prevScreen, prevCalc
    optimizationOn = True
    
    Set ws = ThisWorkbook.Worksheets(gUndoStack(gUndoIndex).sheetName)
    BeginSheetWrite ws, wasProtected
    ws.Cells(gUndoStack(gUndoIndex).rowNum, gUndoStack(gUndoIndex).colNum).Value2 = gUndoStack(gUndoIndex).oldValue
    If wasProtected Then EndSheetWrite ws, wasProtected
    EndOptimizedBlock prevEvents, prevScreen, prevCalc
    optimizationOn = False
    
    MsgBox "Undo applied: " & ws.Name & " R" & gUndoStack(gUndoIndex).rowNum & "C" & gUndoStack(gUndoIndex).colNum, vbInformation
    gUndoIndex = gUndoIndex - 1
    gUndoCount = gUndoCount - 1
    Exit Sub
EH:
    If wasProtected Then EndSheetWrite ws, wasProtected
    If optimizationOn Then EndOptimizedBlock prevEvents, prevScreen, prevCalc
    LogMsg "Undo_LastEdit", Err.Number & " - " & Err.Description
End Sub

' ============================================================
' SINGLE-BASE MANUAL SHIFT LOGIC
' ============================================================
Private Sub HandleShiftMode(ByVal ws As Worksheet, ByVal Target As Range)
    Dim r As Long: r = Target.Row
    Dim currentDate As Date
    Dim currentStart As Date
    Dim currentEnd As Date
    Dim prevStart As Date
    Dim prevEnd As Date
    Dim prevDays As Long
    Dim delta As Long
    
    Select Case Target.Column
        Case COL_START
            NormalizeRowDates ws, r
            If TryResolvePreviousRowState(ws, r, Target.Column, prevStart, prevEnd, prevDays) Then
                KeepDurationOnStartChange ws, r, prevStart, prevEnd
            End If
            
            If TryResolvePreviousRowState(ws, r, Target.Column, prevStart, prevEnd, prevDays) Then
                If TryGetCellDate(ws.Cells(r, COL_START), currentDate) Then
                    delta = DateDelta(prevStart, currentDate)
                    If delta <> 0 Then ShiftDownstream ws, r, delta, False
                    If delta <> 0 Then ShiftUpstream ws, r, delta
                End If
            End If
            UpdateDaysFromStartEnd ws, r
            
        Case COL_END
            NormalizeRowDates ws, r
            If TryResolvePreviousRowState(ws, r, Target.Column, prevStart, prevEnd, prevDays) Then
                If TryGetCellDate(ws.Cells(r, COL_START), currentStart) And TryGetCellDate(ws.Cells(r, COL_END), currentEnd) Then
                    If currentEnd >= currentStart Then
                        UpdateDaysFromStartEnd ws, r
                        delta = DateDelta(prevEnd, currentEnd)
                        If delta <> 0 Then ShiftDownstream ws, r, delta, False
                    End If
                End If
            Else
                UpdateDaysFromStartEnd ws, r
            End If
            
        Case COL_DAYS
            If TryResolvePreviousRowState(ws, r, Target.Column, prevStart, prevEnd, prevDays) Then
                UpdateEndFromStartDays ws, r
                If TryGetCellDate(ws.Cells(r, COL_START), currentStart) And TryGetCellDate(ws.Cells(r, COL_END), currentEnd) Then
                    If currentEnd >= currentStart Then
                        delta = DateDelta(prevEnd, currentEnd)
                        If delta <> 0 Then ShiftDownstream ws, r, delta, False
                    End If
                End If
                UpdateDaysFromStartEnd ws, r
            Else
                UpdateEndFromStartDays ws, r
            End If
            
        Case COL_RISK, COL_NOTE
            ' Manual notes/risk edits do not alter schedule calculations.
    End Select
End Sub

Private Function TryResolvePreviousRowState(ByVal ws As Worksheet, ByVal r As Long, ByVal editedCol As Long, ByRef prevStart As Date, ByRef prevEnd As Date, ByRef prevDays As Long) As Boolean
    On Error GoTo EH
    Dim useWD As Boolean
    Dim havePrevStart As Boolean
    Dim havePrevEnd As Boolean
    Dim currentStart As Date
    Dim currentEnd As Date
    
    If gPrevSheet = ws.Name And gPrevRow = r Then
        havePrevStart = TryParseDateValue(gPrevStart, prevStart)
        havePrevEnd = TryParseDateValue(gPrevEnd, prevEnd)
        prevDays = LongOrDefault(gPrevDays, 0)
        
        If editedCol = COL_START And Not havePrevStart Then havePrevStart = TryParseDateValue(gPrevValue, prevStart)
        If editedCol = COL_END And Not havePrevEnd Then havePrevEnd = TryParseDateValue(gPrevValue, prevEnd)
        If editedCol = COL_DAYS And prevDays < 1 Then prevDays = LongOrDefault(gPrevValue, 0)
    End If
    
    If Not havePrevStart Then
        If TryGetCellDate(ws.Cells(r, COL_START), currentStart) Then
            prevStart = currentStart
            havePrevStart = True
        End If
    End If
    
    If Not havePrevEnd Then
        If TryGetCellDate(ws.Cells(r, COL_END), currentEnd) Then
            prevEnd = currentEnd
            havePrevEnd = True
        End If
    End If
    
    If prevDays < 1 Then prevDays = LongOrDefault(ws.Cells(r, COL_DAYS).Value, 0)
    
    useWD = CfgOn("CFG_SHIFT_WORKDAYS_ONLY", False)
    
    If Not havePrevStart And havePrevEnd And prevDays > 0 Then
        prevStart = AddDays(prevEnd, -(prevDays - 1), useWD)
        havePrevStart = True
    End If
    
    If Not havePrevEnd And havePrevStart And prevDays > 0 Then
        prevEnd = AddDays(prevStart, prevDays - 1, useWD)
        havePrevEnd = True
    End If
    
    If prevDays < 1 And havePrevStart And havePrevEnd Then
        prevDays = DateDiff("d", prevStart, prevEnd) + 1
    End If
    
    TryResolvePreviousRowState = (havePrevStart And havePrevEnd And prevDays > 0)
    Exit Function
EH:
    LogMsg "TryResolvePreviousRowState", Err.Number & " - " & Err.Description, ws.Name, r
End Function

Private Sub ShiftDownstream(ByVal ws As Worksheet, ByVal fromRow As Long, ByVal delta As Long, ByVal stopAtFixed As Boolean)
    On Error GoTo EH
    
    Dim lastR As Long: lastR = LastUsedRow(ws)
    Dim r As Long
    Dim st As Date, en As Date
    Dim useWD As Boolean: useWD = CfgOn("CFG_SHIFT_WORKDAYS_ONLY", False)
    
    For r = fromRow + 1 To lastR
        If IsGroupRow(ws, r) Then GoTo ContinueLoop
        If stopAtFixed And IsFixedRow(ws, r) Then Exit For
        
        If TryGetCellDate(ws.Cells(r, COL_START), st) And TryGetCellDate(ws.Cells(r, COL_END), en) Then
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
    LogMsg "ShiftDownstream", Err.Number & " - " & Err.Description, ws.Name, fromRow
End Sub
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
End Sub


Private Function DateDelta(ByVal d1 As Date, ByVal d2 As Date) As Long
    If CfgOn("CFG_SHIFT_WORKDAYS_ONLY", False) Then
        DateDelta = WorkdayDiff(d1, d2)
    Else
        DateDelta = DateDiff("d", d1, d2)
    End If
End Function

' ============================================================
' LEGACY PTO PATH (unused in single-base manual mode)
' ============================================================
Private Sub PTO_Recalculate(ByVal ws As Worksheet)
    On Error GoTo EH
    Dim wasProtected As Boolean
    BeginSheetWrite ws, wasProtected
    
    Dim dictEnd As Object
    Set dictEnd = CreateObject("Scripting.Dictionary")
    
    Dim lastR As Long: lastR = LastUsedRow(ws)
    Dim r As Long
    Dim stepId As String, predStr As String
    Dim lag As Long, days As Long
    Dim st As Date, en As Date
    Dim maxEnd As Date, gotPred As Boolean
    Dim useWD As Boolean: useWD = CfgOn("CFG_SHIFT_WORKDAYS_ONLY", False)
    
    For r = FIRST_DATA_ROW To lastR
        If IsGroupRow(ws, r) Then GoTo ContinueLoop
        
        stepId = Trim$(CStr(ws.Cells(r, COL_STEP).Value))
        If stepId = "" Then GoTo ContinueLoop
        
        ' Days
        days = LongOrDefault(ws.Cells(r, COL_DAYS).Value, 1)
        If days < 1 Then days = 1
        ws.Cells(r, COL_DAYS).Value = days
        
        ' Lag
        lag = LongOrDefault(ws.Cells(r, COL_LAG).Value, 0)
        
        predStr = Trim$(CStr(ws.Cells(r, COL_PRED).Value))
        
        If IsFixedRow(ws, r) Or predStr = "" Then
            If Not TryGetCellDate(ws.Cells(r, COL_START), st) Then
                LogMsg "PTO_Recalculate", "Missing Start on step=" & stepId, ws.Name, r, COL_START
                GoTo ContinueLoop
            End If
            If useWD Then st = NormalizeToWorkday(st)
            
        Else
            gotPred = False
            maxEnd = DateSerial(1900, 1, 1)
            
            Dim preds As Variant, p As Variant, key As String
            preds = SplitPred(predStr)
            For Each p In preds
                key = Trim$(CStr(p))
                If key <> "" Then
                    If dictEnd.Exists(key) Then
                        If Not gotPred Then
                            maxEnd = dictEnd(key)
                            gotPred = True
                        Else
                            If dictEnd(key) > maxEnd Then maxEnd = dictEnd(key)
                        End If
                    Else
                        LogMsg "PTO_Recalculate", "Predecessor not found: " & key & " for step=" & stepId, ws.Name, r, COL_PRED
                    End If
                End If
            Next p
            
            If Not gotPred Then GoTo ContinueLoop
            
            st = AddDays(maxEnd, lag + 1, useWD)
        End If
        
        ' End from start + days
        en = AddDays(st, days - 1, useWD)
        
        ws.Cells(r, COL_START).Value2 = st
        ws.Cells(r, COL_END).Value2 = en
        SafeSetNumberFormat ws.Cells(r, COL_START), "yyyy-mm-dd"
        SafeSetNumberFormat ws.Cells(r, COL_END), "yyyy-mm-dd"
        UpdateDaysFromStartEnd ws, r
        
        dictEnd(stepId) = en
        
ContinueLoop:
    Next r
    
CleanExit:
    If wasProtected Then EndSheetWrite ws, wasProtected
    Set dictEnd = Nothing
    Exit Sub
EH:
    LogMsg "PTO_Recalculate", Err.Number & " - " & Err.Description, ws.Name
    Resume CleanExit
End Sub

' ============================================================
' GANTT REFRESH (timeline expand + labels + CF/PAINT)
' ============================================================
Private Sub RefreshGantt(ByVal ws As Worksheet, ByVal includeToday As Boolean, Optional ByVal skipNormalize As Boolean = False)
    Dim prevEv As Boolean
    Dim wasProtected As Boolean
    Dim renderEndCol As Long
    Dim clearEndCol As Long
    prevEv = Application.EnableEvents
    Application.EnableEvents = False
    On Error GoTo EH
    BeginSheetWrite ws, wasProtected
    
    If Not skipNormalize Then NormalizeSheetDates ws
    
    Dim minD As Date, maxD As Date
    GetMinMaxDates ws, minD, maxD
    
    If includeToday Then
        If Date < minD Then minD = Date
        If Date > maxD Then maxD = Date
    End If
    
    EnsureTimelineCovers ws, minD, maxD
    renderEndCol = DATE_COL_START + DateDiff("d", minD, maxD)
    clearEndCol = HeaderLastCol(ws)
    If clearEndCol < renderEndCol Then clearEndCol = renderEndCol
    
    BuildDateHeader ws, minD, maxD
    FixHeaderMerges ws, clearEndCol
    
    WriteBarLabels ws, minD, maxD, clearEndCol
    
    If UCase$(CfgText("CFG_REPAINT_MODE", "PAINT")) = "PAINT" Or gDisableConditionalFormatting Then
        PaintBars ws, minD, maxD, clearEndCol
    Else
        ApplyConditionalFormatting ws, minD, maxD, clearEndCol
    End If
    ResetTimelineBorders ws, clearEndCol, LastUsedRow(ws)
    DrawTodayMarker ws, minD, maxD
    
    GoTo Fin
EH:
    LogMsg "RefreshGantt", Err.Number & " - " & Err.Description, ws.Name
Fin:
    If wasProtected Then EndSheetWrite ws, wasProtected
    Application.EnableEvents = prevEv
End Sub

Private Sub RefreshGanttExactRange(ByVal ws As Worksheet, ByVal firstD As Date, ByVal lastD As Date, Optional ByVal includeToday As Boolean = False)
    Dim prevEv As Boolean
    Dim wasProtected As Boolean
    Dim clearEndCol As Long
    prevEv = Application.EnableEvents
    Application.EnableEvents = False
    On Error GoTo EH
    BeginSheetWrite ws, wasProtected
    
    If includeToday Then
        If Date < firstD Then firstD = Date
        If Date > lastD Then lastD = Date
    End If
    
    EnsureTimelineMatches ws, firstD, lastD
    clearEndCol = HeaderLastCol(ws)
    
    BuildDateHeader ws, firstD, lastD
    FixHeaderMerges ws, clearEndCol
    WriteBarLabels ws, firstD, lastD, clearEndCol
    
    If UCase$(CfgText("CFG_REPAINT_MODE", "PAINT")) = "PAINT" Or gDisableConditionalFormatting Then
        PaintBars ws, firstD, lastD, clearEndCol
    Else
        ApplyConditionalFormatting ws, firstD, lastD, clearEndCol
    End If
    ResetTimelineBorders ws, clearEndCol, LastUsedRow(ws)
    DrawTodayMarker ws, firstD, lastD
    
    GoTo Fin
EH:
    LogMsg "RefreshGanttExactRange", Err.Number & " - " & Err.Description, ws.Name
Fin:
    If wasProtected Then EndSheetWrite ws, wasProtected
    Application.EnableEvents = prevEv
End Sub

Private Function IsPaintModeActive() As Boolean
    IsPaintModeActive = (UCase$(CfgText("CFG_REPAINT_MODE", "PAINT")) = "PAINT" Or gDisableConditionalFormatting)
End Function

Private Sub RefreshPaintOnly(ByVal ws As Worksheet, ByVal includeToday As Boolean)
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
End Sub

Private Sub GetMinMaxDates(ByVal ws As Worksheet, ByRef minD As Date, ByRef maxD As Date)
    Dim r As Long, lastR As Long
    Dim got As Boolean
    Dim st As Date, en As Date
    lastR = LastUsedRow(ws)
    
    got = False
    For r = FIRST_DATA_ROW To lastR
        If IsGroupRow(ws, r) Then GoTo ContinueLoop
        If TryGetCellDate(ws.Cells(r, COL_START), st) And TryGetCellDate(ws.Cells(r, COL_END), en) Then
            If Not got Then
                minD = st
                maxD = en
                got = True
            Else
                If st < minD Then minD = st
                If en > maxD Then maxD = en
            End If
        End If
ContinueLoop:
    Next r
    
    If Not got Then
        minD = Date
        maxD = Date
    End If
End Sub

Private Sub EnsureTimelineCovers(ByVal ws As Worksheet, ByVal minD As Date, ByVal maxD As Date)
    On Error GoTo EH
    
    Dim curFirst As Date, curLast As Date
    Dim lastCol As Long
    Dim addCols As Long
    
    curFirst = HeaderFirstDate(ws)
    curLast = HeaderLastDate(ws)
    
    ' Extend LEFT: insert columns before DATE_COL_START
    If IsDate(curFirst) Then
        If minD < curFirst Then
            addCols = DateDiff("d", minD, curFirst)
            LogMsg "EnsureTimelineCovers", "LEFT expand " & addCols & " cols (" & Format$(minD, "yyyy-mm-dd") & ")", ws.Name
            ws.Unprotect
            ws.Columns(DATE_COL_START).Resize(, addCols).Insert Shift:=xlShiftToRight
        End If
    End If
    
    ' Re-read after possible left expansion
    curFirst = HeaderFirstDate(ws)
    curLast = HeaderLastDate(ws)
    lastCol = HeaderLastCol(ws)
    
    ' Extend RIGHT: append columns after lastCol
    If IsDate(curLast) Then
        If maxD > curLast Then
            addCols = DateDiff("d", curLast, maxD)
            LogMsg "EnsureTimelineCovers", "RIGHT expand " & addCols & " cols (" & Format$(maxD, "yyyy-mm-dd") & ")", ws.Name
            ws.Unprotect
            ws.Columns(lastCol + 1).Resize(, addCols).Insert Shift:=xlShiftToRight
        End If
    End If
    
    Exit Sub
EH:
    LogMsg "EnsureTimelineCovers", "ERROR " & Err.Number & " - " & Err.Description, ws.Name
End Sub

Private Sub EnsureTimelineMatches(ByVal ws As Worksheet, ByVal targetFirst As Date, ByVal targetLast As Date)
    On Error GoTo EH
    
    Dim curFirst As Date
    Dim curLast As Date
    Dim lastCol As Long
    Dim deleteCols As Long
    
    If targetLast < targetFirst Then
        curFirst = targetFirst
        targetFirst = targetLast
        targetLast = curFirst
    End If
    
    EnsureTimelineCovers ws, targetFirst, targetLast
    
    curFirst = HeaderFirstDate(ws)
    curLast = HeaderLastDate(ws)
    
    If IsDate(curFirst) Then
        If curFirst < targetFirst Then
            deleteCols = DateDiff("d", curFirst, targetFirst)
            If deleteCols > 0 Then
                ws.Columns(DATE_COL_START).Resize(, deleteCols).Delete Shift:=xlToLeft
            End If
        End If
    End If
    
    curLast = HeaderLastDate(ws)
    lastCol = HeaderLastCol(ws)
    If IsDate(curLast) Then
        If curLast > targetLast Then
            deleteCols = DateDiff("d", targetLast, curLast)
            If deleteCols > 0 Then
                ws.Columns(lastCol - deleteCols + 1).Resize(, deleteCols).Delete Shift:=xlToLeft
            End If
        End If
    End If
    Exit Sub
EH:
    LogMsg "EnsureTimelineMatches", Err.Number & " - " & Err.Description, ws.Name
End Sub

Private Sub BuildDateHeader(ByVal ws As Worksheet, ByVal firstD As Date, ByVal lastD As Date)
    Dim totalDays As Long: totalDays = DateDiff("d", firstD, lastD) + 1
    Dim i As Long, d As Date, col As Long
    For i = 0 To totalDays - 1
        d = DateAdd("d", i, firstD)
        col = DATE_COL_START + i
        
        ws.Columns(col).ColumnWidth = 5#
        
        With ws.Cells(HEADER_ROW, col)
            .Value = d
            SafeSetNumberFormat ws.Cells(HEADER_ROW, col), "mm-dd"
            .Font.Bold = True
            .Font.Size = 7
            .HorizontalAlignment = xlCenter
            .VerticalAlignment = xlCenter
            .Interior.Color = HexToLong(BG_SURFACE2)
            
            If d = Date Then
                .Font.Color = HexToLong(C_RED)
            ElseIf Weekday(d, vbMonday) >= 6 Then
                .Font.Color = HexToLong(C_AMBER)
            Else
                .Font.Color = HexToLong(C_DIM)
            End If
            
            SetThinBorder ws.Cells(HEADER_ROW, col)
        End With
    Next i
End Sub

Private Sub FixHeaderMerges(ByVal ws As Worksheet, ByVal endCol As Long)
    On Error Resume Next
    ws.Range(ws.Cells(1, 1), ws.Cells(1, ws.Columns.Count)).UnMerge
    ws.Range(ws.Cells(2, 1), ws.Cells(2, ws.Columns.Count)).UnMerge
    On Error GoTo 0
    
    ws.Range(ws.Cells(1, 1), ws.Cells(1, endCol)).Merge
    ws.Range(ws.Cells(2, 1), ws.Cells(2, endCol)).Merge
End Sub

Private Sub WriteBarLabels(ByVal ws As Worksheet, ByVal firstD As Date, ByVal lastD As Date, Optional ByVal clearEndCol As Long = 0)
    Dim totalDays As Long: totalDays = DateDiff("d", firstD, lastD) + 1
    Dim renderEndCol As Long: renderEndCol = DATE_COL_START + totalDays - 1
    Dim lastR As Long: lastR = LastUsedRow(ws)
    Dim r As Long
    Dim st As Date, phase As String, offset As Long
    
    If clearEndCol < renderEndCol Then clearEndCol = renderEndCol
    ws.Range(ws.Cells(FIRST_DATA_ROW, DATE_COL_START), ws.Cells(lastR, clearEndCol)).ClearContents
    
    For r = FIRST_DATA_ROW To lastR
        If IsGroupRow(ws, r) Then GoTo ContinueLoop
        If Not TryGetCellDate(ws.Cells(r, COL_START), st) Then GoTo ContinueLoop
        phase = CStr(ws.Cells(r, COL_PHASE).Value)
        
        offset = DateDiff("d", firstD, st)
        If offset >= 0 And offset <= totalDays - 1 Then
            With ws.Cells(r, DATE_COL_START + offset)
                .Value = Left$(phase, 12)
                .Font.Bold = True
                .Font.Size = 7
                .HorizontalAlignment = xlLeft
                .VerticalAlignment = xlCenter
            End With
        End If
ContinueLoop:
    Next r
End Sub

Private Sub DrawTodayMarker(ByVal ws As Worksheet, ByVal firstD As Date, ByVal lastD As Date)
    Dim totalDays As Long: totalDays = DateDiff("d", firstD, lastD) + 1
    Dim offset As Long: offset = DateDiff("d", firstD, Date)
    If offset < 0 Or offset > totalDays - 1 Then Exit Sub
    
    Dim col As Long: col = DATE_COL_START + offset
    Dim lastR As Long: lastR = LastUsedRow(ws)
    Dim r As Long
    
    For r = HEADER_ROW To lastR
        With ws.Cells(r, col)
            .Borders(xlEdgeLeft).LineStyle = xlContinuous
            .Borders(xlEdgeLeft).Weight = xlMedium
            .Borders(xlEdgeLeft).Color = HexToLong(C_RED)
            .Borders(xlEdgeRight).LineStyle = xlContinuous
            .Borders(xlEdgeRight).Weight = xlMedium
            .Borders(xlEdgeRight).Color = HexToLong(C_RED)
        End With
    Next r
End Sub

Private Sub ResetTimelineBorders(ByVal ws As Worksheet, ByVal endCol As Long, ByVal lastR As Long)
    On Error GoTo EH
    If endCol < DATE_COL_START Then Exit Sub
    If lastR < HEADER_ROW Then Exit Sub
    
    With ws.Range(ws.Cells(HEADER_ROW, DATE_COL_START), ws.Cells(lastR, endCol)).Borders
        .LineStyle = xlContinuous
        .Weight = xlThin
        .Color = HexToLong(BORDER_HEX)
    End With
    Exit Sub
EH:
    LogMsg "ResetTimelineBorders", Err.Number & " - " & Err.Description, ws.Name
End Sub

Private Sub ApplyConditionalFormatting(ByVal ws As Worksheet, ByVal firstD As Date, ByVal lastD As Date, Optional ByVal clearEndCol As Long = 0)
    On Error GoTo EH
    
    ' Temporarily unprotect for CF operations
    Dim wasProtected As Boolean
    wasProtected = ws.ProtectContents
    If wasProtected Then ws.Unprotect
    
    Dim totalDays As Long: totalDays = DateDiff("d", firstD, lastD) + 1
    Dim renderEndCol As Long: renderEndCol = DATE_COL_START + totalDays - 1
    Dim lastR As Long: lastR = LastUsedRow(ws)
    ' Inverted/empty grid causes Error 5 on FormatConditions.Add
    If totalDays < 1 Or lastR < FIRST_DATA_ROW Then GoTo CleanExit
    
    Dim rng As Range
    Dim clearRng As Range
    
    If clearEndCol < renderEndCol Then clearEndCol = renderEndCol
    Set clearRng = ws.Range(ws.Cells(FIRST_DATA_ROW, DATE_COL_START), ws.Cells(lastR, clearEndCol))
    Set rng = ws.Range(ws.Cells(FIRST_DATA_ROW, DATE_COL_START), ws.Cells(lastR, renderEndCol))
    
    On Error Resume Next
    clearRng.FormatConditions.Delete
    On Error GoTo EH
    
    ResetTimelineSurface ws, clearEndCol, lastR
    
    Dim colL As String: colL = ColLetter(DATE_COL_START)
    Dim fc As FormatCondition
    Dim weekendFormula As String
    
    ' Weekend background
    weekendFormula = "=AND($D4<>"""",WEEKDAY(" & colL & "$3,2)>5)"
    If TryAddExpressionCF(rng, weekendFormula, fc, "AddWeekendRule", ws.Name) Then
        fc.Interior.Color = HexToLong(BG_WEEKEND)
    Else
        GoTo UsePaint
    End If
    
    If Not AddPhaseRule(rng, colL, "DOC", C_BLUE) Then GoTo UsePaint
    If Not AddPhaseRule(rng, colL, "PICKUP", C_BLUE) Then GoTo UsePaint
    If Not AddPhaseRule(rng, colL, "UAE_REP", C_PURPLE) Then GoTo UsePaint
    If Not AddPhaseRule(rng, colL, "LAB_GATE", C_BLUE) Then GoTo UsePaint
    If Not AddPhaseRule(rng, colL, "GCC_BLACK", C_DIM) Then GoTo UsePaint
    If Not AddPhaseRule(rng, colL, "TRANS_OUT", C_ORANGE) Then GoTo UsePaint
    If Not AddPhaseRule(rng, colL, "KSA_REP", C_PINK) Then GoTo UsePaint
    If Not AddPhaseRule(rng, colL, "TRANS_BACK", C_GREEN) Then GoTo UsePaint
    If Not AddPhaseRule(rng, colL, "FINAL", C_YELLOW) Then GoTo UsePaint
    
    ' Risk override - split into simpler formula
    Dim riskFormula As String
    riskFormula = "=AND($D4<>""""," & colL & "$3>=$D4," & colL & "$3<=$E4," & _
                  "OR(ISNUMBER(SEARCH(""HIGH"",$G4)),ISNUMBER(SEARCH(""WARNING"",$G4))))"
    
    If TryAddExpressionCF(rng, riskFormula, fc, "AddRiskRule", ws.Name) Then
        fc.Interior.Color = HexToLong(C_RED)
        fc.SetFirstPriority
    Else
        GoTo UsePaint
    End If
    
    If rng.FormatConditions.Count = 0 Then
        GoTo UsePaint
    End If
    
    ' Restore protection
    If wasProtected Then ApplyProtection ws, True
    
    Set rng = Nothing
    Set fc = Nothing
    Exit Sub
UsePaint:
    gDisableConditionalFormatting = True
    On Error Resume Next
    clearRng.FormatConditions.Delete
    On Error GoTo EH
    PaintBars ws, firstD, lastD, clearEndCol
    LogMsg "ApplyConditionalFormatting", "CF disabled for this session; using PAINT", ws.Name
    If wasProtected Then ApplyProtection ws, True
    Set clearRng = Nothing
    Set rng = Nothing
    Set fc = Nothing
    Exit Sub
CleanExit:
    If wasProtected Then ApplyProtection ws, True
    Set clearRng = Nothing
    Set rng = Nothing
    Set fc = Nothing
    Exit Sub
EH:
    LogMsg "ApplyConditionalFormatting", Err.Number & " - " & Err.Description, ws.Name
    ' Restore protection even on error
    If wasProtected Then
        On Error Resume Next
        ApplyProtection ws, True
    End If
    Set clearRng = Nothing
    Set rng = Nothing
    Set fc = Nothing
End Sub

Private Function AddPhaseRule(ByVal rng As Range, ByVal colL As String, ByVal key As String, ByVal hexColor As String) As Boolean
    On Error GoTo EH
    Dim fc As FormatCondition
    Dim phaseFormula As String
    phaseFormula = "=AND($D4<>"""",ISNUMBER(SEARCH(""" & key & """,$B4))," & colL & "$3>=$D4," & colL & "$3<=$E4)"
    
    If TryAddExpressionCF(rng, phaseFormula, fc, "AddPhaseRule", rng.Worksheet.Name & " [key=" & key & "]") Then
        fc.Interior.Color = HexToLong(hexColor)
        AddPhaseRule = True
    End If
CleanExit:
    Set fc = Nothing
    Exit Function
EH:
    LogMsg "AddPhaseRule", "Error " & Err.Number & ": " & Err.Description & " [key=" & key & "]", rng.Worksheet.Name
    Err.Clear
    AddPhaseRule = False
    Resume CleanExit
End Function

Private Function TryAddExpressionCF(ByVal rng As Range, ByVal formulaUS As String, ByRef fc As FormatCondition, ByVal procName As String, ByVal logContext As String) As Boolean
    On Error GoTo EH
    Dim localSep As String
    Dim formulaLocal As String
    Dim errNo As Long
    Dim errMsg As String
    
    Set fc = rng.FormatConditions.Add(Type:=xlExpression, Formula1:=formulaUS)
    TryAddExpressionCF = True
    Exit Function
EH:
    errNo = Err.Number
    errMsg = Err.Description
    localSep = CfListSep()
    Err.Clear
    
    If localSep <> "," Then
        On Error GoTo LocalEH
        formulaLocal = Replace(formulaUS, ",", localSep)
        Set fc = rng.FormatConditions.Add(Type:=xlExpression, Formula1:=formulaLocal)
        TryAddExpressionCF = True
        Exit Function
    End If
    
    LogMsg procName, "Error " & errNo & ": " & errMsg & " | Formula=" & formulaUS, logContext
    Err.Clear
    Exit Function
LocalEH:
    LogMsg procName, "Error " & Err.Number & ": " & Err.Description & " | FormulaUS=" & formulaUS & " | FormulaLocal=" & formulaLocal, logContext
    Err.Clear
End Function

Private Sub PaintBars(ByVal ws As Worksheet, ByVal firstD As Date, ByVal lastD As Date, Optional ByVal clearEndCol As Long = 0)
    On Error GoTo EH
    
    Dim totalDays As Long: totalDays = DateDiff("d", firstD, lastD) + 1
    Dim renderEndCol As Long: renderEndCol = DATE_COL_START + totalDays - 1
    Dim lastR As Long: lastR = LastUsedRow(ws)
    Dim bodyRng As Range
    
    If totalDays < 1 Or lastR < FIRST_DATA_ROW Then Exit Sub
    If clearEndCol < renderEndCol Then clearEndCol = renderEndCol
    
    Set bodyRng = ws.Range(ws.Cells(FIRST_DATA_ROW, DATE_COL_START), ws.Cells(lastR, clearEndCol))
    ResetTimelineSurface ws, clearEndCol, lastR
    
    Dim r As Long
    Dim st As Date, en As Date, offsetS As Long, offsetE As Long
    Dim phase As String, risk As String
    
    For r = FIRST_DATA_ROW To lastR
        If IsGroupRow(ws, r) Then GoTo ContinueRow
        
        If Not (TryGetCellDate(ws.Cells(r, COL_START), st) And TryGetCellDate(ws.Cells(r, COL_END), en)) Then GoTo ContinueRow
        offsetS = DateDiff("d", firstD, st)
        offsetE = DateDiff("d", firstD, en)
        If offsetS < 0 Then offsetS = 0
        If offsetE > totalDays - 1 Then offsetE = totalDays - 1
        If offsetS > offsetE Then GoTo ContinueRow
        
        phase = CStr(ws.Cells(r, COL_PHASE).Value)
        risk = CStr(ws.Cells(r, COL_RISK).Value)
        
        Dim barColor As Long
        If InStr(1, risk, "HIGH", vbTextCompare) > 0 Or InStr(1, risk, "WARNING", vbTextCompare) > 0 Then
            barColor = HexToLong(C_RED)
        Else
            barColor = PhaseColorLong(phase)
        End If
        
        ws.Range(ws.Cells(r, DATE_COL_START + offsetS), ws.Cells(r, DATE_COL_START + offsetE)).Interior.Color = barColor
        
ContinueRow:
    Next r
    
    Set bodyRng = Nothing
    Exit Sub
EH:
    LogMsg "PaintBars", Err.Number & " - " & Err.Description, ws.Name
    Set bodyRng = Nothing
End Sub

' ============================================================
' LEGACY BASELINE SUPPORT
' ============================================================
Private Sub RestoreFromBaseline(ByVal ws As Worksheet)
    LogMsg "RestoreFromBaseline", "Legacy baseline restore ignored in single-base manual mode", ws.Name
End Sub

Private Sub NormalizeSheetDates(ByVal ws As Worksheet)
    Dim r As Long, lastR As Long
    lastR = LastUsedRow(ws)
    For r = FIRST_DATA_ROW To lastR
        If IsGroupRow(ws, r) Then GoTo ContinueLoop
        NormalizeRowDates ws, r
ContinueLoop:
    Next r
End Sub

Private Function ValidateTaskRow(ByVal ws As Worksheet, ByVal r As Long) As Boolean
    On Error GoTo ValidationFailed
    ValidateTaskRow = True

    If IsGroupRow(ws, r) Then Exit Function
    If IsEmptyTaskRow(ws, r) Then Exit Function
    
    NormalizeRowDates ws, r

    If IsBlankish(ws.Cells(r, COL_STEP).Value2) Then
        LogMsg "ValidateTaskRow", "Missing Step ID", ws.Name, r, COL_STEP
        ValidateTaskRow = False
        Exit Function
    End If

    Dim st As Date, en As Date, d As Long
    
    If Not TryGetCellDate(ws.Cells(r, COL_START), st) Then
        LogMsg "ValidateTaskRow", "Invalid Start date", ws.Name, r, COL_START
        ValidateTaskRow = False
        Exit Function
    End If
    If Not TryGetCellDate(ws.Cells(r, COL_END), en) Then
        LogMsg "ValidateTaskRow", "Invalid End date", ws.Name, r, COL_END
        ValidateTaskRow = False
        Exit Function
    End If

    If st > en Then
        LogMsg "ValidateTaskRow", "Start > End", ws.Name, r, COL_START
        ValidateTaskRow = False
        Exit Function
    End If

    d = DateDiff("d", st, en) + 1
    If LongOrDefault(ws.Cells(r, COL_DAYS).Value2, 0) <> d Then
        ws.Cells(r, COL_DAYS).Value2 = d
    End If

    Exit Function
ValidationFailed:
    LogMsg "ValidateTaskRow", "Error: " & Err.Description, ws.Name, r
    ValidateTaskRow = False
End Function

Private Sub ValidateSheetRows(ByVal ws As Worksheet)
    Dim r As Long, lastR As Long
    lastR = LastUsedRow(ws)
    For r = FIRST_DATA_ROW To lastR
        If IsGroupRow(ws, r) Then GoTo ContinueLoop
        Call ValidateTaskRow(ws, r)
ContinueLoop:
    Next r
End Sub

Private Sub TryCoerceCellDate(ByVal c As Range)
    Dim d As Date
    
    If TryParseDateValue(c.Value2, d) Or TryParseDateValue(c.Value, d) Then
        c.Value2 = d
        SafeSetNumberFormat c, "yyyy-mm-dd"
    End If
End Sub

Private Function TryGetCellDate(ByVal c As Range, ByRef d As Date) As Boolean
    TryGetCellDate = TryParseDateValue(c.Value2, d)
    If Not TryGetCellDate Then
        TryGetCellDate = TryParseDateValue(c.Value, d)
    End If
End Function

Private Function TryParseDateValue(ByVal v As Variant, ByRef d As Date) As Boolean
    On Error GoTo Fail
    
    If IsError(v) Or IsEmpty(v) Then Exit Function
    
    If VarType(v) = vbDate Then
        d = CDate(v)
        TryParseDateValue = True
        Exit Function
    End If
    
    If IsNumeric(v) Then
        If CDbl(v) > 0 And CDbl(v) < 60000 Then
            d = CDate(CDbl(v))
            TryParseDateValue = True
            Exit Function
        End If
    End If
    
    Dim s As String
    s = Trim$(CStr(v))
    If Len(s) = 0 Then Exit Function
    
    If IsDate(s) Then
        d = CDate(s)
        TryParseDateValue = True
        Exit Function
    End If
    
    If ParseDashedDate(s, d) Then
        TryParseDateValue = True
        Exit Function
    End If
    
Fail:
    Err.Clear
End Function

Private Function ParseDashedDate(ByVal s As String, ByRef d As Date) As Boolean
    On Error GoTo Fail
    Dim parts As Variant
    Dim y As Long, m As Long, dd As Long
    
    s = Trim$(s)
    If InStr(1, s, "T", vbTextCompare) > 0 Then s = Split(s, "T")(0)
    If InStr(1, s, " ", vbTextCompare) > 0 Then s = Split(s, " ")(0)
    s = Replace(s, ".", "-")
    s = Replace(s, "/", "-")
    
    parts = Split(s, "-")
    If UBound(parts) <> 2 Then Exit Function
    
    If Len(Trim$(CStr(parts(0)))) = 4 Then
        y = LongOrDefault(parts(0), 0)
        m = LongOrDefault(parts(1), 0)
        dd = LongOrDefault(parts(2), 0)
    ElseIf Len(Trim$(CStr(parts(2)))) = 4 Then
        y = LongOrDefault(parts(2), 0)
        If LongOrDefault(parts(0), 0) > 12 Then
            dd = LongOrDefault(parts(0), 0)
            m = LongOrDefault(parts(1), 0)
        Else
            m = LongOrDefault(parts(0), 0)
            dd = LongOrDefault(parts(1), 0)
        End If
    Else
        Exit Function
    End If
    
    If y < 1900 Or m < 1 Or m > 12 Or dd < 1 Or dd > 31 Then Exit Function
    
    d = DateSerial(y, m, dd)
    ParseDashedDate = True
    Exit Function
Fail:
    Err.Clear
End Function

Private Sub NormalizeRowDates(ByVal ws As Worksheet, ByVal r As Long)
    On Error Resume Next
    Dim useWD As Boolean: useWD = CfgOn("CFG_SHIFT_WORKDAYS_ONLY", False)
    Dim st As Date
    Dim en As Date
    
    TryCoerceCellDate ws.Cells(r, COL_START)
    TryCoerceCellDate ws.Cells(r, COL_END)
    
    If TryGetCellDate(ws.Cells(r, COL_START), st) Then
        If useWD Then st = NormalizeToWorkday(st)
        ws.Cells(r, COL_START).Value2 = st
        SafeSetNumberFormat ws.Cells(r, COL_START), "yyyy-mm-dd"
    End If
    
    If TryGetCellDate(ws.Cells(r, COL_END), en) Then
        If useWD Then en = NormalizeToWorkday(en)
        ws.Cells(r, COL_END).Value2 = en
        SafeSetNumberFormat ws.Cells(r, COL_END), "yyyy-mm-dd"
    End If
    
    If Err.Number <> 0 Then
        LogMsg "NormalizeRowDates", "Format error: " & Err.Description, ws.Name, r
        Err.Clear
    End If
End Sub

Private Sub UpdateDaysFromStartEnd(ByVal ws As Worksheet, ByVal r As Long)
    Dim st As Date, en As Date
    If Not (TryGetCellDate(ws.Cells(r, COL_START), st) And TryGetCellDate(ws.Cells(r, COL_END), en)) Then Exit Sub
    ws.Cells(r, COL_DAYS).Value = DateDiff("d", st, en) + 1
End Sub

Private Sub UpdateEndFromStartDays(ByVal ws As Worksheet, ByVal r As Long)
    Dim st As Date
    If Not TryGetCellDate(ws.Cells(r, COL_START), st) Then Exit Sub
    Dim d As Long: d = LongOrDefault(ws.Cells(r, COL_DAYS).Value, 1)
    If d < 1 Then d = 1
    Dim useWD As Boolean: useWD = CfgOn("CFG_SHIFT_WORKDAYS_ONLY", False)
    
    Dim en As Date: en = AddDays(st, d - 1, useWD)
    ws.Cells(r, COL_END).Value2 = en
    SafeSetNumberFormat ws.Cells(r, COL_END), "yyyy-mm-dd"
End Sub

Private Sub KeepDurationOnStartChange(ByVal ws As Worksheet, ByVal r As Long, ByVal prevSt As Date, ByVal prevEn As Date)
    Dim st As Date
    
    If Not TryGetCellDate(ws.Cells(r, COL_START), st) Then Exit Sub
    
    Dim useWD As Boolean: useWD = CfgOn("CFG_SHIFT_WORKDAYS_ONLY", False)
    
    Dim prevDur As Long
    prevDur = DateDiff("d", prevSt, prevEn)
    Dim en As Date
    
    If useWD Then
        Dim d As Long: d = LongOrDefault(ws.Cells(r, COL_DAYS).Value, prevDur + 1)
        If d < 1 Then d = 1
        en = AddDays(st, d - 1, True)
    Else
        en = AddDays(st, prevDur, False)
    End If
    
    ws.Cells(r, COL_END).Value2 = en
    SafeSetNumberFormat ws.Cells(r, COL_END), "yyyy-mm-dd"
End Sub

' ============================================================
' PROTECTION
' ============================================================
Private Sub SafeSetNumberFormat(ByVal targetCell As Range, ByVal fmt As String)
    On Error GoTo FirstFail
    targetCell.NumberFormat = fmt
    Exit Sub
    
FirstFail:
    Dim ws As Worksheet
    Dim wasProtected As Boolean
    Dim firstErrNo As Long
    Dim firstErrMsg As String
    
    firstErrNo = Err.Number
    firstErrMsg = Err.Description
    Err.Clear
    
    Set ws = targetCell.Worksheet
    wasProtected = ws.ProtectContents
    
    If Not wasProtected Then
        LogMsg "SafeSetNumberFormat", firstErrNo & " - " & firstErrMsg, ws.Name, targetCell.Row, targetCell.Column
        Exit Sub
    End If
    
    On Error Resume Next
    ws.Unprotect
    targetCell.NumberFormat = fmt
    
    If Err.Number <> 0 Then
        LogMsg "SafeSetNumberFormat", firstErrNo & "/" & Err.Number & " - " & firstErrMsg & " / " & Err.Description, ws.Name, targetCell.Row, targetCell.Column
        Err.Clear
    End If
    
    If ws.ProtectContents = False Then
        ApplyProtection ws, True
    End If
    On Error GoTo 0
End Sub

Private Sub ApplyStaticColumnVisibility(ByVal ws As Worksheet)
    On Error GoTo EH
    If ws Is Nothing Then Exit Sub
    
    ws.Columns(COL_STEP).Hidden = True
    ws.Columns(COL_PRED).Hidden = True
    ws.Columns(COL_LAG).Hidden = True
    Exit Sub
EH:
    LogMsg "ApplyStaticColumnVisibility", Err.Number & " - " & Err.Description, ws.Name
End Sub

Private Sub ApplyProtection(ByVal ws As Worksheet, ByVal doProtect As Boolean)
    On Error GoTo EH
    
    ws.Unprotect
    
    ws.Cells.Locked = True
    
    Dim r As Long, lastR As Long
    lastR = LastUsedRow(ws)
    For r = FIRST_DATA_ROW To lastR
        If IsGroupRow(ws, r) Then GoTo ContinueLoop
        ws.Cells(r, COL_START).Locked = False
        ws.Cells(r, COL_END).Locked = False
        ws.Cells(r, COL_DAYS).Locked = False
        ws.Cells(r, COL_RISK).Locked = False
        ws.Cells(r, COL_NOTE).Locked = False
ContinueLoop:
    Next r
    
    ApplyStaticColumnVisibility ws
    
    If doProtect Then
        ws.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, UserInterfaceOnly:=True, _
                   AllowFormattingCells:=True, AllowFormattingColumns:=False, AllowFormattingRows:=False, _
                   AllowInsertingColumns:=False, AllowInsertingRows:=False, AllowInsertingHyperlinks:=False, _
                   AllowDeletingColumns:=False, AllowDeletingRows:=False, AllowSorting:=True, AllowFiltering:=True, _
                   AllowUsingPivotTables:=False
        ws.EnableSelection = xlUnlockedCells
    End If
    
    Exit Sub
EH:
    LogMsg "ApplyProtection", Err.Number & " - " & Err.Description, ws.Name
End Sub

Private Sub EnsureGanttActionButtons(ByVal ws As Worksheet)
    On Error GoTo EH
    Dim topPos As Double
    Dim btnHeight As Double
    Dim btnGap As Double
    Dim initLeft As Double, resetLeft As Double, notesLeft As Double
    Dim initWidth As Double, resetWidth As Double, notesWidth As Double
    
    If ws Is Nothing Then Exit Sub
    If Not IsGanttSheet(ws) Then Exit Sub
    
    DeleteManagedButtons ws
    
    topPos = ws.Rows(1).Top + 6
    btnHeight = 20
    btnGap = 6
    
    initLeft = ws.Cells(1, COL_PHASE).Left + 6
    resetLeft = ws.Cells(1, COL_START).Left + 6
    notesLeft = ws.Cells(1, COL_DAYS).Left + 6
    
    initWidth = ws.Cells(1, COL_START).Left - initLeft - btnGap
    resetWidth = ws.Cells(1, COL_DAYS).Left - resetLeft - btnGap
    notesWidth = ws.Cells(1, COL_PRED).Left - notesLeft - btnGap
    
    If initWidth < 54 Then initWidth = 54
    If resetWidth < 54 Then resetWidth = 54
    If notesWidth < 78 Then notesWidth = 78
    
    UpsertActionButton ws, BTN_INIT_NAME, "Init", "modMIR_Gantt_Unified.Init_Unified_System", initLeft, topPos, initWidth, btnHeight, C_BLUE
    UpsertActionButton ws, BTN_RESET_NAME, "Reset", "modMIR_Gantt_Unified.Reset_Schedule_To_Original", resetLeft, topPos, resetWidth, btnHeight, C_RED
    UpsertActionButton ws, BTN_NOTES_NAME, CurrentNotesButtonCaption(ws), "modMIR_Gantt_Unified.Toggle_Notes_Action_Column", notesLeft, topPos, notesWidth, btnHeight, C_AMBER
    Exit Sub
EH:
    LogMsg "EnsureGanttActionButtons", Err.Number & " - " & Err.Description, ws.Name
End Sub

Private Sub DeleteManagedButtons(ByVal ws As Worksheet)
    On Error GoTo EH
    Dim i As Long
    Dim shp As Shape
    Dim btn As Object
    
    If ws Is Nothing Then Exit Sub
    For i = ws.Buttons.Count To 1 Step -1
        Set btn = ws.Buttons(i)
        If Left$(btn.Name, Len(BTN_PREFIX)) = BTN_PREFIX Then btn.Delete
    Next i
    For i = ws.Shapes.Count To 1 Step -1
        Set shp = ws.Shapes(i)
        If Left$(shp.Name, Len(BTN_PREFIX)) = BTN_PREFIX Then shp.Delete
    Next i
    Exit Sub
EH:
    LogMsg "DeleteManagedButtons", Err.Number & " - " & Err.Description, ws.Name
End Sub

Private Sub UpsertActionButton(ByVal ws As Worksheet, ByVal buttonName As String, ByVal caption As String, ByVal macroName As String, ByVal leftPos As Double, ByVal topPos As Double, ByVal widthPos As Double, ByVal heightPos As Double, ByVal fillHex As String)
    On Error GoTo EH
    Dim btn As Object
    
    On Error Resume Next
    ws.Buttons(buttonName).Delete
    Err.Clear
    On Error GoTo EH
    
    Set btn = ws.Buttons.Add(leftPos, topPos, widthPos, heightPos)
    With btn
        .Name = buttonName
        .OnAction = macroName
        .caption = caption
        .Placement = xlFreeFloating
        .PrintObject = False
    End With
    
    On Error Resume Next
    btn.Font.Bold = True
    btn.Font.Size = 9
    Err.Clear
    On Error GoTo EH
    Exit Sub
EH:
    LogMsg "UpsertActionButton", Err.Number & " - " & Err.Description, ws.Name
End Sub

Private Function CurrentNotesButtonCaption(ByVal ws As Worksheet) As String
    If ws Is Nothing Then
        CurrentNotesButtonCaption = "Hide Notes"
    ElseIf ws.Columns(COL_NOTE).Hidden Then
        CurrentNotesButtonCaption = "Show Notes"
    Else
        CurrentNotesButtonCaption = "Hide Notes"
    End If
End Function

' ============================================================
' HELPERS
' ============================================================
Private Function IsGanttSheet(ByVal ws As Worksheet) As Boolean
    IsGanttSheet = (UCase$(ws.Name) = UCase$(SHEET_BASE))
End Function

Private Function IsBlankish(ByVal v As Variant) As Boolean
    If IsEmpty(v) Then
        IsBlankish = True
    ElseIf VarType(v) = vbString Then
        IsBlankish = (Len(Trim$(v)) = 0)
    Else
        IsBlankish = False
    End If
End Function



Private Function IsEmptyTaskRow(ByVal ws As Worksheet, ByVal r As Long) As Boolean
    IsEmptyTaskRow = _
        IsBlankish(ws.Cells(r, COL_STEP).Value2) And _
        IsBlankish(ws.Cells(r, COL_PHASE).Value2) And _
        IsBlankish(ws.Cells(r, COL_TASK).Value2) And _
        IsBlankish(ws.Cells(r, COL_START).Value2) And _
        IsBlankish(ws.Cells(r, COL_END).Value2) And _
        IsBlankish(ws.Cells(r, COL_DAYS).Value2) And _
        IsBlankish(ws.Cells(r, COL_RISK).Value2) And _
        IsBlankish(ws.Cells(r, COL_NOTE).Value2)
End Function

Private Function IsGroupRow(ByVal ws As Worksheet, ByVal r As Long) As Boolean
    Dim marker As String
    marker = Trim$(CStr(ws.Cells(r, COL_STEP).Value2))

    If InStr(1, marker, ChrW(&H25B8), vbTextCompare) > 0 Then
        IsGroupRow = True
        Exit Function
    End If

    If ws.Cells(r, COL_STEP).MergeCells And marker <> "" And _
       IsBlankish(ws.Cells(r, COL_START).Value2) And IsBlankish(ws.Cells(r, COL_END).Value2) Then
        IsGroupRow = True
        Exit Function
    End If

    IsGroupRow = False
End Function

Private Function IsFixedRow(ByVal ws As Worksheet, ByVal r As Long) As Boolean
    Dim s As String
    s = UCase$(CStr(ws.Cells(r, COL_PHASE).Value) & " " & CStr(ws.Cells(r, COL_TASK).Value))
    IsFixedRow = (InStr(1, s, "FIXED", vbTextCompare) > 0)
End Function

Private Function IsLegacySheet(ByVal ws As Worksheet) As Boolean
    Dim nm As String
    nm = UCase$(ws.Name)
    IsLegacySheet = (nm = "BASELINE" Or nm = "GANTT_BEST" Or nm = "GANTT_WORST")
End Function

Private Sub ReportLegacySheetsOnce()
    On Error GoTo EH
    If gLegacySheetsReported Then Exit Sub
    
    Dim ws As Worksheet
    Dim legacyList As String
    
    For Each ws In ThisWorkbook.Worksheets
        If IsLegacySheet(ws) Then
            If Len(legacyList) > 0 Then legacyList = legacyList & ", "
            legacyList = legacyList & ws.Name
        End If
    Next ws
    
    If Len(legacyList) = 0 Then Exit Sub
    
    gLegacySheetsReported = True
    MsgBox "Legacy sheets are ignored in single-base manual mode: " & legacyList, vbInformation
    LogMsg "LegacySheets", "Ignored legacy sheets: " & legacyList
    Exit Sub
EH:
    LogMsg "LegacySheets", Err.Number & " - " & Err.Description
End Sub

Private Function StepExists(ByVal ws As Worksheet, ByVal stepId As String) As Boolean
    Dim r As Long, lastR As Long
    lastR = LastUsedRow(ws)
    For r = FIRST_DATA_ROW To lastR
        If Not IsGroupRow(ws, r) Then
            If UCase$(Trim$(CStr(ws.Cells(r, COL_STEP).Value2))) = UCase$(Trim$(stepId)) Then
                StepExists = True
                Exit Function
            End If
        End If
    Next r
    StepExists = False
End Function

Private Function LastUsedRow(ByVal ws As Worksheet) As Long
    Dim f As Range

    On Error Resume Next
    Set f = ws.Cells.Find(What:="*", After:=ws.Cells(1, 1), LookIn:=xlFormulas, LookAt:=xlPart, _
                          SearchOrder:=xlByRows, SearchDirection:=xlPrevious, MatchCase:=False)
    On Error GoTo 0

    If f Is Nothing Then
        LastUsedRow = FIRST_DATA_ROW
    Else
        LastUsedRow = f.Row
        If LastUsedRow < FIRST_DATA_ROW Then LastUsedRow = FIRST_DATA_ROW
    End If

    Set f = Nothing
End Function

Private Sub ResetTimelineSurface(ByVal ws As Worksheet, ByVal clearEndCol As Long, ByVal lastR As Long)
    On Error GoTo EH
    
    Dim bodyRng As Range
    Dim col As Long
    Dim headerD As Date
    Dim r As Long
    
    If clearEndCol < DATE_COL_START Then Exit Sub
    If lastR < FIRST_DATA_ROW Then Exit Sub
    
    Set bodyRng = ws.Range(ws.Cells(FIRST_DATA_ROW, DATE_COL_START), ws.Cells(lastR, clearEndCol))
    bodyRng.Interior.Color = HexToLong(BG_DARK)
    With bodyRng.Borders
        .LineStyle = xlContinuous
        .Weight = xlThin
        .Color = HexToLong(BORDER_HEX)
    End With
    
    For col = DATE_COL_START To clearEndCol
        If TryGetCellDate(ws.Cells(HEADER_ROW, col), headerD) Then
            If Weekday(headerD, vbMonday) >= 6 Then
                ws.Range(ws.Cells(FIRST_DATA_ROW, col), ws.Cells(lastR, col)).Interior.Color = HexToLong(BG_WEEKEND)
            End If
        End If
    Next col
    
    For r = FIRST_DATA_ROW To lastR
        If IsGroupRow(ws, r) Then
            ws.Range(ws.Cells(r, DATE_COL_START), ws.Cells(r, clearEndCol)).Interior.Color = HexToLong(BG_SURFACE2)
        End If
    Next r
    
    Set bodyRng = Nothing
    Exit Sub
EH:
    LogMsg "ResetTimelineSurface", Err.Number & " - " & Err.Description, ws.Name
    Set bodyRng = Nothing
End Sub

Private Function HeaderLastCol(ByVal ws As Worksheet) As Long
    Dim c As Long
    c = ws.Cells(HEADER_ROW, ws.Columns.Count).End(xlToLeft).Column
    If c < DATE_COL_START Then c = DATE_COL_START
    HeaderLastCol = c
End Function

Private Function HeaderFirstDate(ByVal ws As Worksheet) As Variant
    HeaderFirstDate = ws.Cells(HEADER_ROW, DATE_COL_START).Value
End Function

Private Function HeaderLastDate(ByVal ws As Worksheet) As Variant
    HeaderLastDate = ws.Cells(HEADER_ROW, HeaderLastCol(ws)).Value
End Function

Private Function CfListSep() As String
    ' Conditional Formatting formulas must use the workbook list separator (e.g. ";" on KO/DE Excel).
    CfListSep = Application.International(xlListSeparator)
    If Len(CfListSep) <> 1 Then CfListSep = ","
End Function

Private Function ColLetter(ByVal colNum As Long) As String
    ColLetter = Split(Cells(1, colNum).Address(True, False), "$")(1)
End Function

Private Sub SetThinBorder(ByVal cell As Range)
    With cell.Borders
        .LineStyle = xlContinuous
        .Weight = xlThin
        .Color = HexToLong(BORDER_HEX)
    End With
End Sub

Private Function PhaseColorLong(ByVal phase As String) As Long
    Dim s As String: s = UCase$(phase)
    Select Case True
        Case InStr(1, s, "DOC", vbTextCompare) > 0
            PhaseColorLong = HexToLong(C_BLUE)
        Case InStr(1, s, "PICKUP", vbTextCompare) > 0
            PhaseColorLong = HexToLong(C_BLUE)
        Case InStr(1, s, "UAE_REP", vbTextCompare) > 0
            PhaseColorLong = HexToLong(C_PURPLE)
        Case InStr(1, s, "TRANS_OUT", vbTextCompare) > 0
            PhaseColorLong = HexToLong(C_ORANGE)
        Case InStr(1, s, "KSA_REP", vbTextCompare) > 0
            PhaseColorLong = HexToLong(C_PINK)
        Case InStr(1, s, "TRANS_BACK", vbTextCompare) > 0
            PhaseColorLong = HexToLong(C_GREEN)
        Case InStr(1, s, "FINAL", vbTextCompare) > 0
            PhaseColorLong = HexToLong(C_YELLOW)
        Case Else
            PhaseColorLong = HexToLong(C_AMBER)
    End Select
End Function

Public Function HexToLong(ByVal hex As String) As Long
    hex = Replace(hex, "#", "")
    Dim r As Long, g As Long, b As Long
    r = CLng("&H" & Mid$(hex, 1, 2))
    g = CLng("&H" & Mid$(hex, 3, 2))
    b = CLng("&H" & Mid$(hex, 5, 2))
    HexToLong = RGB(r, g, b)
End Function

Private Function Nz(ByVal v As Variant, ByVal defaultValue As Variant) As Variant
    If IsError(v) Or IsEmpty(v) Or v = "" Then
        Nz = defaultValue
    Else
        Nz = v
    End If
End Function

Private Function LongOrDefault(ByVal v As Variant, ByVal defaultValue As Long) As Long
    On Error GoTo SafeDefault
    If IsError(v) Or IsEmpty(v) Then GoTo SafeDefault
    
    If IsNumeric(v) Then
        LongOrDefault = CLng(v)
        Exit Function
    End If
    
    Dim s As String
    s = Trim$(CStr(v))
    If Len(s) = 0 Then GoTo SafeDefault
    If IsNumeric(s) Then
        LongOrDefault = CLng(CDbl(s))
        Exit Function
    End If
    
SafeDefault:
    LongOrDefault = defaultValue
End Function

Private Function SplitPred(ByVal s As String) As Variant
    s = Replace(s, ";", ",")
    s = Replace(s, " ", "")
    If s = "" Then
        SplitPred = Array()
    Else
        SplitPred = Split(s, ",")
    End If
End Function

Private Function HolidayDateKey(ByVal d As Date) As String
    HolidayDateKey = CStr(CLng(DateSerial(Year(d), Month(d), Day(d))))
End Function

Private Function HolidayLookup() As Object
    On Error GoTo EH
    Dim payload As String
    Dim parts As Variant
    Dim token As Variant
    Dim holidayDate As Date
    
    payload = Trim$(GetHiddenTextName(HOLIDAY_CFG_NAME, ""))
    If gHolidayLookup Is Nothing Or payload <> gHolidayLookupSource Then
        Set gHolidayLookup = CreateObject("Scripting.Dictionary")
        gHolidayLookupSource = payload
        
        If Len(payload) > 0 Then
            parts = Split(payload, ",")
            For Each token In parts
                If ParseDashedDate(Trim$(CStr(token)), holidayDate) Then
                    gHolidayLookup(HolidayDateKey(holidayDate)) = True
                End If
            Next token
        End If
    End If
    
    Set HolidayLookup = gHolidayLookup
    Exit Function
EH:
    LogMsg "HolidayLookup", Err.Number & " - " & Err.Description
    Set HolidayLookup = Nothing
End Function

Private Function IsConfiguredHoliday(ByVal d As Date) As Boolean
    Dim dict As Object
    Set dict = HolidayLookup()
    If dict Is Nothing Then Exit Function
    IsConfiguredHoliday = dict.Exists(HolidayDateKey(d))
End Function

Private Function IsWorkday(ByVal d As Date) As Boolean
    IsWorkday = (Weekday(d, vbMonday) <= 5 And Not IsConfiguredHoliday(d))
End Function

Private Function NormalizeToWorkday(ByVal d As Date) As Date
    Do While Not IsWorkday(d)
        d = DateAdd("d", 1, d)
    Loop
    NormalizeToWorkday = d
End Function

Private Function AddWorkdays(ByVal d As Date, ByVal n As Long) As Date
    Dim stepDir As Long
    Dim i As Long
    Dim cur As Date: cur = d
    
    If n = 0 Then
        AddWorkdays = NormalizeToWorkday(cur)
        Exit Function
    End If
    
    stepDir = IIf(n > 0, 1, -1)
    i = 0
    Do While i <> n
        cur = DateAdd("d", stepDir, cur)
        If IsWorkday(cur) Then
            i = i + stepDir
        End If
    Loop
    AddWorkdays = cur
End Function

Private Function AddDays(ByVal d As Date, ByVal n As Long, ByVal useWorkdays As Boolean) As Date
    If useWorkdays Then
        AddDays = AddWorkdays(d, n)
    Else
        AddDays = DateAdd("d", n, d)
    End If
End Function

Private Function WorkdayDiff(ByVal d1 As Date, ByVal d2 As Date) As Long
    Dim n As Long: n = 0
    Dim cur As Date: cur = d1
    Dim dir As Long
    
    If d2 = d1 Then
        WorkdayDiff = 0
        Exit Function
    End If
    
    dir = IIf(d2 > d1, 1, -1)
    Do While cur <> d2
        cur = DateAdd("d", dir, cur)
        If IsWorkday(cur) Then
            n = n + dir
        End If
        If Abs(n) > 4000 Then Exit Do
    Loop
    
    WorkdayDiff = n
End Function

' ============================================================
' CONFIG READERS (named ranges)
' ============================================================
Private Function CfgText(ByVal cfgName As String, ByVal defaultValue As String) As String
    On Error GoTo Safe
    CfgText = CStr(ThisWorkbook.Names(cfgName).RefersToRange.Value)
    If Trim$(CfgText) = "" Then CfgText = defaultValue
    Exit Function
Safe:
    CfgText = defaultValue
End Function

Private Function CfgOn(ByVal cfgName As String, ByVal defaultValue As Boolean) As Boolean
    Dim v As String
    v = UCase$(Trim$(CfgText(cfgName, IIf(defaultValue, "ON", "OFF"))))
    CfgOn = (v = "ON" Or v = "TRUE" Or v = "1" Or v = "YES")
End Function

' ============================================================
' ORIGINAL SCHEDULE SNAPSHOT
' ============================================================
Private Sub EnsureUidScheduleSnapshot(ByVal ws As Worksheet, Optional ByVal overwrite As Boolean = False)
    On Error GoTo EH
    Dim r As Long, lastR As Long
    Dim taskIndex As Long
    Dim uid As String
    Dim st As Date, en As Date
    Dim days As Long
    Dim payload As String
    
    If ws Is Nothing Then Exit Sub
    If Not overwrite And UidScheduleMetadataReady() Then Exit Sub
    
    ClearUidScheduleMetadata
    lastR = LastUsedRow(ws)
    
    For r = FIRST_DATA_ROW To lastR
        If IsGroupRow(ws, r) Then GoTo ContinueLoop
        If IsBlankish(ws.Cells(r, COL_STEP).Value2) And IsBlankish(ws.Cells(r, COL_TASK).Value2) Then GoTo ContinueLoop
        If Not (TryGetCellDate(ws.Cells(r, COL_START), st) And TryGetCellDate(ws.Cells(r, COL_END), en)) Then GoTo ContinueLoop
        
        days = LongOrDefault(ws.Cells(r, COL_DAYS).Value2, DateDiff("d", st, en) + 1)
        If days < 1 Then days = DateDiff("d", st, en) + 1
        
        taskIndex = taskIndex + 1
        uid = Format$(taskIndex, "0000")
        SetHiddenRangeName UidRowName(uid), ws.Cells(r, COL_STEP)
        payload = Format$(st, "yyyy-mm-dd") & "|" & Format$(en, "yyyy-mm-dd") & "|" & CStr(days)
        SetHiddenTextName UidOrigName(uid), payload
ContinueLoop:
    Next r
    
    If taskIndex > 0 Then LogMsg "EnsureUidScheduleSnapshot", "Captured " & taskIndex & " task rows", ws.Name
    Exit Sub
EH:
    LogMsg "EnsureUidScheduleSnapshot", Err.Number & " - " & Err.Description, ws.Name
End Sub

Private Function UidScheduleMetadataReady() As Boolean
    On Error GoTo EH
    Dim nm As Name
    Dim key As String
    Dim uid As String
    Dim rowCount As Long
    Dim origCount As Long
    
    For Each nm In ThisWorkbook.Names
        key = UCase$(SimpleNameKey(nm.Name))
        If Left$(key, Len(UID_ROW_NAME_PREFIX)) = UID_ROW_NAME_PREFIX Then
            uid = Mid$(key, Len(UID_ROW_NAME_PREFIX) + 1)
            rowCount = rowCount + 1
            If Len(GetHiddenTextName(UidOrigName(uid), "")) > 0 Then origCount = origCount + 1
        End If
    Next nm
    
    UidScheduleMetadataReady = (rowCount > 0 And rowCount = origCount)
    Exit Function
EH:
    LogMsg "UidScheduleMetadataReady", Err.Number & " - " & Err.Description
End Function

Private Sub EnsureOriginalTimelineRangeSnapshot(ByVal ws As Worksheet, Optional ByVal overwrite As Boolean = False)
    On Error GoTo EH
    Dim minD As Date
    Dim maxD As Date
    Dim payload As String
    
    If ws Is Nothing Then Exit Sub
    If Not overwrite Then
        If TryGetOriginalTimelineRange(minD, maxD) Then Exit Sub
    End If
    
    GetMinMaxDates ws, minD, maxD
    payload = Format$(minD, "yyyy-mm-dd") & "|" & Format$(maxD, "yyyy-mm-dd")
    SetHiddenTextName ORIG_TIMELINE_RANGE_NAME, payload
    Exit Sub
EH:
    LogMsg "EnsureOriginalTimelineRangeSnapshot", Err.Number & " - " & Err.Description, ws.Name
End Sub

Private Function TryGetOriginalTimelineRange(ByRef firstD As Date, ByRef lastD As Date) As Boolean
    On Error GoTo EH
    Dim payload As String
    Dim parts As Variant
    
    payload = Trim$(GetHiddenTextName(ORIG_TIMELINE_RANGE_NAME, ""))
    If Len(payload) = 0 Then Exit Function
    
    parts = Split(payload, "|")
    If UBound(parts) < 1 Then Exit Function
    If Not ParseDashedDate(CStr(parts(0)), firstD) Then Exit Function
    If Not ParseDashedDate(CStr(parts(1)), lastD) Then Exit Function
    If lastD < firstD Then Exit Function
    
    TryGetOriginalTimelineRange = True
    Exit Function
EH:
    LogMsg "TryGetOriginalTimelineRange", Err.Number & " - " & Err.Description
End Function

Private Function RestoreOriginalSchedule(ByVal ws As Worksheet) As Long
    On Error GoTo EH
    Dim nm As Name
    Dim key As String
    Dim uid As String
    Dim payload As String
    Dim anchorCell As Range
    Dim origStart As Date, origEnd As Date
    Dim origDays As Long
    
    For Each nm In ThisWorkbook.Names
        key = UCase$(SimpleNameKey(nm.Name))
        If Left$(key, Len(UID_ROW_NAME_PREFIX)) <> UID_ROW_NAME_PREFIX Then GoTo ContinueLoop
        
        uid = Mid$(SimpleNameKey(nm.Name), Len(UID_ROW_NAME_PREFIX) + 1)
        payload = GetHiddenTextName(UidOrigName(uid), "")
        If Len(payload) = 0 Then
            LogMsg "RestoreOriginalSchedule", "Missing original payload for UID " & uid, ws.Name
            GoTo ContinueLoop
        End If
        If Not TryParseOriginalSchedulePayload(payload, origStart, origEnd, origDays) Then GoTo ContinueLoop
        
        Set anchorCell = Nothing
        On Error Resume Next
        Set anchorCell = nm.RefersToRange
        On Error GoTo EH
        
        If anchorCell Is Nothing Then
            LogMsg "RestoreOriginalSchedule", "Stale row anchor for UID " & uid, ws.Name
            GoTo ContinueLoop
        End If
        If UCase$(anchorCell.Worksheet.Name) <> UCase$(ws.Name) Then GoTo ContinueLoop
        If anchorCell.Row < FIRST_DATA_ROW Then GoTo ContinueLoop
        If IsGroupRow(ws, anchorCell.Row) Then GoTo ContinueLoop
        
        ws.Cells(anchorCell.Row, COL_START).Value2 = origStart
        ws.Cells(anchorCell.Row, COL_END).Value2 = origEnd
        ws.Cells(anchorCell.Row, COL_DAYS).Value2 = origDays
        SafeSetNumberFormat ws.Cells(anchorCell.Row, COL_START), "yyyy-mm-dd"
        SafeSetNumberFormat ws.Cells(anchorCell.Row, COL_END), "yyyy-mm-dd"
        RestoreOriginalSchedule = RestoreOriginalSchedule + 1
ContinueLoop:
        Set anchorCell = Nothing
    Next nm
    
    Exit Function
EH:
    LogMsg "RestoreOriginalSchedule", Err.Number & " - " & Err.Description, ws.Name
End Function

Private Function TryParseOriginalSchedulePayload(ByVal payload As String, ByRef st As Date, ByRef en As Date, ByRef days As Long) As Boolean
    On Error GoTo EH
    Dim parts As Variant
    
    parts = Split(payload, "|")
    If UBound(parts) < 2 Then Exit Function
    If Not ParseDashedDate(CStr(parts(0)), st) Then Exit Function
    If Not ParseDashedDate(CStr(parts(1)), en) Then Exit Function
    
    days = LongOrDefault(parts(2), DateDiff("d", st, en) + 1)
    If days < 1 Then days = DateDiff("d", st, en) + 1
    TryParseOriginalSchedulePayload = True
    Exit Function
EH:
    LogMsg "TryParseOriginalSchedulePayload", Err.Number & " - " & Err.Description
End Function

Private Function UidRowName(ByVal uid As String) As String
    UidRowName = UID_ROW_NAME_PREFIX & uid
End Function

Private Function UidOrigName(ByVal uid As String) As String
    UidOrigName = UID_ORIG_NAME_PREFIX & uid
End Function

Private Sub ClearUidScheduleMetadata()
    On Error GoTo EH
    Dim i As Long
    Dim key As String
    
    For i = ThisWorkbook.Names.Count To 1 Step -1
        key = UCase$(SimpleNameKey(ThisWorkbook.Names(i).Name))
        If Left$(key, Len(UID_ROW_NAME_PREFIX)) = UID_ROW_NAME_PREFIX Or Left$(key, Len(UID_ORIG_NAME_PREFIX)) = UID_ORIG_NAME_PREFIX Then
            ThisWorkbook.Names(i).Delete
        End If
    Next i
    Exit Sub
EH:
    LogMsg "ClearUidScheduleMetadata", Err.Number & " - " & Err.Description
End Sub

Private Sub SetHiddenRangeName(ByVal nameKey As String, ByVal targetCell As Range)
    On Error GoTo EH
    Dim refersTo As String
    
    On Error Resume Next
    ThisWorkbook.Names(nameKey).Delete
    Err.Clear
    On Error GoTo EH
    
    refersTo = "=" & "'" & targetCell.Worksheet.Name & "'!" & targetCell.Address(True, True, xlA1)
    ThisWorkbook.Names.Add Name:=nameKey, refersTo:=refersTo
    ThisWorkbook.Names(nameKey).Visible = False
    Exit Sub
EH:
    LogMsg "SetHiddenRangeName", Err.Number & " - " & Err.Description, nameKey
End Sub

Private Sub SetHiddenTextName(ByVal nameKey As String, ByVal textValue As String)
    On Error GoTo EH
    Dim escaped As String
    
    On Error Resume Next
    ThisWorkbook.Names(nameKey).Delete
    Err.Clear
    On Error GoTo EH
    
    escaped = Replace(textValue, """", """""")
    ThisWorkbook.Names.Add Name:=nameKey, refersTo:="=""" & escaped & """"
    ThisWorkbook.Names(nameKey).Visible = False
    Exit Sub
EH:
    LogMsg "SetHiddenTextName", Err.Number & " - " & Err.Description, nameKey
End Sub

Private Function GetHiddenTextName(ByVal nameKey As String, Optional ByVal defaultValue As String = "") As String
    On Error GoTo Safe
    GetHiddenTextName = CStr(Application.Evaluate(ThisWorkbook.Names(nameKey).refersTo))
    If Len(GetHiddenTextName) = 0 Then GetHiddenTextName = defaultValue
    Exit Function
Safe:
    GetHiddenTextName = defaultValue
End Function

Private Sub EnsureBuildMetadataDefaults()
    On Error GoTo EH
    If Len(GetHiddenTextName(BUILD_TIMESTAMP_NAME, "")) = 0 Then SetHiddenTextName BUILD_TIMESTAMP_NAME, "manual"
    If Len(GetHiddenTextName(BUILD_BAS_TIMESTAMP_NAME, "")) = 0 Then SetHiddenTextName BUILD_BAS_TIMESTAMP_NAME, "manual"
    If Len(GetHiddenTextName(BUILD_HOOK_TIMESTAMP_NAME, "")) = 0 Then SetHiddenTextName BUILD_HOOK_TIMESTAMP_NAME, "manual"
    If Len(GetHiddenTextName(BUILD_TOKEN_NAME, "")) = 0 Then SetHiddenTextName BUILD_TOKEN_NAME, "manual"
    Exit Sub
EH:
    LogMsg "EnsureBuildMetadataDefaults", Err.Number & " - " & Err.Description
End Sub

Private Function SimpleNameKey(ByVal fullName As String) As String
    Dim pos As Long
    pos = InStrRev(fullName, "!")
    If pos > 0 Then
        SimpleNameKey = Mid$(fullName, pos + 1)
    Else
        SimpleNameKey = fullName
    End If
End Function

Private Function ColumnAuditName(ByVal colNum As Long) As String
    Select Case colNum
        Case COL_START
            ColumnAuditName = "Start"
        Case COL_END
            ColumnAuditName = "End"
        Case COL_DAYS
            ColumnAuditName = "Days"
        Case COL_RISK
            ColumnAuditName = "Risk"
        Case COL_NOTE
            ColumnAuditName = "Notes"
        Case Else
            ColumnAuditName = "Col" & CStr(colNum)
    End Select
End Function

Private Function CompactAuditText(ByVal textValue As String, ByVal maxLen As Long) As String
    Dim s As String
    s = Trim$(textValue)
    s = Replace(s, vbCrLf, " / ")
    s = Replace(s, vbCr, " / ")
    s = Replace(s, vbLf, " / ")
    If maxLen < 4 Then maxLen = 4
    If Len(s) > maxLen Then s = Left$(s, maxLen - 3) & "..."
    CompactAuditText = s
End Function

Private Function AuditScalar(ByVal v As Variant) As String
    On Error GoTo EH
    If IsError(v) Then
        AuditScalar = "#ERR"
        Exit Function
    End If
    If IsEmpty(v) Then
        AuditScalar = "-"
        Exit Function
    End If
    
    Dim s As String
    s = Trim$(CStr(v))
    If Len(s) = 0 Then
        AuditScalar = "-"
        Exit Function
    End If
    
    AuditScalar = CompactAuditText(s, 120)
    Exit Function
EH:
    AuditScalar = "#ERR"
End Function

Private Function AuditDateValue(ByVal v As Variant) As String
    Dim d As Date
    If TryParseDateValue(v, d) Then
        AuditDateValue = Format$(d, "yyyy-mm-dd")
    Else
        AuditDateValue = AuditScalar(v)
    End If
End Function

Private Function AuditFieldValue(ByVal colNum As Long, ByVal v As Variant) As String
    Select Case colNum
        Case COL_START, COL_END
            AuditFieldValue = AuditDateValue(v)
        Case Else
            AuditFieldValue = AuditScalar(v)
    End Select
End Function

Private Sub LogScheduleEdit(ByVal ws As Worksheet, ByVal r As Long, ByVal editedCol As Long, _
    ByVal beforeValue As Variant, ByVal beforeStart As Variant, ByVal beforeEnd As Variant, _
    ByVal beforeDays As Variant, ByVal beforeRisk As Variant, ByVal beforeNote As Variant)
    On Error GoTo EH
    
    Dim afterStart As Variant
    Dim afterEnd As Variant
    Dim afterDays As Variant
    Dim afterRisk As Variant
    Dim afterNote As Variant
    Dim stepId As String
    Dim taskText As String
    Dim msg As String
    
    afterStart = ws.Cells(r, COL_START).Value2
    afterEnd = ws.Cells(r, COL_END).Value2
    afterDays = ws.Cells(r, COL_DAYS).Value2
    afterRisk = ws.Cells(r, COL_RISK).Value2
    afterNote = ws.Cells(r, COL_NOTE).Value2
    
    If AuditDateValue(beforeStart) = AuditDateValue(afterStart) _
        And AuditDateValue(beforeEnd) = AuditDateValue(afterEnd) _
        And AuditScalar(beforeDays) = AuditScalar(afterDays) _
        And AuditScalar(beforeRisk) = AuditScalar(afterRisk) _
        And AuditScalar(beforeNote) = AuditScalar(afterNote) Then
        Exit Sub
    End If
    
    stepId = AuditScalar(ws.Cells(r, COL_STEP).Value2)
    taskText = CompactAuditText(CStr(ws.Cells(r, COL_TASK).Value2), 48)
    
    msg = "step=" & stepId & _
          " task=" & taskText & _
          " field=" & ColumnAuditName(editedCol) & _
          " cell=" & AuditFieldValue(editedCol, beforeValue) & " -> " & AuditFieldValue(editedCol, ws.Cells(r, editedCol).Value2) & _
          " | start=" & AuditDateValue(beforeStart) & " -> " & AuditDateValue(afterStart) & _
          " | end=" & AuditDateValue(beforeEnd) & " -> " & AuditDateValue(afterEnd) & _
          " | days=" & AuditScalar(beforeDays) & " -> " & AuditScalar(afterDays) & _
          " | risk=" & AuditScalar(beforeRisk) & " -> " & AuditScalar(afterRisk)
    
    If editedCol = COL_NOTE Then
        msg = msg & " | note=" & CompactAuditText(AuditScalar(afterNote), 80)
    End If
    
    LogMsg "ScheduleEdit", msg, ws.Name, r, editedCol
    Exit Sub
EH:
    LogMsg "ScheduleEdit", Err.Number & " - " & Err.Description, ws.Name, r, editedCol
End Sub

Private Sub WriteSummaryMetricRow(ByVal ws As Worksheet, ByVal rowNum As Long, ByVal labelText As String, ByVal valueText As String, ByVal detailText As String)
    ws.Cells(rowNum, 1).Value2 = labelText
    ws.Cells(rowNum, 2).Value2 = valueText
    ws.Cells(rowNum, 3).Value2 = detailText
End Sub

Private Sub RefreshSummaryDashboard(Optional ByVal sourceProc As String = "")
    On Error GoTo EH
    
    Dim summaryWs As Worksheet
    Dim baseWs As Worksheet
    Dim logWs As Worksheet
    Dim prevEvents As Boolean
    Dim prevScreenUpdating As Boolean
    Dim prevCalc As XlCalculation
    Dim lastR As Long
    Dim r As Long
    Dim activeCount As Long
    Dim remainingCount As Long
    Dim highCount As Long
    Dim amberCount As Long
    Dim upcomingCount As Long
    Dim minD As Date
    Dim maxD As Date
    Dim rowStart As Date
    Dim rowEnd As Date
    Dim nextStart As Date
    Dim nextStep As String
    Dim nextTask As String
    Dim notesState As String
    Dim buildToken As String
    Dim riskText As String
    Dim haveNext As Boolean
    Dim lastLogRow As Long
    Dim lastProc As String
    Dim lastLogTime As String
    Dim logStamp As Date
    Dim writeRow As Long
    Dim srcLogRow As Long
    
    prevEvents = Application.EnableEvents
    prevScreenUpdating = Application.ScreenUpdating
    prevCalc = Application.Calculation
    Application.EnableEvents = False
    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual
    
    On Error Resume Next
    Set summaryWs = ThisWorkbook.Worksheets(SHEET_SUMMARY)
    Set baseWs = ThisWorkbook.Worksheets(SHEET_BASE)
    On Error GoTo EH
    If summaryWs Is Nothing Or baseWs Is Nothing Then GoTo SafeExit
    
    Set logWs = EnsureLogSheet()
    GetMinMaxDates baseWs, minD, maxD
    lastR = LastUsedRow(baseWs)
    
    For r = FIRST_DATA_ROW To lastR
        If IsGroupRow(baseWs, r) Or IsEmptyTaskRow(baseWs, r) Then GoTo ContinueLoop
        
        riskText = UCase$(Trim$(CStr(baseWs.Cells(r, COL_RISK).Value2)))
        Select Case riskText
            Case "HIGH"
                highCount = highCount + 1
            Case "AMBER"
                amberCount = amberCount + 1
        End Select
        
        If TryGetCellDate(baseWs.Cells(r, COL_START), rowStart) And TryGetCellDate(baseWs.Cells(r, COL_END), rowEnd) Then
            If Date >= rowStart And Date <= rowEnd Then activeCount = activeCount + 1
            If rowEnd >= Date Then remainingCount = remainingCount + 1
            If rowStart >= Date And rowStart <= DateAdd("d", 7, Date) Then upcomingCount = upcomingCount + 1
            If rowStart >= Date Then
                If Not haveNext Or rowStart < nextStart Then
                    haveNext = True
                    nextStart = rowStart
                    nextStep = AuditScalar(baseWs.Cells(r, COL_STEP).Value2)
                    nextTask = CompactAuditText(CStr(baseWs.Cells(r, COL_TASK).Value2), 48)
                End If
            End If
        End If
ContinueLoop:
    Next r
    
    notesState = IIf(baseWs.Columns(COL_NOTE).Hidden, "Hidden", "Visible")
    buildToken = CompactAuditText(GetHiddenTextName(BUILD_TOKEN_NAME, "manual"), 48)
    
    lastLogRow = logWs.Cells(logWs.Rows.Count, 1).End(xlUp).Row
    If lastLogRow >= 2 Then
        lastProc = AuditScalar(logWs.Cells(lastLogRow, 2).Value2)
        If TryParseDateValue(logWs.Cells(lastLogRow, 1).Value2, logStamp) Then
            lastLogTime = Format$(logStamp, "yyyy-mm-dd hh:mm")
        End If
    Else
        lastProc = "-"
        lastLogTime = "-"
    End If
    
    With summaryWs.Range("A" & DASHBOARD_START_ROW & ":C" & DASHBOARD_RECENT_LAST_ROW)
        .UnMerge
        .Clear
        .Font.Name = "Calibri"
        .Font.Size = 10
        .WrapText = True
        .HorizontalAlignment = xlLeft
        .VerticalAlignment = xlCenter
        .Borders.LineStyle = xlContinuous
        .Borders.Color = HexToLong(BORDER_HEX)
    End With
    
    summaryWs.Range("A" & DASHBOARD_START_ROW & ":C" & DASHBOARD_START_ROW).Merge
    summaryWs.Range("A" & DASHBOARD_START_ROW).Value2 = "Operational Dashboard"
    If Len(sourceProc) > 0 Then
        summaryWs.Range("A" & DASHBOARD_START_ROW).Value2 = "Operational Dashboard | " & sourceProc
    End If
    summaryWs.Range("A" & DASHBOARD_START_ROW & ":C" & DASHBOARD_START_ROW).Interior.Color = HexToLong(C_BLUE)
    summaryWs.Range("A" & DASHBOARD_START_ROW & ":C" & DASHBOARD_START_ROW).Font.Bold = True
    summaryWs.Range("A" & DASHBOARD_START_ROW & ":C" & DASHBOARD_START_ROW).Font.Color = HexToLong(BG_DARK)
    
    WriteSummaryMetricRow summaryWs, DASHBOARD_START_ROW + 1, "Generated", Format$(Now, "yyyy-mm-dd hh:mm"), "Trigger: " & IIf(Len(sourceProc) > 0, sourceProc, "manual")
    WriteSummaryMetricRow summaryWs, DASHBOARD_START_ROW + 2, "Timeline", Format$(minD, "yyyy-mm-dd") & " -> " & Format$(maxD, "yyyy-mm-dd"), "Days: " & CStr(DateDiff("d", minD, maxD) + 1)
    WriteSummaryMetricRow summaryWs, DASHBOARD_START_ROW + 3, "Active Today", CStr(activeCount), "Remaining: " & CStr(remainingCount)
    If haveNext Then
        WriteSummaryMetricRow summaryWs, DASHBOARD_START_ROW + 4, "Next Task", nextStep & " | " & nextTask, "Start: " & Format$(nextStart, "yyyy-mm-dd")
    Else
        WriteSummaryMetricRow summaryWs, DASHBOARD_START_ROW + 4, "Next Task", "No future task", "-"
    End If
    WriteSummaryMetricRow summaryWs, DASHBOARD_START_ROW + 5, "Risk Status", "HIGH: " & CStr(highCount), "AMBER: " & CStr(amberCount)
    WriteSummaryMetricRow summaryWs, DASHBOARD_START_ROW + 6, "Upcoming 7D", CStr(upcomingCount), "Notes: " & notesState
    WriteSummaryMetricRow summaryWs, DASHBOARD_START_ROW + 7, "Build Token", buildToken, "Last log: " & lastProc & IIf(Len(lastLogTime) > 0, " @ " & lastLogTime, "")
    
    summaryWs.Range("A" & DASHBOARD_RECENT_HEADER_ROW & ":C" & DASHBOARD_RECENT_HEADER_ROW).Merge
    summaryWs.Range("A" & DASHBOARD_RECENT_HEADER_ROW).Value2 = "Recent Activity"
    summaryWs.Range("A" & DASHBOARD_RECENT_HEADER_ROW & ":C" & DASHBOARD_RECENT_HEADER_ROW).Interior.Color = HexToLong(C_AMBER)
    summaryWs.Range("A" & DASHBOARD_RECENT_HEADER_ROW & ":C" & DASHBOARD_RECENT_HEADER_ROW).Font.Bold = True
    summaryWs.Range("A" & DASHBOARD_RECENT_HEADER_ROW & ":C" & DASHBOARD_RECENT_HEADER_ROW).Font.Color = HexToLong(BG_DARK)
    summaryWs.Range("A" & (DASHBOARD_START_ROW + 1) & ":A" & (DASHBOARD_START_ROW + 7)).Font.Bold = True
    
    writeRow = DASHBOARD_RECENT_FIRST_ROW
    For srcLogRow = lastLogRow To 2 Step -1
        summaryWs.Cells(writeRow, 1).Value2 = logWs.Cells(srcLogRow, 1).Value2
        summaryWs.Cells(writeRow, 1).NumberFormat = "yyyy-mm-dd hh:mm"
        summaryWs.Cells(writeRow, 2).Value2 = AuditScalar(logWs.Cells(srcLogRow, 2).Value2)
        summaryWs.Cells(writeRow, 3).Value2 = CompactAuditText(CStr(logWs.Cells(srcLogRow, 6).Value2), 96)
        writeRow = writeRow + 1
        If writeRow > DASHBOARD_RECENT_LAST_ROW Then Exit For
    Next srcLogRow
    
    Do While writeRow <= DASHBOARD_RECENT_LAST_ROW
        summaryWs.Cells(writeRow, 1).Value2 = "-"
        summaryWs.Cells(writeRow, 2).Value2 = "-"
        summaryWs.Cells(writeRow, 3).Value2 = ""
        writeRow = writeRow + 1
    Loop
    
    summaryWs.Range("A" & DASHBOARD_START_ROW & ":C" & DASHBOARD_RECENT_LAST_ROW).Rows.AutoFit
    
SafeExit:
    Application.Calculation = prevCalc
    Application.ScreenUpdating = prevScreenUpdating
    Application.EnableEvents = prevEvents
    Exit Sub
EH:
    LogMsg "RefreshSummaryDashboard", Err.Number & " - " & Err.Description
    Resume SafeExit
End Sub

' ============================================================
' LOG
' ============================================================

Private Function EnsureLogSheet() As Worksheet
    On Error Resume Next
    Set EnsureLogSheet = ThisWorkbook.Worksheets("LOG")
    On Error GoTo 0

    If EnsureLogSheet Is Nothing Then
        Set EnsureLogSheet = ThisWorkbook.Worksheets.Add(After:=ThisWorkbook.Worksheets(ThisWorkbook.Worksheets.Count))
        EnsureLogSheet.Name = "LOG"
    End If

    If Len(CStr(EnsureLogSheet.Cells(1, 1).Value2)) = 0 Then
        EnsureLogSheet.Range("A1:F1").Value = Array("Timestamp", "Proc", "Sheet", "Row", "Col", "Message")
        EnsureLogSheet.Rows(1).Font.Bold = True
    End If
End Function


Public Sub LogMsg(ByVal proc As String, ByVal msg As String, Optional ByVal sheetName As String = "", Optional ByVal rowNum As Long = 0, Optional ByVal colNum As Long = 0)
    On Error Resume Next
    Dim ws As Worksheet
    Set ws = EnsureLogSheet()

    Dim userName As String
    userName = Environ$("USERNAME")

    Dim n As Long
    n = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row + 1

    ws.Cells(n, 1).Value = Format$(Now, "yyyy-mm-dd hh:mm:ss")
    ws.Cells(n, 2).Value2 = proc
    ws.Cells(n, 3).Value2 = sheetName
    ws.Cells(n, 4).Value2 = rowNum
    ws.Cells(n, 5).Value2 = colNum
    ws.Cells(n, 6).Value2 = "[" & userName & "] " & msg
End Sub

Public Sub Force_Refresh_Colors()
    ' Manual color refresh for active Gantt sheet
    On Error GoTo EH
    Dim ws As Worksheet
    Dim wasProtected As Boolean
    Set ws = ActiveSheet
    
    If Not IsGanttSheet(ws) Then
        MsgBox "Active sheet is not " & SHEET_BASE & ".", vbExclamation
        Exit Sub
    End If
    
    BeginSheetWrite ws, wasProtected
    
    Dim minD As Date, maxD As Date
    GetMinMaxDates ws, minD, maxD
    
    ' Clear existing formatting
    On Error Resume Next
    ws.Unprotect
    Dim lastR As Long: lastR = LastUsedRow(ws)
    Dim endCol As Long: endCol = HeaderLastCol(ws)
    ws.Range(ws.Cells(FIRST_DATA_ROW, DATE_COL_START), ws.Cells(lastR, endCol)).Interior.ColorIndex = xlNone
    ws.Range(ws.Cells(FIRST_DATA_ROW, DATE_COL_START), ws.Cells(lastR, endCol)).FormatConditions.Delete
    On Error GoTo EH
    
    ' Rebuild colors using the current repaint mode.
    RefreshGantt ws, False
    
    If wasProtected Then EndSheetWrite ws, wasProtected
    
    MsgBox "Color formatting refreshed on " & ws.Name, vbInformation
    LogMsg "Force_Refresh_Colors", "Manual refresh completed", ws.Name
    RefreshSummaryDashboard "Force_Refresh_Colors"
    Exit Sub
EH:
    If wasProtected Then EndSheetWrite ws, wasProtected
    MsgBox "Error: " & Err.Description, vbCritical
    LogMsg "Force_Refresh_Colors", Err.Number & " - " & Err.Description, ws.Name
End Sub

Public Sub Diagnostic_Color_Status()
    ' Show current color configuration status
    On Error Resume Next
    Dim ws As Worksheet
    Set ws = ActiveSheet
    
    Dim msg As String
    msg = "=== COLOR DIAGNOSTIC ===" & vbCrLf & vbCrLf
    msg = msg & "Active Sheet: " & ws.Name & vbCrLf
    msg = msg & "Is Gantt Sheet: " & IsGanttSheet(ws) & vbCrLf & vbCrLf
    
    msg = msg & "--- Configuration ---" & vbCrLf
    msg = msg & "Mode: Single-base manual" & vbCrLf
    msg = msg & "REPAINT_MODE: " & CfgText("CFG_REPAINT_MODE", "PAINT") & vbCrLf
    msg = msg & "Start/End/Days change behavior: Recompute current row + shift lower rows" & vbCrLf
    msg = msg & "Predecessor/Lag: Hidden and ignored" & vbCrLf
    msg = msg & "Step ID column hidden: " & ws.Columns(COL_STEP).Hidden & vbCrLf
    msg = msg & "Notes column: " & IIf(ws.Columns(COL_NOTE).Hidden, "Hidden", "Visible") & vbCrLf
    msg = msg & "CF Disabled This Session: " & gDisableConditionalFormatting & vbCrLf & vbCrLf
    
    msg = msg & "--- Build Metadata ---" & vbCrLf
    msg = msg & "Build Timestamp: " & GetHiddenTextName(BUILD_TIMESTAMP_NAME, "manual") & vbCrLf
    msg = msg & "BAS Timestamp: " & GetHiddenTextName(BUILD_BAS_TIMESTAMP_NAME, "manual") & vbCrLf
    msg = msg & "Event Hook Timestamp: " & GetHiddenTextName(BUILD_HOOK_TIMESTAMP_NAME, "manual") & vbCrLf
    msg = msg & "Build Token: " & GetHiddenTextName(BUILD_TOKEN_NAME, "manual") & vbCrLf & vbCrLf
    
    If IsGanttSheet(ws) Then
        Dim lastR As Long: lastR = LastUsedRow(ws)
        Dim endCol As Long: endCol = HeaderLastCol(ws)
        Dim cfCount As Long
        On Error Resume Next
        cfCount = ws.Range(ws.Cells(FIRST_DATA_ROW, DATE_COL_START), ws.Cells(lastR, endCol)).FormatConditions.Count
        On Error GoTo 0
        
        msg = msg & "--- Formatting Status ---" & vbCrLf
        msg = msg & "Conditional Format Rules: " & cfCount & vbCrLf
        msg = msg & "Data Rows: " & (lastR - FIRST_DATA_ROW + 1) & vbCrLf
        msg = msg & "Date Columns: " & (endCol - DATE_COL_START + 1) & vbCrLf
    End If
    
    MsgBox msg, vbInformation, "Color Diagnostic"
End Sub




