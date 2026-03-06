# 家长待办任务网站（GitHub Pages）

本项目是一个纯静态网站，包含：
- 家长待办任务看板（`index.html`）
- 可下载成品文案（`deliverables/`）
- PDF 汇总（`parent_todo_summary_2026-03-06.pdf`）

## 在线访问

- GitHub Pages：`https://haishuiaa1234.github.io/tangguo/`
- 微信备用（国内 CDN 镜像）：`https://cdn.jsdelivr.net/gh/haishuiaa1234/tangguo@main/index.html`

说明：
- 如果微信内置浏览器打不开 GitHub Pages，优先使用 jsDelivr 备用链接。
- 备用链接通常 1~10 分钟内同步最新版本。

## GitHub Pages 自动部署

仓库推送到 `main` 分支后，GitHub Actions 会自动部署。

工作流文件：
- `.github/workflows/pages.yml`

## 本地打开

直接双击 `index.html` 即可打开，或使用本地服务：

```powershell
python -m http.server 8788 --bind 127.0.0.1
```

然后访问：

`http://127.0.0.1:8788`
