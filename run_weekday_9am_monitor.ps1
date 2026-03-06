param(
    [string]$GroupName = "",
    [string]$TeacherName = "",
    [int]$LookbackDays = 3,
    [string]$OutputPath = "homework_report.md",
    [string]$StateFile = ".qq_monitor_state.json",
    [string]$ChatFile = "",
    [string]$ChatFileEncoding = "utf-8"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

$cmdArgs = @(
    "qq_homework_monitor.py",
    "--lookback-days", $LookbackDays.ToString(),
    "--output", $OutputPath,
    "--state-file", $StateFile,
    "--once",
    "--force-write"
)

if ($GroupName) {
    $cmdArgs += @("--group-name", $GroupName)
}

if ($TeacherName) {
    $cmdArgs += @("--teacher-name", $TeacherName)
}

if ($ChatFile) {
    $cmdArgs += @("--chat-file", $ChatFile, "--chat-file-encoding", $ChatFileEncoding)
}

python @cmdArgs
exit $LASTEXITCODE
