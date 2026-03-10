const STORAGE_KEY = "parent_todo_state_v1";

const checks = Array.from(document.querySelectorAll(".task-check"));
const progressText = document.getElementById("progressText");
const progressPercent = document.getElementById("progressPercent");
const progressBar = document.getElementById("progressBar");
const toast = document.getElementById("toast");
const exportBtn = document.getElementById("exportBtn");
const resetBtn = document.getElementById("resetBtn");
const latestReportContent = document.getElementById("latestReportContent");
const reportLoadedAt = document.getElementById("reportLoadedAt");

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    toast.classList.remove("show");
  }, 1500);
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const data = raw ? JSON.parse(raw) : {};
    checks.forEach((check) => {
      const id = check.dataset.taskId;
      check.checked = Boolean(data[id]);
    });
  } catch (error) {
    console.warn("load state failed:", error);
  }
}

function saveState() {
  const data = {};
  checks.forEach((check) => {
    data[check.dataset.taskId] = check.checked;
  });
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

function updateProgress() {
  const total = checks.length;
  const done = checks.filter((check) => check.checked).length;
  const percent = total === 0 ? 0 : Math.round((done / total) * 100);
  progressText.textContent = `${done} / ${total}`;
  progressPercent.textContent = `${percent}%`;
  progressBar.style.width = `${percent}%`;
}

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

async function copyText(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const input = document.createElement("textarea");
  input.value = text;
  document.body.appendChild(input);
  input.select();
  document.execCommand("copy");
  document.body.removeChild(input);
}

checks.forEach((check) => {
  check.addEventListener("change", () => {
    saveState();
    updateProgress();
  });
});

document.querySelectorAll(".copy-btn").forEach((button) => {
  button.addEventListener("click", async () => {
    const id = button.dataset.copyTarget;
    const sample = document.getElementById(id);
    if (!sample) {
      showToast("未找到可复制内容");
      return;
    }

    try {
      await copyText(sample.textContent.trim());
      showToast("已复制到剪贴板");
    } catch (error) {
      showToast("复制失败，请手动复制");
      console.error(error);
    }
  });
});

exportBtn.addEventListener("click", async () => {
  const done = checks
    .filter((check) => check.checked)
    .map((check) => check.closest(".task-card").querySelector(".task-title").textContent.trim());

  if (done.length === 0) {
    showToast("还没有勾选完成项");
    return;
  }

  const output = `家长已完成任务（${new Date().toLocaleString()}）\n- ${done.join("\n- ")}`;
  try {
    await copyText(output);
    showToast("已复制已完成清单");
  } catch (error) {
    showToast("复制失败，请稍后再试");
  }
});

resetBtn.addEventListener("click", () => {
  const ok = window.confirm("确认清空所有勾选状态吗？");
  if (!ok) {
    return;
  }

  checks.forEach((check) => {
    check.checked = false;
  });
  saveState();
  updateProgress();
  showToast("已重置");
});

loadState();
updateProgress();
loadLatestReport();
