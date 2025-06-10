from flask import Flask, jsonify, request,render_template,Response
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import math
app = Flask(__name__)

# 月份代码映射
MONTH_CODE_MAP = {
    "Jan": "F", "Feb": "G", "Mar": "H", "Apr": "J",
    "May": "K", "Jun": "M", "Jul": "N", "Aug": "Q",
    "Sep": "U", "Oct": "V", "Nov": "X", "Dec": "Z"
}

# 加载波动率数据 (这里使用模拟数据)
# 实际应用中应从文件或数据库加载
viya_vol = pd.DataFrame({
    "RISK_FACTOR": ["SB_CN_F24", "SB_CN_G24", "SB_CN_H24", "WT_CN_F24"],
    "VOLATILITY": [0.25, 0.26, 0.24, 0.30]
})

# 静态映射数据
curve_mapping = [
    {"commodity": "Soybean", "destination": "China", "curve_root": "SB_CN"},
    {"commodity": "Soybean", "destination": "Japan", "curve_root": "SB_JP"},
    {"commodity": "Soybean", "destination": "South Korea", "curve_root": "SB_KR"},
    {"commodity": "Wheat", "destination": "China", "curve_root": "WT_CN"},
    {"commodity": "Wheat", "destination": "India", "curve_root": "WT_IN"},
    {"commodity": "Corn", "destination": "Mexico", "curve_root": "CN_MX"},
    {"commodity": "Corn", "destination": "Brazil", "curve_root": "CN_BR"},
    {"commodity": "Palm Oil", "destination": "India", "curve_root": "PO_IN"},
    {"commodity": "Palm Oil", "destination": "Bangladesh", "curve_root": "PO_BD"},
    {"commodity": "Rapeseed", "destination": "Germany", "curve_root": "RS_DE"},
    {"commodity": "Rapeseed", "destination": "France", "curve_root": "RS_FR"},
    {"commodity": "Sugar", "destination": "USA", "curve_root": "SG_US"},
    {"commodity": "Sugar", "destination": "Canada", "curve_root": "SG_CA"},
    {"commodity": "Coffee", "destination": "Italy", "curve_root": "CF_IT"},
    {"commodity": "Coffee", "destination": "UK", "curve_root": "CF_UK"},
]

def index():
    all_commodities = sorted(set(row["commodity"] for row in curve_mapping))
    all_destinations = sorted(set(row["destination"] for row in curve_mapping))
    return render_template("PFE_front.html", commodities=all_commodities, destinations=all_destinations)

def get_destinations():
    commodity = request.json.get("commodity")
    destinations = sorted(set(
        row["destination"] for row in curve_mapping if row["commodity"] == commodity
    ))
    return jsonify(destinations)

def get_commodities():
    destination = request.json.get("destination")
    commodities = sorted(set(
        row["commodity"] for row in curve_mapping if row["destination"] == destination
    ))
    return jsonify(commodities)

def get_curve_root():
    data = request.json
    commodity = data["commodity"]
    destination = data["destination"]
    for row in curve_mapping:
        if row["commodity"] == commodity and row["destination"] == destination:
            return jsonify({"curve_root": row["curve_root"]})
    return jsonify({"curve_root": "Not Found"})

def get_available_months():
    months = pd.date_range("2024-01-01", "2025-12-01", freq="MS").strftime("%Y-%m").tolist()
    return jsonify(months)


def calculate_pfe():
    data = request.json
    comm = data["commodity"]
    dest = data["destination"]
    dirc = data["direction"]
    position = float(data["position"])
    price = float(data["price"])
    # 1) 获取曲线根
    curve_root = None
    for row in curve_mapping:
        if row["commodity"] == comm and row["destination"] == dest:
            curve_root = row["curve_root"]
            break

    if not curve_root:
        return jsonify({"error": "Mapping not found"}), 404

    # 2) 解析交割月
    try:
        tgt = datetime.strptime(data["deliver_date"] + "-01", "%Y-%m-%d")
        mon = tgt.strftime('%b')
        short_m = MONTH_CODE_MAP.get(mon, mon[0]) + tgt.strftime('%y')
        risk_curve = f"{curve_root}_{short_m}"
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    # 3) 获取波动率
    vol_row = viya_vol[viya_vol['RISK_FACTOR'] == risk_curve]
    if vol_row.empty:
        return jsonify({"error": "Volatility data not found"}), 404

    vol = vol_row.iloc[0]['VOLATILITY']
    # 4) 计算剩余年化时间
    eom = (tgt.replace(day=1) + relativedelta(months=1) - relativedelta(days=1))
    eom_date = eom.date()
    tte = max((eom_date - date.today()).days / 365.25, 0)

    # 5) 计算单位风险敞口
    buy_term = 1.645 * vol * math.sqrt(tte) - 0.5 * vol ** 2 * tte
    sell_term = -1.645 * vol * math.sqrt(tte) - 0.5 * vol ** 2 * tte

    if dirc == "Buy":
        unit_exposure = price * (-1 + math.exp(buy_term))
    else:  # Sell
        unit_exposure = price * (1 - math.exp(sell_term))

    # 6) 计算总风险敞口 (单位敞口 * 头寸)
    total_exposure = unit_exposure * position

    return jsonify({
        "risk_curve": risk_curve,
        "vol": vol,
        "time_to_exp": round(tte, 6),
        "exposure": round(unit_exposure, 6),
        "total_exposure": round(total_exposure, 6)
    })

def export_csv():
    rows = request.json  # 接收一个列表
    df = pd.DataFrame(rows)
    csv_str = df.to_csv(index=False)
    return Response(
        csv_str,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=exposure_results.csv"})