param(
  [int]$Port = 8788,
  [string]$Subdomain = ""
)

$ErrorActionPreference = "Stop"

$siteDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $siteDir

Write-Host "站点目录: $siteDir"
Write-Host "本地地址: http://127.0.0.1:$Port"
Write-Host "正在启动本地静态服务..."

$serverJob = Start-Job -ScriptBlock {
  param($dir, $port)
  Set-Location $dir
  python -m http.server $port --bind 127.0.0.1
} -ArgumentList $siteDir, $Port

try {
  Start-Sleep -Seconds 2
  Write-Host ""
  Write-Host "公网隧道启动中（按 Ctrl+C 停止）..."
  Write-Host "首次执行会自动下载 localtunnel 依赖，请稍等。"
  Write-Host ""

  if ($Subdomain -and $Subdomain.Trim()) {
    npx -y localtunnel --port $Port --subdomain $Subdomain
  } else {
    npx -y localtunnel --port $Port
  }
}
finally {
  Write-Host ""
  Write-Host "正在关闭本地服务..."
  Stop-Job $serverJob -ErrorAction SilentlyContinue | Out-Null
  Remove-Job $serverJob -ErrorAction SilentlyContinue | Out-Null
}
