param(
    [string]$GroupName = "",
    [string]$TeacherName = "",
    [int]$LookbackDays = 3,
    [string]$OutputPath = "homework_report.md",
    [string]$StateFile = ".qq_monitor_state.json",
    [string]$ChatFile = "",
    [string]$ChatFileEncoding = "utf-8",
    [string]$SiteRepoPath = "tangguo",
    [string]$SiteReportRelativePath = "homework_report.md",
    [switch]$NoPublishToSite
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
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if ($NoPublishToSite) {
    Write-Host "Skip publish: -NoPublishToSite specified."
    exit 0
}

function Resolve-AbsPath([string]$BaseDir, [string]$PathValue) {
    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }
    return (Join-Path $BaseDir $PathValue)
}

function Publish-ReportToSite(
    [string]$BaseDir,
    [string]$ReportPath,
    [string]$SiteRepo,
    [string]$SiteReportRel
) {
    $reportAbs = Resolve-AbsPath -BaseDir $BaseDir -PathValue $ReportPath
    if (-not (Test-Path $reportAbs)) {
        throw "Report file not found: $reportAbs"
    }

    $siteRepoAbs = Resolve-AbsPath -BaseDir $BaseDir -PathValue $SiteRepo
    if (-not (Test-Path $siteRepoAbs)) {
        throw "Site repository path not found: $siteRepoAbs"
    }
    if (-not (Test-Path (Join-Path $siteRepoAbs ".git"))) {
        throw "Site repository is not a git repo: $siteRepoAbs"
    }

    $siteReportAbs = Resolve-AbsPath -BaseDir $siteRepoAbs -PathValue $SiteReportRel
    $siteReportDir = Split-Path -Parent $siteReportAbs
    if (-not (Test-Path $siteReportDir)) {
        New-Item -Path $siteReportDir -ItemType Directory -Force | Out-Null
    }

    Copy-Item -Path $reportAbs -Destination $siteReportAbs -Force

    Push-Location $siteRepoAbs
    try {
        git add -- $SiteReportRel
        git diff --cached --quiet -- $SiteReportRel
        if ($LASTEXITCODE -eq 0) {
            Write-Host "No site changes to publish."
            return
        }

        $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        git commit -m "chore: auto publish homework report ($stamp)"
        if ($LASTEXITCODE -ne 0) {
            throw "git commit failed."
        }

        git push origin main
        if ($LASTEXITCODE -ne 0) {
            throw "git push failed."
        }

        Write-Host "Published report to site repository: $siteRepoAbs"
    } finally {
        Pop-Location
    }
}

Publish-ReportToSite -BaseDir $scriptDir -ReportPath $OutputPath -SiteRepo $SiteRepoPath -SiteReportRel $SiteReportRelativePath
exit 0
