param(
    [string]$TaskName = "QQHomeworkMonitor_Weekday9AM",
    [string]$GroupName = "",
    [string]$TeacherName = "",
    [int]$LookbackDays = 3,
    [string]$OutputPath = "homework_report.md",
    [string]$StateFile = ".qq_monitor_state.json",
    [string]$ChatFile = "",
    [string]$ChatFileEncoding = "utf-8"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$runnerPath = Join-Path $scriptDir "run_weekday_9am_monitor.ps1"

if (-not (Test-Path $runnerPath)) {
    throw "Runner script not found: $runnerPath"
}

$runnerEsc = $runnerPath -replace '"', '\"'
$outputEsc = $OutputPath -replace '"', '\"'
$stateEsc = $StateFile -replace '"', '\"'

$psArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$runnerEsc`" -LookbackDays $LookbackDays -OutputPath `"$outputEsc`" -StateFile `"$stateEsc`""
if ($GroupName) {
    $groupEsc = $GroupName -replace '"', '\"'
    $psArgs += " -GroupName `"$groupEsc`""
}
if ($TeacherName) {
    $teacherEsc = $TeacherName -replace '"', '\"'
    $psArgs += " -TeacherName `"$teacherEsc`""
}
if ($ChatFile) {
    $chatEsc = $ChatFile -replace '"', '\"'
    $chatEncEsc = $ChatFileEncoding -replace '"', '\"'
    $psArgs += " -ChatFile `"$chatEsc`" -ChatFileEncoding `"$chatEncEsc`""
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $psArgs -WorkingDirectory $scriptDir
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At 9:00AM
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType InteractiveToken -RunLevel Limited

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "QQ homework monitor at 9AM on weekdays." | Out-Null

Write-Host "Scheduled task registered: $TaskName"
Write-Host "Trigger: Monday-Friday 09:00"
