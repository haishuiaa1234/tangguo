param(
  [Parameter(Mandatory = $true)]
  [string]$EnvId
)

$ErrorActionPreference = "Stop"

$siteDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $siteDir

Write-Host "站点目录: $siteDir"
Write-Host "目标环境: $EnvId"

function Ensure-CloudBaseCli {
  $cli = Get-Command cloudbase -ErrorAction SilentlyContinue
  if ($null -ne $cli) {
    Write-Host "CloudBase CLI 已安装: $($cli.Source)"
    return
  }

  Write-Host "未检测到 CloudBase CLI，正在安装..."
  npm install -g @cloudbase/cli
}

function Ensure-LoggedIn {
  Write-Host ""
  Write-Host "如果你还没登录，会打开扫码/浏览器登录流程。"
  cloudbase login
}

Ensure-CloudBaseCli
Ensure-LoggedIn

Write-Host ""
Write-Host "开始部署静态网站..."
cloudbase hosting deploy . -e $EnvId

Write-Host ""
Write-Host "部署完成，正在读取访问域名..."
cloudbase hosting detail -e $EnvId

Write-Host ""
Write-Host "完成。上面输出里会包含默认访问域名。"
