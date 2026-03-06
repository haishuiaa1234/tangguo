#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Monitor QQ group chat and extract Chinese homework tasks from a target teacher.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

try:
    import pyautogui  # type: ignore
    import pygetwindow as gw  # type: ignore
    import pyperclip  # type: ignore
except ImportError:
    pyautogui = None
    gw = None
    pyperclip = None


WEEKDAY_MAP = {
    0: "周一",
    1: "周二",
    2: "周三",
    3: "周四",
    4: "周五",
    5: "周六",
    6: "周日",
}

CH_WEEKDAY = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}

HOMEWORK_KEYWORDS = [
    "作业",
    "完成",
    "背诵",
    "朗读",
    "抄写",
    "默写",
    "听写",
    "预习",
    "复习",
    "练习",
    "阅读",
    "打卡",
    "提交",
    "上传",
    "签字",
    "改错",
    "写话",
    "作文",
    "生字",
    "词语",
    "课文",
    "古诗",
    "练习册",
    "试卷",
    "卷子",
    "第",
    "页",
]

NON_HOMEWORK_PATTERNS = [
    r"^收到[了]?$",
    r"^谢谢[老师]?$",
    r"^辛苦[了]?$",
    r"^已完成$",
    r"^打卡$",
]

PAGE_PATTERN = re.compile(
    r"(第\s*\d+\s*页|第\s*[一二三四五六七八九十百]+\s*页|p\s*\d+)", re.IGNORECASE
)


@dataclass
class Message:
    timestamp: datetime
    sender: str
    content: str


@dataclass
class Task:
    source_time: datetime
    text: str
    pages: list[str]
    eta_minutes: int
    due_priority: int
    due_hint: str
    can_help: str


def normalize_sender(sender: str) -> str:
    return re.sub(r"\s+", "", sender or "").strip()


def safe_read_text(path: Path, encoding: str) -> str:
    return path.read_text(encoding=encoding, errors="ignore")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="监控QQ群并提取语文作业（近3天，指定老师）。"
    )
    parser.add_argument("--group-name", default="琅小柳洲东路一2班", help="QQ群名关键字")
    parser.add_argument("--teacher-name", default="语文-王老师", help="老师昵称关键字")
    parser.add_argument(
        "--poll-seconds", type=int, default=300, help="轮询间隔秒数（默认5分钟）"
    )
    parser.add_argument(
        "--lookback-days", type=int, default=3, help="回看天数（默认3）"
    )
    parser.add_argument(
        "--output", default="homework_report.md", help="输出报告路径（Markdown）"
    )
    parser.add_argument(
        "--state-file", default=".qq_monitor_state.json", help="状态文件路径"
    )
    parser.add_argument(
        "--chat-file",
        default="",
        help="可选：QQ聊天导出文件路径。设置后将监控该文件而不是抓QQ窗口。",
    )
    parser.add_argument(
        "--chat-file-encoding", default="utf-8", help="聊天导出文件编码（默认utf-8）"
    )
    parser.add_argument(
        "--use-scroll-capture",
        action="store_true",
        help="使用鼠标滚轮方式抓取QQ聊天区（适配红框聊天区）。",
    )
    parser.add_argument(
        "--scroll-rounds",
        type=int,
        default=18,
        help="滚轮抓取轮数（每轮复制一次后向上滚动）。",
    )
    parser.add_argument(
        "--scroll-amount",
        type=int,
        default=900,
        help="每轮滚动距离（正数表示向上）。",
    )
    parser.add_argument(
        "--raw-output",
        default="raw_capture.txt",
        help="保存原始抓取文本路径；留空则不保存。",
    )
    parser.add_argument("--once", action="store_true", help="只执行一次后退出")
    return parser.parse_args()


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def calc_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def resolve_qq_window(group_name: str):
    if pyautogui is None or gw is None or pyperclip is None:
        raise RuntimeError(
            "缺少依赖：请先运行 `pip install -r requirements.txt` 安装 pyautogui/pyperclip/PyGetWindow。"
        )

    titles = [t for t in gw.getAllTitles() if t and group_name in t]
    if not titles:
        try_open_group_chat_from_main_qq(group_name)
        time.sleep(1.2)
        titles = [t for t in gw.getAllTitles() if t and group_name in t]
    if titles:
        windows = gw.getWindowsWithTitle(titles[0])
        if not windows:
            raise RuntimeError("找到了标题但无法获取窗口对象。")
        win = windows[0]
    else:
        # QQ NT often keeps conversation inside a single main window titled "QQ".
        qq_titles = [
            t
            for t in gw.getAllTitles()
            if t and (t.strip() == "QQ" or t.strip().startswith("QQ "))
        ]
        if not qq_titles:
            raise RuntimeError(
                f"未找到包含群名“{group_name}”的窗口，也未找到可用QQ主窗口。"
            )
        windows = gw.getWindowsWithTitle(qq_titles[0])
        if not windows:
            raise RuntimeError("无法获取QQ主窗口对象。")
        win = windows[0]
    return win


def capture_chat_text_from_qq(group_name: str) -> str:
    win = resolve_qq_window(group_name)

    safe_activate_window(win)
    time.sleep(0.6)
    text = capture_text_by_multi_points(win)

    if not text.strip():
        raise RuntimeError("复制到的聊天内容为空，请确认聊天窗口中有记录。")
    return text


def capture_chat_text_from_qq_by_scroll(
    group_name: str,
    teacher_name: str,
    scroll_rounds: int,
    scroll_amount: int,
) -> str:
    assert pyautogui is not None
    assert pyperclip is not None

    win = resolve_qq_window(group_name)
    safe_activate_window(win)
    time.sleep(0.6)

    old_clipboard = pyperclip.paste()
    chunks: list[str] = []
    px = 0
    py = 0
    try:
        px, py, seed = choose_best_chat_point(win, teacher_name)
        if seed.strip():
            chunks.append(seed)

        pyautogui.click(px, py)
        time.sleep(0.15)
        pyautogui.hotkey("ctrl", "end")
        time.sleep(0.2)
        pyautogui.press("end")
        time.sleep(0.2)

        rounds = max(1, scroll_rounds)
        for _ in range(rounds):
            txt = copy_text_at_pixel(px, py)
            if txt.strip():
                chunks.append(txt)
            pyautogui.scroll(int(scroll_amount), x=px, y=py)
            time.sleep(0.35)

        tail = copy_text_at_pixel(px, py)
        if tail.strip():
            chunks.append(tail)
    finally:
        pyperclip.copy(old_clipboard)

    merged = merge_text_chunks(chunks)
    if not merged.strip():
        raise RuntimeError("滚轮抓取未获取到有效聊天文本。")
    return merged


def try_open_group_chat_from_main_qq(group_name: str) -> None:
    assert pyautogui is not None
    assert gw is not None
    assert pyperclip is not None

    qq_titles = []
    for t in gw.getAllTitles():
        if not t:
            continue
        stripped = t.strip()
        if stripped == "QQ" or stripped.startswith("QQ "):
            qq_titles.append(t)
    if not qq_titles:
        return

    windows = gw.getWindowsWithTitle(qq_titles[0])
    if not windows:
        return
    win = windows[0]
    old_clipboard = pyperclip.paste()
    try:
        safe_activate_window(win)
        time.sleep(0.5)
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.press("backspace")
        pyperclip.copy(group_name)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.4)
        pyautogui.press("enter")
        time.sleep(0.6)
        pyautogui.press("enter")
    finally:
        pyperclip.copy(old_clipboard)


def safe_activate_window(win) -> None:
    try:
        if hasattr(win, "isMinimized") and win.isMinimized:
            win.restore()
            time.sleep(0.2)
        win.activate()
    except Exception:
        # Fallback: click into the window area to focus when activate() is unreliable.
        try:
            x = win.left + min(100, max(10, win.width // 4))
            y = win.top + min(100, max(10, win.height // 6))
            pyautogui.click(x, y)
        except Exception:
            pass


def capture_text_by_multi_points(win) -> str:
    assert pyautogui is not None
    assert pyperclip is not None

    old_clipboard = pyperclip.paste()
    best = ""

    try:
        _, _, best = choose_best_chat_point(win, teacher_name_hint="")
    finally:
        pyperclip.copy(old_clipboard)
    return best


def get_chat_area_candidates() -> list[tuple[float, float]]:
    return [
        # Common chat panel positions.
        (0.72, 0.28),
        (0.72, 0.40),
        (0.72, 0.52),
        (0.62, 0.35),
        (0.55, 0.35),
        # Some QQ NT layouts place selectable text further right.
        (0.85, 0.28),
        (0.85, 0.36),
        (0.85, 0.44),
        (0.85, 0.52),
        (0.85, 0.60),
        (0.85, 0.68),
    ]


def copy_text_at_pixel(x: int, y: int) -> str:
    assert pyautogui is not None
    assert pyperclip is not None

    pyautogui.click(x, y)
    time.sleep(0.15)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.15)
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.35)
    return pyperclip.paste() or ""


def choose_best_chat_point(win, teacher_name_hint: str) -> tuple[int, int, str]:
    best_text = ""
    best_score = -1
    best_px = win.left + int(win.width * 0.85)
    best_py = win.top + int(win.height * 0.28)

    for rx, ry in get_chat_area_candidates():
        px = win.left + int(win.width * rx)
        py = win.top + int(win.height * ry)
        txt = copy_text_at_pixel(px, py)
        sc = score_captured_text(txt, teacher_name_hint=teacher_name_hint)
        if sc > best_score:
            best_score = sc
            best_text = txt
            best_px = px
            best_py = py
    return best_px, best_py, best_text


def merge_text_chunks(chunks: list[str]) -> str:
    merged: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        text = (chunk or "").strip()
        if not text:
            continue
        key = calc_hash(re.sub(r"\s+", "", text))
        if key in seen:
            continue
        seen.add(key)
        merged.append(text)
    return "\n\n".join(merged)


def score_captured_text(text: str, teacher_name_hint: str = "") -> int:
    if not text:
        return 0
    score = len(text)
    score += text.count("\n") * 20
    if any(ch in text for ch in ["作业", "老师", "群", "家长", "今天", "明天"]):
        score += 300
    if teacher_name_hint and teacher_name_hint in text:
        score += 500
    return score


def parse_date_token(token: str) -> Optional[date]:
    token = token.strip()
    m = re.match(r"^(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})日?$", token)
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def parse_datetime_token(token: str, fallback_date: date) -> Optional[datetime]:
    token = token.strip()
    patterns = [
        r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?$",
        r"^(\d{4})年(\d{1,2})月(\d{1,2})日?\s+(\d{1,2}):(\d{2})(?::(\d{2}))?$",
    ]
    for p in patterns:
        m = re.match(p, token)
        if m:
            y, mo, d, hh, mm, ss = m.groups()
            try:
                return datetime(
                    int(y),
                    int(mo),
                    int(d),
                    int(hh),
                    int(mm),
                    int(ss or 0),
                )
            except ValueError:
                return None

    m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", token)
    if m:
        hh, mm, ss = m.groups()
        try:
            return datetime(
                fallback_date.year,
                fallback_date.month,
                fallback_date.day,
                int(hh),
                int(mm),
                int(ss or 0),
            )
        except ValueError:
            return None
    return None


def flush_message(
    out: list[Message],
    sender: Optional[str],
    timestamp: Optional[datetime],
    buffer: list[str],
) -> None:
    if sender and timestamp and buffer:
        content = "\n".join([x for x in buffer if x.strip()]).strip()
        if content:
            out.append(Message(timestamp=timestamp, sender=sender, content=content))


def parse_chat_text(raw_text: str, now: datetime) -> list[Message]:
    lines = [line.rstrip() for line in raw_text.splitlines()]
    messages: list[Message] = []

    active_sender: Optional[str] = None
    active_ts: Optional[datetime] = None
    content_buffer: list[str] = []
    current_date = now.date()

    header_patterns = [
        re.compile(
            r"^(?P<dt>\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?)\s+(?P<sender>.+?)$"
        ),
        re.compile(
            r"^(?P<sender>.+?)\s+(?P<dt>\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?)$"
        ),
        re.compile(r"^(?P<sender>.+?)\s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?)$"),
    ]

    for raw_line in lines:
        line = raw_line.strip().replace("\ufeff", "")
        if not line:
            if content_buffer:
                content_buffer.append("")
            continue

        date_token = parse_date_token(line)
        if date_token:
            current_date = date_token
            continue

        matched = False
        for hp in header_patterns:
            m = hp.match(line)
            if not m:
                continue

            flush_message(messages, active_sender, active_ts, content_buffer)
            content_buffer = []

            sender = m.groupdict().get("sender", "").strip()
            dt_token = m.groupdict().get("dt")
            time_token = m.groupdict().get("time")
            dt = None
            if dt_token:
                dt = parse_datetime_token(dt_token, fallback_date=current_date)
            elif time_token:
                dt = parse_datetime_token(time_token, fallback_date=current_date)

            active_sender = sender
            active_ts = dt
            matched = True
            break

        if matched:
            continue

        if active_sender is not None:
            content_buffer.append(line)

    flush_message(messages, active_sender, active_ts, content_buffer)

    # Only keep sane timestamps.
    valid: list[Message] = []
    for msg in messages:
        if msg.timestamp.year < 2000 or msg.timestamp > (now + timedelta(days=2)):
            continue
        valid.append(msg)
    return valid


def contains_non_homework_only(text: str) -> bool:
    pure = re.sub(r"[，。！？,.!?\s]+", "", text)
    if not pure:
        return True
    return any(re.match(p, pure) for p in NON_HOMEWORK_PATTERNS)


def is_homework_text(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    if contains_non_homework_only(normalized):
        return False

    keyword_hits = sum(1 for kw in HOMEWORK_KEYWORDS if kw in normalized)
    if keyword_hits >= 2:
        return True
    if keyword_hits == 1 and len(normalized) >= 8:
        return True

    imperative_hints = ["请", "务必", "今晚", "明天交", "完成后", "家长", "签字"]
    return any(x in normalized for x in imperative_hints)


def estimate_minutes(task_text: str) -> int:
    if any(k in task_text for k in ["作文", "写话", "读后感"]):
        return 40
    if any(k in task_text for k in ["试卷", "练习册", "练习题"]):
        return 35
    if any(k in task_text for k in ["抄写", "默写", "听写"]):
        return 25
    if any(k in task_text for k in ["背诵", "朗读"]):
        return 20
    if any(k in task_text for k in ["阅读", "预习", "复习"]):
        return 30
    return 20


def infer_due_priority_and_hint(task_text: str) -> tuple[int, str]:
    if any(x in task_text for x in ["今天", "今晚", "当天"]):
        return 0, "今天"
    if "明天" in task_text:
        return 1, "明天"
    m = re.search(r"(周[一二三四五六日天])", task_text)
    if m:
        return 2, m.group(1)
    return 3, "未写明"


def infer_help_hint(task_text: str) -> str:
    if any(x in task_text for x in ["作文", "写话", "读后感"]):
        return "可帮你生成提纲、开头结尾示例，由孩子自行改写成最终稿。"
    if any(x in task_text for x in ["阅读理解", "阅读题"]):
        return "可帮你拆解题型并给答题模板，再让孩子按文段填写。"
    if any(x in task_text for x in ["造句", "组词", "近义词", "反义词"]):
        return "可先给练习草稿，家长再带孩子口头复述后誊写。"
    if any(x in task_text for x in ["抄写", "背诵", "朗读", "默写"]):
        return "可生成分段打卡清单和计时安排，便于执行。"
    return "可帮你进一步拆成更细步骤（每10-15分钟一段）。"


def split_candidate_tasks(content: str) -> Iterable[str]:
    # Split by line and common sentence delimiters.
    raw_segments = re.split(r"[\n；;。]", content)
    for seg in raw_segments:
        s = seg.strip(" -：:，,")
        if s:
            yield s


def dedupe_tasks(tasks: list[Task]) -> list[Task]:
    out: list[Task] = []
    seen: set[str] = set()
    for t in tasks:
        key = re.sub(r"\s+", "", t.text)
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def extract_tasks(
    messages: list[Message], teacher_name: str, lookback_days: int, now: datetime
) -> list[Task]:
    teacher_normalized = normalize_sender(teacher_name)
    cutoff = now - timedelta(days=lookback_days)
    tasks: list[Task] = []

    for msg in messages:
        if msg.timestamp < cutoff:
            continue
        sender_norm = normalize_sender(msg.sender)
        if teacher_normalized not in sender_norm and sender_norm not in teacher_normalized:
            continue

        for segment in split_candidate_tasks(msg.content):
            if not is_homework_text(segment):
                continue
            pages = [m.group(0) for m in PAGE_PATTERN.finditer(segment)]
            eta = estimate_minutes(segment)
            due_priority, due_hint = infer_due_priority_and_hint(segment)
            tasks.append(
                Task(
                    source_time=msg.timestamp,
                    text=segment,
                    pages=pages,
                    eta_minutes=eta,
                    due_priority=due_priority,
                    due_hint=due_hint,
                    can_help=infer_help_hint(segment),
                )
            )
    tasks.sort(key=lambda x: (x.due_priority, x.source_time))
    return dedupe_tasks(tasks)


def plan_tasks(tasks: list[Task], now: datetime) -> dict[date, list[Task]]:
    # Evening-focused plan for the next 3 days.
    days = [now.date() + timedelta(days=i) for i in range(3)]
    remain_minutes = {d: 80 for d in days}
    plan: dict[date, list[Task]] = {d: [] for d in days}

    for task in tasks:
        preferred = min(task.due_priority, 2)
        day_indexes = list(range(preferred, 3)) + list(range(0, preferred))
        chosen_day = days[2]
        for idx in day_indexes:
            d = days[idx]
            if remain_minutes[d] >= task.eta_minutes:
                chosen_day = d
                break
        plan[chosen_day].append(task)
        remain_minutes[chosen_day] -= task.eta_minutes
    return plan


def markdown_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def format_report(
    tasks: list[Task],
    messages: list[Message],
    group_name: str,
    teacher_name: str,
    lookback_days: int,
    now: datetime,
) -> str:
    cutoff = (now - timedelta(days=lookback_days)).strftime("%Y-%m-%d %H:%M")
    lines: list[str] = []
    lines.append(f"# 语文作业监控报告（{now.strftime('%Y-%m-%d %H:%M')}）")
    lines.append("")
    lines.append(f"- 群名：{group_name}")
    lines.append(f"- 监控对象：{teacher_name}")
    lines.append(f"- 统计窗口：最近{lookback_days}天（自 {cutoff} 起）")
    lines.append("")

    if not tasks:
        lines.append("## 1. 识别结果")
        lines.append("近3天未识别到明确“需要学生完成”的语文作业消息。")
        lines.append("")
        lines.append("## 2. 建议")
        lines.append("1. 请确认老师昵称与脚本参数 `--teacher-name` 一致。")
        lines.append("2. 请确认抓取到的是聊天记录区而不是输入框内容。")
        lines.append("3. 可切换到 `--chat-file` 模式读取导出的QQ群聊天记录。")
        return "\n".join(lines)

    lines.append("## 1. 识别到的待完成作业")
    lines.append("| 序号 | 发布时间 | 作业内容 | 页码/提示 | 预计时长 |")
    lines.append("|---|---|---|---|---|")
    for idx, task in enumerate(tasks, start=1):
        page_text = "、".join(task.pages) if task.pages else "-"
        lines.append(
            f"| {idx} | {task.source_time.strftime('%m-%d %H:%M')} | "
            f"{markdown_escape(task.text)} | {markdown_escape(page_text)} | {task.eta_minutes} 分钟 |"
        )
    lines.append("")

    lines.append("## 2. 3天完成计划")
    plan = plan_tasks(tasks, now)
    for d in sorted(plan.keys()):
        day_name = WEEKDAY_MAP[d.weekday()]
        lines.append(f"### {d.strftime('%Y-%m-%d')}（{day_name}）")
        if not plan[d]:
            lines.append("- 预留机动时间：复盘错题/阅读20分钟。")
            continue
        for t in plan[d]:
            lines.append(f"- [ ] {t.text}（约{t.eta_minutes}分钟，来源：{t.source_time.strftime('%m-%d %H:%M')}）")
        total = sum(x.eta_minutes for x in plan[d])
        lines.append(f"- 合计时长：约 {total} 分钟")
    lines.append("")

    lines.append("## 3. 完成建议")
    lines.append("1. 执行顺序建议：先“背诵/朗读”，再“抄写/默写”，最后做“练习册/作文”。")
    lines.append("2. 采用25分钟专注+5分钟休息，低年级每晚总时长建议控制在60-90分钟。")
    lines.append("3. 每项完成后立刻拍照或打卡，避免临近截止集中提交。")
    lines.append("4. 对于“签字/订正”类任务，先完成内容再统一家长核对。")
    lines.append("")

    lines.append("## 4. 可协助完成部分（我可以帮）")
    help_lines = []
    for t in tasks:
        help_lines.append(f"- {t.text} -> {t.can_help}")
    # Deduplicate help display.
    seen_help: set[str] = set()
    for hl in help_lines:
        if hl in seen_help:
            continue
        seen_help.add(hl)
        lines.append(hl)
    lines.append("")

    lines.append("## 5. 老师原始消息摘录（近3天）")
    teacher_norm = normalize_sender(teacher_name)
    recent_msgs = [
        m
        for m in messages
        if m.timestamp >= now - timedelta(days=lookback_days)
        and (
            teacher_norm in normalize_sender(m.sender)
            or normalize_sender(m.sender) in teacher_norm
        )
    ]
    recent_msgs.sort(key=lambda x: x.timestamp)
    for m in recent_msgs[-20:]:
        brief = m.content.replace("\n", " ").strip()
        if len(brief) > 120:
            brief = brief[:117] + "..."
        lines.append(f"- [{m.timestamp.strftime('%m-%d %H:%M')}] {brief}")

    return "\n".join(lines)


def process_once(
    raw_text: str,
    now: datetime,
    args: argparse.Namespace,
) -> tuple[str, int]:
    messages = parse_chat_text(raw_text, now=now)
    tasks = extract_tasks(
        messages=messages,
        teacher_name=args.teacher_name,
        lookback_days=args.lookback_days,
        now=now,
    )
    report = format_report(
        tasks=tasks,
        messages=messages,
        group_name=args.group_name,
        teacher_name=args.teacher_name,
        lookback_days=args.lookback_days,
        now=now,
    )
    return report, len(tasks)


def read_source_text(args: argparse.Namespace) -> str:
    if args.chat_file:
        path = Path(args.chat_file).expanduser().resolve()
        if not path.exists():
            raise RuntimeError(f"聊天文件不存在：{path}")
        return safe_read_text(path, args.chat_file_encoding)
    if args.use_scroll_capture:
        raw = capture_chat_text_from_qq_by_scroll(
            group_name=args.group_name,
            teacher_name=args.teacher_name,
            scroll_rounds=args.scroll_rounds,
            scroll_amount=args.scroll_amount,
        )
    else:
        raw = capture_chat_text_from_qq(args.group_name)

    if args.raw_output:
        Path(args.raw_output).expanduser().resolve().write_text(raw, encoding="utf-8")
    return raw


def main() -> int:
    args = parse_args()
    output_path = Path(args.output).expanduser().resolve()
    state_path = Path(args.state_file).expanduser().resolve()
    state = load_state(state_path)

    print("QQ群作业监控启动：")
    print(f"- 群名关键字: {args.group_name}")
    print(f"- 老师关键字: {args.teacher_name}")
    print(f"- 输出报告: {output_path}")
    if args.chat_file:
        print(f"- 模式: 聊天文件监控 ({args.chat_file})")
    else:
        print("- 模式: QQ窗口抓取")

    while True:
        try:
            raw_text = read_source_text(args)
            digest = calc_hash(raw_text)

            if state.get("last_hash") == digest:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 无新内容，跳过生成。")
            else:
                now = datetime.now()
                report, task_count = process_once(raw_text=raw_text, now=now, args=args)
                output_path.write_text(report, encoding="utf-8")
                print(
                    f"[{now.strftime('%H:%M:%S')}] 已更新报告：{output_path}，识别作业 {task_count} 条。"
                )
                state["last_hash"] = digest
                state["last_report_at"] = now.isoformat(timespec="seconds")
                save_state(state_path, state)
        except KeyboardInterrupt:
            print("\n已手动停止监控。")
            return 0
        except Exception as exc:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 处理失败：{exc}")
            if args.once:
                return 1

        if args.once:
            return 0
        time.sleep(max(5, args.poll_seconds))


if __name__ == "__main__":
    sys.exit(main())
