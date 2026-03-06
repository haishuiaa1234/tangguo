param(
    [string]$TaskName = "QQHomeworkMonitor_Weekday9AM"
)

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Scheduled task removed: $TaskName"
} else {
    Write-Host "Scheduled task not found: $TaskName"
}
