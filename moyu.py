import os
import datetime
import tkinter as tk
from tkinter import messagebox

# 日志文件设置
log_dir = os.path.expanduser("~/FishLog")
log_file = os.path.join(log_dir, "moyu_log.txt")
os.makedirs(log_dir, exist_ok=True)

# 读取已有日志
if os.path.exists(log_file):
    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
else:
    lines = []

# 统计信息
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

# 已解锁成就
achievements = set()
if total_minutes >= 60:
    achievements.add("🐟 累计摸鱼超过 1 小时")
if total_minutes >= 300:
    achievements.add("🌊 摸鱼达人：累计 5 小时")
if today_total >= 60:
    achievements.add("📅 今日摸鱼满 1 小时")
if len(unique_days) >= 5:
    achievements.add("📆 连续摸鱼 5 天成就")

# GUI 主界面
root = tk.Tk()
root.title("摸鱼时间小助手")

label = tk.Label(root, text="请输入本次摸鱼时间（分钟）:")
label.pack(pady=10)

entry = tk.Entry(root)
entry.pack(pady=5)

def start_moyu():
    global total_minutes, today_total, achievements

    try:
        mins = int(entry.get())
    except ValueError:
        messagebox.showerror("错误", "请输入整数分钟数！")
        return

    start_time = datetime.datetime.now()
    start_str = start_time.strftime("%H:%M:%S")
    date_str = start_time.strftime("%Y-%m-%d")

    # 写入日志
    if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("日期\t开始时间\t时长（分钟）\n")

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{date_str}\t{start_str}\t{mins}\n")

    total_minutes += mins
    today_total += mins
    unique_days.add(date_str)

    msg = f"✅ 本次摸鱼 {mins} 分钟已记录\n📅 今天累计：{today_total} 分钟\n📊 总计：{total_minutes} 分钟"

    # 成就解锁
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
        msg += "\n\n🎉 解锁成就：\n" + "\n".join(new_achievements)

    messagebox.showinfo("摸鱼完成", msg)

button = tk.Button(root, text="开始摸鱼", command=start_moyu)
button.pack(pady=10)

root.mainloop()