const latestReportContent = document.getElementById("latestReportContent");
const reportLoadedAt = document.getElementById("reportLoadedAt");

async function loadLatestReport() {
  if (!latestReportContent || !reportLoadedAt) {
    return;
  }

  try {
    const response = await fetch(`./homework_report.md?t=${Date.now()}`, {
      cache: "no-store"
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const text = await response.text();
    latestReportContent.textContent = text.trim() || "报告文件为空。";
    reportLoadedAt.textContent = `已加载：${new Date().toLocaleString()}`;
  } catch (error) {
    latestReportContent.textContent = "加载报告失败，请点击“打开报告原文”查看。";
    reportLoadedAt.textContent = "加载失败";
    console.error("load report failed:", error);
  }
}

loadLatestReport();

