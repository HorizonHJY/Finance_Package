import os
import datetime
import threading
import time
import tkinter as tk
from tkinter import messagebox

import pyautogui  # 确保已执行：pip install pyautogui

# ========== 全局变量 ==========
session_end_ts = 0       # 记录当前摸鱼截止时间戳
stop_flag = False        # 停止标志
session_thread = None    # 模拟鼠标点击的线程
countdown_job = None     # 用于取消 after 回调的标识

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


# ========== 后台自动点击鼠标的函数 ==========
def simulate_mouse_click():
    """
    每3秒点击一次鼠标，防止系统/Teams 进入 away 状态。
    检查 stop_flag 和当前时间戳来决定是否继续。
    """
    global stop_flag, session_end_ts
    while time.time() < session_end_ts and not stop_flag:
        pyautogui.click()
        time.sleep(3)


# ========== 更新倒计时的函数 ==========
def update_countdown():
    global countdown_job
    now_ts = time.time()
    remaining_secs = max(int(session_end_ts - now_ts), 0)
    if remaining_secs > 0 and not stop_flag:
        mins, secs = divmod(remaining_secs, 60)
        countdown_label.config(text=f"剩余时间：{mins:02d}:{secs:02d}")
        # 每秒更新一次
        countdown_job = root.after(1000, update_countdown)
    else:
        countdown_label.config(text="已停止")
        # 停止倒计时，无需继续 after 回调

# ========== 停止按钮触发 ==========
def stop_moyu():
    global stop_flag, session_end_ts
    stop_flag = True
    session_end_ts = time.time()  # 让线程和倒计时结束
    if countdown_job:
        root.after_cancel(countdown_job)
    countdown_label.config(text="已停止")
    messagebox.showinfo("已停止", "摸鱼已提前停止。")


# ========== GUI 主界面 ==========
root = tk.Tk()
root.title("摸鱼时间小助手")
root.geometry("320x240")  # 窗口大小可根据需求调整

label = tk.Label(root, text="请输入本次摸鱼时间（分钟）：")
label.pack(pady=8)

entry = tk.Entry(root)
entry.pack(pady=5)

countdown_label = tk.Label(root, text="剩余时间：00:00", font=("Arial", 14))
countdown_label.pack(pady=10)

def start_moyu():
    global total_minutes, today_total, achievements, unique_days
    global session_end_ts, stop_flag, session_thread, countdown_job, today

    # 1. 校验输入
    try:
        mins = int(entry.get())
        if mins <= 0:
            raise ValueError
    except ValueError:
        messagebox.showerror("错误", "请输入一个正整数（分钟）！")
        return

    now = datetime.datetime.now()
    now_ts = time.time()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    # 2. 写入日志文件
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{date_str}\t{time_str}\t{mins}\n")

    # 3. 更新统计数据
    total_minutes += mins
    if date_str == today:
        today_total += mins
    else:
        # 跨天情况下重置今天累计
        today = date_str
        today_total = mins
    unique_days.add(date_str)

    # 4. 如果已有活动线程在运行，就延长 session_end_ts 否则启动新的线程
    if session_thread and session_thread.is_alive() and time.time() < session_end_ts and not stop_flag:
        # 延长会话时间
        session_end_ts += mins * 60
    else:
        # 新会话开始
        stop_flag = False
        session_end_ts = now_ts + mins * 60
        session_thread = threading.Thread(target=simulate_mouse_click, daemon=True)
        session_thread.start()
        # 开始倒计时
        update_countdown()

    # 5. 生成提示信息
    msg = (
        f"🐟 本次摸鱼：{mins} 分钟\n"
        f"📅 今日累计：{today_total} 分钟\n"
        f"📊 历史总计：{total_minutes} 分钟"
    )

    # 6. 检查并解锁新成就
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

    # 7. 弹出信息框
    messagebox.showinfo("摸鱼启动成功", msg)

# 开始与停止按钮
button_frame = tk.Frame(root)
button_frame.pack(pady=10)

start_button = tk.Button(button_frame, text="开始摸鱼", width=12, command=start_moyu)
start_button.grid(row=0, column=0, padx=5)

stop_button = tk.Button(button_frame, text="提前停止", width=12, command=stop_moyu)
stop_button.grid(row=0, column=1, padx=5)

# 启动 GUI 主循环
root.mainloop()

