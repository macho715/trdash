$xlsm = "C:\tr_dash-main\work\TR5_PreOp_Gantt_20260415\excel\TR5_PreOp_Gantt_20260415_162140.xlsm"
$old  = "RefreshGanttExactRange ws, DateSerial(2026, 4, 27), DateSerial(2026, 5, 17), False"
$new  = "RefreshGantt ws, False"

Write-Host "Starting Excel..." -ForegroundColor Cyan
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $true
$excel.DisplayAlerts = $false
$excel.AutomationSecurity = 1   # msoAutomationSecurityLow

Write-Host "Excel $($excel.Version) ready." -ForegroundColor Green
Write-Host "Opening workbook..." -ForegroundColor Cyan
$wb = $excel.Workbooks.Open($xlsm, 0, $false)
Write-Host "Opened: $($wb.Name)" -ForegroundColor Green

$cm = $wb.VBProject.VBComponents("modMIR_Gantt_Unified").CodeModule
$n  = $cm.CountOfLines
$code = $cm.Lines(1, $n)

$count = ([regex]::Matches($code, [regex]::Escape($old))).Count
Write-Host "Hardcoded occurrences: $count" -ForegroundColor Yellow

if ($count -eq 0) {
    Write-Host "[WARN] Pattern not found. RefreshGanttExactRange lines:" -ForegroundColor Red
    $lines = $code -split "`r`n|`n"
    for ($i = 0; $i -lt $lines.Length; $i++) {
        if ($lines[$i] -match "RefreshGanttExactRange") {
            Write-Host "  $($i+1): $($lines[$i])"
        }
    }
} else {
    $newCode = $code -replace [regex]::Escape($old), $new
    $remaining = ([regex]::Matches($newCode, [regex]::Escape($old))).Count
    $cm.DeleteLines(1, $n)
    $cm.InsertLines(1, $newCode)
    Write-Host "Replaced $count occurrences. Remaining: $remaining. Lines: $($cm.CountOfLines)" -ForegroundColor Green
    $wb.Save()
    Write-Host "Saved." -ForegroundColor Green
}

$excel.Visible = $false
$wb.Close($false)
$excel.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null
Write-Host "Done." -ForegroundColor Cyan
