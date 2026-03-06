param(
    [string]$GroupName = "琅小柳洲东路一2班",
    [string]$TeacherName = "语文-王老师",
    [int]$PollSeconds = 300
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

python qq_homework_monitor.py `
  --group-name $GroupName `
  --teacher-name $TeacherName `
  --poll-seconds $PollSeconds
