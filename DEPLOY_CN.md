# 国内可访问部署（免费方案）

## 推荐方案：腾讯云 CloudBase 静态托管

优点：
- 国内网络访问更稳定。
- 适合你这个纯静态网站（HTML/CSS/JS + PDF + txt）。
- 支持免费体验/免费额度（以腾讯云控制台当期规则为准）。

## 一次性准备

1. 先在腾讯云开通 CloudBase，并创建一个环境（拿到 `EnvId`）。
2. 打开 PowerShell，进入网站目录：

```powershell
cd "D:\work\文档\小学生作业\parent-todo-site"
```

3. 执行部署脚本（把 `你的EnvId` 替换掉）：

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy_cn_cloudbase.ps1 -EnvId "你的EnvId"
```

脚本会自动：
- 安装 CloudBase CLI（如果未安装）
- 引导登录
- 上传当前网站目录
- 输出托管域名

## 后续更新网站

每次改完网页后，重新执行同一条部署命令即可覆盖更新。

## 说明

- `index.html` 已是网站首页。
- `parent_todo_summary_2026-03-06.pdf` 会一起发布，可公网下载。
