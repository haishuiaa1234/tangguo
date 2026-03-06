from pathlib import Path

from fpdf import FPDF


ROOT = Path(__file__).resolve().parent
OUTPUT_PDF = ROOT / "parent_todo_summary_2026-03-06.pdf"


def read_text_file(name: str) -> str:
    path = ROOT / "deliverables" / name
    if not path.exists():
        return "（成品文件未找到）"
    return path.read_text(encoding="utf-8").strip()


tasks = [
    {
        "title": "资助告家长书（二选一填写，周一带回）",
        "deadline": "2026-03-09（周一）",
        "desc": "按“申请/不申请”二选一填写，不要空白，签名日期写全。",
        "advice": [
            "先确认是申请还是不申请，再抄写对应句子。",
            "家长签名后拍照留底，避免周一忘带。",
        ],
        "sample": read_text_file("aid_apply.txt"),
    },
    {
        "title": "课后服务班级花名册填写",
        "deadline": "建议 2026-03-06 当天完成",
        "desc": "老师要求尽快填写；如果某天有校外社团，要在备注里写清楚。",
        "advice": [
            "先看每周固定安排，再决定课后服务天数。",
            "有校外课按“字母（项目）”格式写备注，例如 A（足球）。",
        ],
        "sample": read_text_file("after_school_service_note_example.txt"),
    },
    {
        "title": "雷锋日活动（文字+图片，约10x10cm）",
        "deadline": "2026-03-06（今天）",
        "desc": "第三项需要孩子在家完成，提交“文字+图片”。",
        "advice": [
            "孩子先做一件具体小事（整理书桌、家务劳动）。",
            "拍一张横屏过程图，文字控制在 80-120 字。",
        ],
        "sample": read_text_file("leifeng_finished_text.txt"),
    },
    {
        "title": "妇女节活动（图片+5秒视频）",
        "deadline": "2026-03-07 12:00 前",
        "desc": "三项图片主题 + 新增“致敬她力量”5秒视频，均按横屏提交。",
        "advice": [
            "一次拍完三张图（读书/拥抱/家务），减少反复拍摄。",
            "视频直接一句话，孩子看镜头说完即可。",
        ],
        "sample": read_text_file("womens_day_finished_pack.txt"),
    },
    {
        "title": "植树节创意作品",
        "deadline": "2026-03-12 前带到班级",
        "desc": "可做简单手工卡片或小报，重在参与和整洁度。",
        "advice": [
            "优先选“树苗成长卡”这种低难度作品，30 分钟内可完成。",
            "让孩子自己写标题和一句口号，增强参与感。",
        ],
        "sample": read_text_file("tree_day_finished_pack.txt"),
    },
    {
        "title": "植树节种植照片上传（横屏）",
        "deadline": "2026-03-15 前上传收集表",
        "desc": "拍摄孩子参与种植过程的横屏照片，配一句说明即可提交。",
        "advice": [
            "拍 3 张：准备土壤、种植动作、完成成果，从中选 1 张最清晰的。",
            "配文写明“种了什么 + 学到什么”。",
        ],
        "sample": "照片说明：今天我和家人一起种下了一盆小绿植。我负责挖土、放苗、浇水。我学会了植物需要阳光和水，也要坚持照顾它慢慢长大。",
    },
    {
        "title": "3.5学习要求（日常习惯任务）",
        "deadline": "建议每日打卡",
        "desc": "静坐、亲子阅读、劳动整理三项常规，偏习惯养成。",
        "advice": [
            "按顺序做：静坐10分钟 -> 阅读20分钟 -> 劳动10分钟。",
            "做完拍 1 张阅读图或劳动图，方便后续留档。",
        ],
        "sample": read_text_file("daily_language_routine_checklist.txt"),
    },
]


class ParentTodoPDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("CJK", size=9)
        self.set_text_color(110, 96, 82)
        self.cell(0, 6, "家长待办任务汇总（2026-03-06 版）", align="R")
        self.ln(1)

    def footer(self):
        self.set_y(-12)
        self.set_font("CJK", size=9)
        self.set_text_color(120, 108, 97)
        self.cell(0, 8, f"第 {self.page_no()} 页", align="C")


def main() -> None:
    pdf = ParentTodoPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()

    font_path = Path("C:/Windows/Fonts/simhei.ttf")
    if not font_path.exists():
        raise FileNotFoundError("缺少中文字体 C:/Windows/Fonts/simhei.ttf")

    pdf.add_font("CJK", "", str(font_path))

    def mc(text: str, h: float = 6.0, **kwargs) -> None:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, h, text, **kwargs)

    pdf.set_font("CJK", size=19)
    pdf.set_text_color(52, 42, 33)
    mc("琅小柳洲东路一2班\n家长待办任务汇总", h=10)
    pdf.set_font("CJK", size=11)
    pdf.set_text_color(95, 84, 73)
    mc("整理范围：语文-王老师近3天通知（2026-03-04 至 2026-03-06）", h=7)
    pdf.ln(2)

    pdf.set_draw_color(212, 193, 171)
    pdf.set_fill_color(255, 248, 236)
    pdf.set_font("CJK", size=11)
    mc(
        "优先顺序：\n1. 今天（3月6日）：雷锋日文字+图片、课后服务表、资助单。\n2. 明天中午前（3月7日12:00）：妇女节图片+5秒视频。\n3. 下周内：植树节作品与种植照片。",
        h=7,
        border=1,
        fill=True,
    )
    pdf.ln(3)

    for idx, task in enumerate(tasks, start=1):
        pdf.set_font("CJK", size=13)
        pdf.set_text_color(42, 35, 29)
        mc(f"{idx}. {task['title']}", h=8)

        pdf.set_font("CJK", size=10.5)
        pdf.set_text_color(114, 62, 36)
        mc(f"截止：{task['deadline']}", h=6)

        pdf.set_text_color(68, 59, 50)
        mc(f"任务说明：{task['desc']}", h=6)

        pdf.set_text_color(52, 44, 37)
        mc("完成建议：", h=6)
        for row in task["advice"]:
            mc(f"- {row}", h=6)

        pdf.set_fill_color(252, 246, 235)
        pdf.set_text_color(48, 40, 33)
        mc("可直接使用成品：", h=6, border="LTR", fill=True)
        mc(task["sample"], h=6, border="LBR", fill=True)
        pdf.ln(3)

    pdf.output(str(OUTPUT_PDF))
    print(f"OK: {OUTPUT_PDF}")


if __name__ == "__main__":
    main()
