from flask import Flask, jsonify, request,render_template,Response
from Practice.FE import *
app = Flask(__name__)

def index():
    all_commodities = sorted(set(row["commodity"] for row in curve_mapping_source))
    all_destinations = sorted(set(row["destination"] for row in curve_mapping_source))
    return render_template("PFE_front.html", commodities=all_commodities, destinations=all_destinations)

def get_destinations():
    commodity = request.json.get("commodity")
    destinations = sorted(set(
        row["destination"] for row in curve_mapping_source if row["commodity"] == commodity
    ))
    return jsonify(destinations)

def get_commodities():
    destination = request.json.get("destination")
    commodities = sorted(set(
        row["commodity"] for row in curve_mapping_source if row["destination"] == destination
    ))
    return jsonify(commodities)

def get_curve_root():
    data = request.json
    commodity = data["commodity"]
    destination = data["destination"]
    for row in curve_mapping_source:
        if row["commodity"] == commodity and row["destination"] == destination:
            return jsonify({"curve_root": row["curve_root"]})
    return jsonify({"curve_root": "Not Found"})

def get_available_months():
    data = request.get_json()  # POST JSON
    comm = data.get("commodity")
    dest = data.get("destination")
    curve_root = risk_curve_mapping(comm,dest)
    months = get_available_months_backend(viya_vol, curve_root)
    return jsonify(months)

def get_available_months_backend(data_source: pd.DataFrame, risk_factor: str):
    factor_set = data_source[data_source['RISK_FACTOR'].str.startswith(risk_factor)]
    if factor_set.empty:
        print(f"The factor {risk_factor} doesn't exist!")
        return []

    copy_set = factor_set.copy()
    copy_set['Month_Code'] = copy_set['RISK_FACTOR'].str[-3:]
    copy_set['Month'] = copy_set['Month_Code'].str[0]
    copy_set['year'] = 2000 + copy_set['Month_Code'].str[1:].astype(int)
    copy_set['Month_NUM'] = copy_set['Month'].map(trading_code_to_month ).astype(int)

    sort_data = copy_set.sort_values(by=['year', 'Month_NUM'], ascending=[False, False])

    formatted_dates = sort_data.apply(
        lambda row: f"{datetime(1900, row['Month_NUM'], 1).strftime('%b')}-{str(row['year'])[-2:]}",
        axis=1
    ).tolist()

    return jsonify(formatted_dates)

# get_available_months(viya_vol,"Prncpl_CNSTNZ_SBMPS_CIF")

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
    rows = request.json
    df = pd.DataFrame(rows)
    csv_str = df.to_csv(index=False)
    return Response(
        csv_str,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=exposure_results.csv"})