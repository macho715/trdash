Attribute VB_Name = "Run_TR5_Gantt_Build"
Option Explicit

Public Sub Run_TR5_Gantt_Build()
    Dim shell As Object
    Dim command As String

    Set shell = CreateObject("WScript.Shell")
    command = "powershell -NoProfile -ExecutionPolicy Bypass -Command " & _
              Chr$(34) & "Set-Location 'C:\tr_dash-main'; python 'scripts\tr5_build_gantt_workbook.py' --open" & Chr$(34)
    shell.Run command, 1, False
End Sub
