import os
import datetime
import threading
import time
import tkinter as tk
from tkinter import messagebox

import pyautogui  # 确保已执行：pip install pyautogui

# ========== 全局变量 ==========
remaining_seconds = 0  # 倒计时剩余秒数

# ========== 日志文件设置 ==========
log_dir = os.path.expanduser("~/FishLog")          # 日志目录，展开后会是 C:\Users\<用户名>\FishLog
log_file = os.path.join(log_dir, "moyu_log.txt")   # 日志文件路径
os.makedirs(log_dir, exist_ok=True)

# 如果文件不存在，先创建并写入表头
if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("日期\t开始时间\t时长（分钟）\n")

# ========== 读取已有日志，计算当前累计统计 ==========
lines = []
with open(log_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

total_minutes = 0
today_total = 0
today = datetime.datetime.now().strftime("%Y-%m-%d")
unique_days = set()

for line in lines:
    if line.startswith("日期") or not line.strip():
        continue
    try:
        date_str, _, minutes_str = line.strip().split("\t")
        minutes = int(minutes_str)
        total_minutes += minutes
        if date_str == today:
            today_total += minutes
        unique_days.add(date_str)
    except:
        continue

# 已解锁成就（启动时根据已有日志判断）
achievements = set()
if total_minutes >= 60:
    achievements.add("🐟 累计摸鱼超过 1 小时")
if total_minutes >= 300:
    achievements.add("🌊 摸鱼达人：累计 5 小时")
if today_total >= 60:
    achievements.add("📅 今日摸鱼满 1 小时")
if len(unique_days) >= 5:
    achievements.add("📆 连续摸鱼 5 天成就")

# ========== 后台自动移动鼠标的函数 ==========
def simulate_mouse_move(duration_min: int):
    """
    每3秒微动鼠标一次，防止系统/Teams 进入 away 状态。
    duration_min：摸鱼总时长（分钟）
    """
    end_ts = time.time() + duration_min * 60
    while time.time() < end_ts:
        pyautogui.move(1, 0)
        pyautogui.move(-1, 0)
        time.sleep(3)  # 每3秒动一次

# ========== 更新倒计时的函数 ==========
def update_countdown():
    global remaining_seconds
    if remaining_seconds > 0:
        mins, secs = divmod(remaining_seconds, 60)
        countdown_label.config(text=f"剩余时间：{mins:02d}:{secs:02d}")
        remaining_seconds -= 1
        root.after(1000, update_countdown)
    else:
        countdown_label.config(text="摸鱼时间到！")

# ========== GUI 主界面 ==========
root = tk.Tk()
root.title("摸鱼时间小助手")
root.geometry("320x220")  # 窗口大小可根据需求调整

label = tk.Label(root, text="请输入本次摸鱼时间（分钟）：")
label.pack(pady=8)

entry = tk.Entry(root)
entry.pack(pady=5)

countdown_label = tk.Label(root, text="剩余时间：00:00", font=("Arial", 14))
countdown_label.pack(pady=10)

def start_moyu():
    global total_minutes, today_total, achievements, unique_days, remaining_seconds

    # 1. 校验输入
    try:
        mins = int(entry.get())
        if mins <= 0:
            raise ValueError
    except ValueError:
        messagebox.showerror("错误", "请输入一个正整数（分钟）！")
        return

    # 2. 记录开始时间与日期
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    # 3. 写入日志文件
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{date_str}\t{time_str}\t{mins}\n")

    # 4. 更新统计数据
    total_minutes += mins
    if date_str == today:
        today_total += mins
    else:
        # 如果跨天，重置今天的累计
        today_total = mins
    unique_days.add(date_str)

    # 5. 启动后台线程模拟鼠标移动
    threading.Thread(target=simulate_mouse_move, args=(mins,), daemon=True).start()

    # 6. 初始化倒计时并启动更新
    remaining_seconds = mins * 60
    update_countdown()

    # 7. 生成提示信息
    msg = (
        f"✅ 本次摸鱼：{mins} 分钟\n"
        f"📅 今天累计：{today_total} 分钟\n"
        f"📊 历史总计：{total_minutes} 分钟"
    )

    # 8. 检查并解锁新成就
    new_achievements = []
    if total_minutes >= 60 and "🐟 累计摸鱼超过 1 小时" not in achievements:
        new_achievements.append("🐟 累计摸鱼超过 1 小时")
    if total_minutes >= 300 and "🌊 摸鱼达人：累计 5 小时" not in achievements:
        new_achievements.append("🌊 摸鱼达人：累计 5 小时")
    if today_total >= 60 and "📅 今日摸鱼满 1 小时" not in achievements:
        new_achievements.append("📅 今日摸鱼满 1 小时")
    if len(unique_days) >= 5 and "📆 连续摸鱼 5 天成就" not in achievements:
        new_achievements.append("📆 连续摸鱼 5 天成就")

    if new_achievements:
        achievements.update(new_achievements)
        msg += "\n\n🎉 新成就解锁：\n" + "\n".join(new_achievements)

    # 9. 弹出信息框
    messagebox.showinfo("摸鱼启动成功", msg)

button = tk.Button(root, text="开始摸鱼", width=15, command=start_moyu)
button.pack(pady=10)

# 启动 GUI 主循环
root.mainloop()
