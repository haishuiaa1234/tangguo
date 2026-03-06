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
from typing import Any, Iterable, Optional

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
    due_at: Optional[datetime]
    can_help: str


TASK_ID_LEN = 10


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
    parser.add_argument(
        "--complete-task",
        action="append",
        default=[],
        help="将任务标记为已完成。可传任务ID前缀或任务关键字，可重复传入。",
    )
    parser.add_argument(
        "--reopen-task",
        action="append",
        default=[],
        help="将任务恢复为未完成。可传任务ID前缀或任务关键字，可重复传入。",
    )
    parser.add_argument(
        "--force-write",
        action="store_true",
        help="即使聊天文本无变化也生成报告（定时任务推荐开启）。",
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


def normalize_task_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[，。！？,.!?；;：:、（）()\[\]【】\-—_]+", "", text)
    return text


def make_task_id(task_text: str) -> str:
    norm = normalize_task_text(task_text)
    return calc_hash(norm)[:TASK_ID_LEN]


def parse_due_time_from_text(task_text: str) -> tuple[int, int]:
    text = task_text.replace("：", ":")
    m = re.search(r"(\d{1,2})\s*:\s*(\d{2})", text)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2))
    else:
        m = re.search(r"(\d{1,2})\s*点\s*(半)?", text)
        if m:
            hh = int(m.group(1))
            mm = 30 if m.group(2) else 0
        else:
            if "中午" in text:
                return 12, 0
            if "上午" in text or "早上" in text:
                return 10, 0
            if "下午" in text:
                return 17, 0
            if "晚上" in text or "今晚" in text:
                return 20, 0
            return 20, 0

    if ("下午" in text or "晚上" in text) and hh < 12:
        hh += 12
    if "中午" in text and hh < 11:
        hh += 12
    hh = max(0, min(23, hh))
    mm = max(0, min(59, mm))
    return hh, mm


def infer_due_datetime(task_text: str, now: datetime) -> Optional[datetime]:
    text = task_text.strip()
    hh, mm = parse_due_time_from_text(text)
    base_date: Optional[date] = None

    m = re.search(r"(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})日?", text)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            base_date = date(y, mo, d)
        except ValueError:
            base_date = None

    if base_date is None:
        m = re.search(r"(\d{1,2})[./月-](\d{1,2})日?", text)
        if m:
            mo, d = map(int, m.groups())
            y = now.year
            try:
                candidate = date(y, mo, d)
                if candidate < (now.date() - timedelta(days=180)):
                    candidate = date(y + 1, mo, d)
                base_date = candidate
            except ValueError:
                base_date = None

    if base_date is None:
        if "今天" in text or "今晚" in text or "当天" in text:
            base_date = now.date()
        elif "明天" in text:
            base_date = now.date() + timedelta(days=1)
        elif "后天" in text:
            base_date = now.date() + timedelta(days=2)

    if base_date is None:
        m = re.search(r"(周|星期)\s*([一二三四五六日天])", text)
        if m:
            wd = CH_WEEKDAY[m.group(2)]
            delta = (wd - now.weekday()) % 7
            base_date = now.date() + timedelta(days=delta)

    if base_date is None:
        return None
    try:
        return datetime(base_date.year, base_date.month, base_date.day, hh, mm, 0)
    except ValueError:
        return None


def infer_due_priority_and_hint(task_text: str, now: datetime) -> tuple[int, str, Optional[datetime]]:
    due_at = infer_due_datetime(task_text, now)
    if due_at is not None:
        delta_hours = (due_at - now).total_seconds() / 3600
        if delta_hours <= 24:
            p = 0
        elif delta_hours <= 72:
            p = 1
        elif delta_hours <= 168:
            p = 2
        else:
            p = 3
        return p, due_at.strftime("%m-%d %H:%M"), due_at

    if any(x in task_text for x in ["今天", "今晚", "当天"]):
        return 0, "今天", None
    if "明天" in task_text:
        return 1, "明天", None
    m = re.search(r"(周[一二三四五六日天])", task_text)
    if m:
        return 2, m.group(1), None
    return 3, "未写明", None


def parse_iso_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def due_text_from_record(rec: dict) -> str:
    due_at = parse_iso_datetime(str(rec.get("due_at", "")))
    if due_at:
        return due_at.strftime("%m-%d %H:%M")
    return str(rec.get("due_hint", "未写明"))


def upsert_task_board(tasks: list[Task], state: dict, now: datetime) -> tuple[dict[str, dict], list[dict]]:
    board: dict[str, dict] = state.setdefault("task_board", {})
    now_iso = now.isoformat(timespec="seconds")
    seen_ids: set[str] = set()
    new_task_ids: list[str] = []

    for task in tasks:
        task_id = make_task_id(task.text)
        seen_ids.add(task_id)
        due_at_iso = task.due_at.isoformat(timespec="seconds") if task.due_at else ""
        rec = board.get(task_id)

        if rec is None:
            rec = {
                "task_id": task_id,
                "text": task.text,
                "pages": task.pages,
                "eta_minutes": task.eta_minutes,
                "due_priority": task.due_priority,
                "due_hint": task.due_hint,
                "due_at": due_at_iso,
                "can_help": task.can_help,
                "source_time": task.source_time.isoformat(timespec="seconds"),
                "first_seen": now_iso,
                "last_seen": now_iso,
                "status": "todo",
                "completed_at": "",
                "seen_count": 1,
            }
            board[task_id] = rec
            new_task_ids.append(task_id)
            continue

        # Preserve completion state while refreshing task metadata.
        rec["text"] = task.text
        rec["pages"] = task.pages
        rec["eta_minutes"] = task.eta_minutes
        rec["due_priority"] = task.due_priority
        rec["due_hint"] = task.due_hint
        rec["due_at"] = due_at_iso
        rec["can_help"] = task.can_help
        rec["source_time"] = task.source_time.isoformat(timespec="seconds")
        rec["last_seen"] = now_iso
        rec["seen_count"] = int(rec.get("seen_count", 0)) + 1

    for task_id, rec in board.items():
        rec["seen_in_latest_window"] = task_id in seen_ids

    new_tasks = [board[x] for x in new_task_ids]
    return board, new_tasks


def apply_manual_status_updates(
    board: dict[str, dict],
    complete_tokens: list[str],
    reopen_tokens: list[str],
    now: datetime,
) -> list[str]:
    updates: list[str] = []
    now_iso = now.isoformat(timespec="seconds")

    def _apply(tokens: list[str], target_status: str) -> None:
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            matched = []
            token_low = token.lower()
            for rec in board.values():
                if token_low in str(rec.get("task_id", "")).lower() or token in str(rec.get("text", "")):
                    matched.append(rec)
            if not matched:
                updates.append(f"未匹配到任务：{token}")
                continue
            for rec in matched:
                rec["status"] = target_status
                rec["last_status_update"] = now_iso
                if target_status == "done":
                    rec["completed_at"] = now_iso
                    updates.append(f"已完成：{rec['task_id']} {rec['text'][:28]}")
                else:
                    rec["completed_at"] = ""
                    updates.append(f"已恢复未完成：{rec['task_id']} {rec['text'][:28]}")

    _apply(complete_tokens, "done")
    _apply(reopen_tokens, "todo")
    return updates


def sort_pending_records(records: list[dict], now: datetime) -> list[dict]:
    def _sort_key(rec: dict) -> tuple:
        due_at = parse_iso_datetime(str(rec.get("due_at", "")))
        due_unknown = due_at is None
        due_dt = due_at or datetime.max
        return (
            due_unknown,
            due_dt,
            int(rec.get("due_priority", 3)),
            str(rec.get("first_seen", "")),
        )

    return sorted(records, key=_sort_key)


def sort_done_records(records: list[dict]) -> list[dict]:
    def _sort_key(rec: dict) -> tuple:
        done_at = parse_iso_datetime(str(rec.get("completed_at", "")))
        if done_at is None:
            done_at = datetime.min
        return (done_at,)

    return sorted(records, key=_sort_key, reverse=True)


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
        key = normalize_task_text(t.text)
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
            due_priority, due_hint, due_at = infer_due_priority_and_hint(segment, now=now)
            tasks.append(
                Task(
                    source_time=msg.timestamp,
                    text=segment,
                    pages=pages,
                    eta_minutes=eta,
                    due_priority=due_priority,
                    due_hint=due_hint,
                    due_at=due_at,
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

    ordered = sorted(
        tasks,
        key=lambda x: (
            x.due_at is None,
            x.due_at or datetime.max,
            x.due_priority,
            x.source_time,
        ),
    )

    for task in ordered:
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


def int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def record_to_task(rec: dict, now: datetime) -> Task:
    source_time = parse_iso_datetime(str(rec.get("source_time", ""))) or now
    due_at = parse_iso_datetime(str(rec.get("due_at", "")))
    pages_raw = rec.get("pages", [])
    pages = pages_raw if isinstance(pages_raw, list) else []
    return Task(
        source_time=source_time,
        text=str(rec.get("text", "")).strip(),
        pages=[str(x) for x in pages],
        eta_minutes=int_or_default(rec.get("eta_minutes"), 20),
        due_priority=int_or_default(rec.get("due_priority"), 3),
        due_hint=str(rec.get("due_hint", "未写明")),
        due_at=due_at,
        can_help=str(rec.get("can_help", "可帮你拆解为更细执行步骤。")),
    )


def summarize_board(board: dict[str, dict], now: datetime) -> tuple[list[dict], list[dict]]:
    pending: list[dict] = []
    done: list[dict] = []
    for rec in board.values():
        status = str(rec.get("status", "todo")).lower()
        if status == "done":
            done.append(rec)
        else:
            pending.append(rec)
    return sort_pending_records(pending, now=now), sort_done_records(done)


def urgency_text(rec: dict, now: datetime) -> str:
    due_at = parse_iso_datetime(str(rec.get("due_at", "")))
    if due_at is None:
        return str(rec.get("due_hint", "未写明"))
    delta_hours = (due_at - now).total_seconds() / 3600
    if delta_hours < 0:
        return "已逾期"
    if delta_hours <= 24:
        return "24小时内"
    if delta_hours <= 72:
        return "3天内"
    return "常规"


def task_suggestion_and_example(task_text: str) -> tuple[str, str]:
    if any(x in task_text for x in ["背诵", "朗读"]):
        return (
            "先听录音再分段背诵，每段限时10分钟，最后整段抽背。",
            "示例：第一段朗读3遍 -> 盖住关键词复述 -> 家长抽背2次。",
        )
    if any(x in task_text for x in ["抄写", "默写", "听写"]):
        return (
            "先口头过一遍词义再动笔，写完立即对照课本订正。",
            "示例：每10个词一组，写完后用红笔改错并再写1遍错词。",
        )
    if any(x in task_text for x in ["作文", "写话", "读后感"]):
        return (
            "先列提纲（开头-中间-结尾），再按提纲写初稿，最后润色。",
            "示例：先写3点提纲，每点2句，再扩展成完整段落。",
        )
    if any(x in task_text for x in ["练习", "试卷", "阅读"]):
        return (
            "先限时独立完成，再集中订正错题并口头复述思路。",
            "示例：20分钟做题 + 10分钟订正，错题写“错因+正确方法”。",
        )
    return (
        "拆成10-15分钟的小步骤执行，先完成提交要求最明确的部分。",
        "示例：先完成拍照需提交部分，再处理复盘和巩固部分。",
    )


def format_report(
    extracted_tasks: list[Task],
    new_tasks: list[dict],
    pending_tasks: list[dict],
    done_tasks: list[dict],
    manual_updates: list[str],
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
    lines.append(f"- 本次识别任务：{len(extracted_tasks)} 条")
    lines.append(f"- 本次新增任务：{len(new_tasks)} 条")
    lines.append(f"- 当前未完成：{len(pending_tasks)} 条（已按截止时间优先）")
    lines.append(f"- 已完成保留：{len(done_tasks)} 条")
    lines.append("")

    if manual_updates:
        lines.append("## 0. 本次手动状态更新")
        for item in manual_updates:
            lines.append(f"- {item}")
        lines.append("")

    lines.append("## 1. 本次新增任务")
    if not new_tasks:
        lines.append("本次无新增任务。")
    else:
        lines.append("| 序号 | 任务ID | 发布时间 | 截止时间 | 作业内容 |")
        lines.append("|---|---|---|---|---|")
        for idx, rec in enumerate(new_tasks, start=1):
            source_time = parse_iso_datetime(str(rec.get("source_time", "")))
            source_text = source_time.strftime("%m-%d %H:%M") if source_time else "-"
            lines.append(
                f"| {idx} | `{str(rec.get('task_id', ''))[:8]}` | {source_text} | "
                f"{due_text_from_record(rec)} | {markdown_escape(str(rec.get('text', '')))} |"
            )
    lines.append("")

    lines.append("## 2. 未完成任务（截止日期临近优先）")
    if not pending_tasks:
        lines.append("当前没有未完成任务。")
    else:
        lines.append("| 优先级 | 任务ID | 截止时间 | 紧急度 | 作业内容 | 页码/提示 | 预计时长 |")
        lines.append("|---|---|---|---|---|---|---|")
        for idx, rec in enumerate(pending_tasks, start=1):
            pages_raw = rec.get("pages", [])
            pages = pages_raw if isinstance(pages_raw, list) else []
            page_text = "、".join(str(x) for x in pages) if pages else "-"
            lines.append(
                f"| {idx} | `{str(rec.get('task_id', ''))[:8]}` | {due_text_from_record(rec)} | "
                f"{urgency_text(rec, now)} | {markdown_escape(str(rec.get('text', '')))} | "
                f"{markdown_escape(page_text)} | {int_or_default(rec.get('eta_minutes'), 20)} 分钟 |"
            )
    lines.append("")

    lines.append("## 3. 3天完成计划")
    if not pending_tasks:
        lines.append("暂无待完成任务，建议每天保持20分钟语文阅读。")
    else:
        plan_seed = [record_to_task(rec, now) for rec in pending_tasks]
        plan = plan_tasks(plan_seed, now)
        for d in sorted(plan.keys()):
            day_name = WEEKDAY_MAP[d.weekday()]
            lines.append(f"### {d.strftime('%Y-%m-%d')}（{day_name}）")
            if not plan[d]:
                lines.append("- 预留机动时间：复盘错题/阅读20分钟。")
                continue
            for t in plan[d]:
                lines.append(
                    f"- [ ] {t.text}（约{t.eta_minutes}分钟，截止：{t.due_hint}，ID: `{make_task_id(t.text)[:8]}`）"
                )
            total = sum(x.eta_minutes for x in plan[d])
            lines.append(f"- 合计时长：约 {total} 分钟")
    lines.append("")

    lines.append("## 4. 各任务完成建议与示例")
    if not pending_tasks:
        lines.append("- 暂无未完成任务。")
    else:
        for rec in pending_tasks[:12]:
            task_text = str(rec.get("text", "")).strip()
            suggestion, example = task_suggestion_and_example(task_text)
            lines.append(
                f"- `{str(rec.get('task_id', ''))[:8]}` {task_text}；建议：{suggestion}；示例：{example}"
            )
    lines.append("")

    lines.append("## 5. 已完成任务（保留）")
    if not done_tasks:
        lines.append("暂无已完成任务记录。")
    else:
        lines.append("| 序号 | 完成时间 | 任务ID | 作业内容 |")
        lines.append("|---|---|---|---|")
        for idx, rec in enumerate(done_tasks[:30], start=1):
            done_at = parse_iso_datetime(str(rec.get("completed_at", "")))
            done_text = done_at.strftime("%m-%d %H:%M") if done_at else "-"
            lines.append(
                f"| {idx} | {done_text} | `{str(rec.get('task_id', ''))[:8]}` | {markdown_escape(str(rec.get('text', '')))} |"
            )
    lines.append("")

    lines.append("## 6. 可协助完成部分（我可以帮）")
    help_lines: list[str] = []
    for rec in pending_tasks:
        text = str(rec.get("text", "")).strip()
        can_help = str(rec.get("can_help", "")).strip() or infer_help_hint(text)
        help_lines.append(f"- `{str(rec.get('task_id', ''))[:8]}` {text} -> {can_help}")
    seen_help: set[str] = set()
    if not help_lines:
        lines.append("- 暂无待处理任务。")
    else:
        for item in help_lines:
            if item in seen_help:
                continue
            seen_help.add(item)
            lines.append(item)
    lines.append("")

    lines.append("## 7. 老师原始消息摘录（近3天）")
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

    if not recent_msgs:
        lines.append("- 近3天未抓取到老师消息。")

    return "\n".join(lines)


def process_once(
    raw_text: str,
    now: datetime,
    args: argparse.Namespace,
    state: dict,
) -> tuple[str, dict[str, int]]:
    messages = parse_chat_text(raw_text, now=now)
    extracted_tasks = extract_tasks(
        messages=messages,
        teacher_name=args.teacher_name,
        lookback_days=args.lookback_days,
        now=now,
    )
    board, new_tasks = upsert_task_board(extracted_tasks, state=state, now=now)
    manual_updates = apply_manual_status_updates(
        board=board,
        complete_tokens=list(args.complete_task or []),
        reopen_tokens=list(args.reopen_task or []),
        now=now,
    )
    pending_tasks, done_tasks = summarize_board(board, now=now)
    report = format_report(
        extracted_tasks=extracted_tasks,
        new_tasks=new_tasks,
        pending_tasks=pending_tasks,
        done_tasks=done_tasks,
        manual_updates=manual_updates,
        messages=messages,
        group_name=args.group_name,
        teacher_name=args.teacher_name,
        lookback_days=args.lookback_days,
        now=now,
    )
    stats = {
        "extracted_count": len(extracted_tasks),
        "new_count": len(new_tasks),
        "pending_count": len(pending_tasks),
        "done_count": len(done_tasks),
        "manual_update_count": len(manual_updates),
    }
    return report, stats


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
            has_manual_ops = bool(args.complete_task or args.reopen_task)
            should_process = (
                args.force_write
                or has_manual_ops
                or state.get("last_hash") != digest
            )

            if not should_process:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 无新内容，跳过生成。")
            else:
                now = datetime.now()
                report, stats = process_once(
                    raw_text=raw_text,
                    now=now,
                    args=args,
                    state=state,
                )
                output_path.write_text(report, encoding="utf-8")
                print(
                    f"[{now.strftime('%H:%M:%S')}] 已更新报告：{output_path}；"
                    f"识别 {stats['extracted_count']}，新增 {stats['new_count']}，"
                    f"未完成 {stats['pending_count']}，已完成 {stats['done_count']}。"
                )
                state["last_hash"] = digest
                state["last_report_at"] = now.isoformat(timespec="seconds")
                state["last_stats"] = stats
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
