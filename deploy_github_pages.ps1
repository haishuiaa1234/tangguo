param(
  [Parameter(Mandatory = $true)]
  [string]$RepoUrl
)

$ErrorActionPreference = "Stop"

$siteDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $siteDir

if (-not (Test-Path ".git")) {
  throw "当前目录不是 Git 仓库：$siteDir"
}

$hasOrigin = $false
try {
  git remote get-url origin | Out-Null
  $hasOrigin = $true
} catch {
  $hasOrigin = $false
}

if ($hasOrigin) {
  git remote set-url origin $RepoUrl
} else {
  git remote add origin $RepoUrl
}

Write-Host "正在推送到: $RepoUrl"
git push -u origin main

$pagesHint = ""
if ($RepoUrl -match "github\\.com[:/](.+?)/(.+?)(\\.git)?$") {
  $owner = $Matches[1]
  $repo = $Matches[2]
  $pagesHint = "https://$owner.github.io/$repo/"
}

Write-Host ""
Write-Host "推送完成。"
if ($pagesHint) {
  Write-Host "预计 Pages 地址: $pagesHint"
}
Write-Host "首次部署需等待 GitHub Actions 跑完（通常 1~3 分钟）。"
