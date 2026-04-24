Option Explicit

' ⚠️가정:
' 1) 아래 PYTHON_EXE 와 SCRIPT_PATH 는 실제 PC 경로에 맞게 수정합니다.
' 2) 이 매크로는 원본 .xlsm 안에서 실행됩니다.
' 3) Python 스크립트는 대상 파일을 직접 패치하므로, 실행 전 파일 잠금 여부를 확인합니다.

Private Const PYTHON_EXE As String = "py"
Private Const SCRIPT_PATH As String = "C:\tr_dash-main\scripts\tr5_fix_date_and_gantt_scope_upgraded.py"

Public Sub Run_TR5_Scope_Patch()
    On Error GoTo ErrHandler

    Dim cmd As String
    Dim shellObj As Object
    Dim exitCode As Long

    cmd = """" & PYTHON_EXE & """" & " " & """" & SCRIPT_PATH & """"

    Set shellObj = CreateObject("WScript.Shell")
    exitCode = shellObj.Run(cmd, 0, True)

    WriteLog "Run_TR5_Scope_Patch", "ExitCode=" & CStr(exitCode)

    If exitCode = 0 Then
        MsgBox "TR5 scope patch completed successfully.", vbInformation
    Else
        MsgBox "TR5 scope patch failed. Check validation_report.json and scope_patch.log.", vbExclamation
    End If
    Exit Sub

ErrHandler:
    WriteLog "Run_TR5_Scope_Patch", "Error " & Err.Number & ": " & Err.Description
    MsgBox "Macro failed: " & Err.Description, vbCritical
End Sub

Private Sub WriteLog(ByVal sourceName As String, ByVal messageText As String)
    On Error GoTo SafeExit

    Dim ws As Worksheet
    Dim nextRow As Long

    Set ws = Nothing
    On Error Resume Next
    Set ws = ThisWorkbook.Worksheets("LOG")
    On Error GoTo SafeExit

    If ws Is Nothing Then
        Set ws = ThisWorkbook.Worksheets.Add(After:=ThisWorkbook.Worksheets(ThisWorkbook.Worksheets.Count))
        ws.Name = "LOG"
        ws.Range("A1:C1").Value = Array("Timestamp", "Source", "Message")
    End If

    nextRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row + 1
    ws.Cells(nextRow, 1).Value = Now
    ws.Cells(nextRow, 2).Value = sourceName
    ws.Cells(nextRow, 3).Value = messageText

SafeExit:
End Sub
