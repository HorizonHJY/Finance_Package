import pyautogui
import threading
import time

def simulate_mouse_move(duration_min):
    end_time = time.time() + duration_min * 60
    while time.time() < end_time:
        pyautogui.move(1, 0)
        pyautogui.move(-1, 0)
        time.sleep(60)  # 每分钟动一次

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

    # 启动鼠标后台线程
    threading.Thread(target=simulate_mouse_move, args=(mins,), daemon=True).start()

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

    messagebox.showinfo("摸鱼已启动", msg)
