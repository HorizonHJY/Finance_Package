# pfe_controller.py
from flask import render_template, request, jsonify
import pandas as pd

# 静态映射数据
mapping_data = [
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
    all_commodities = sorted(set(row["commodity"] for row in mapping_data))
    all_destinations = sorted(set(row["destination"] for row in mapping_data))
    return render_template("PFE_front.html", commodities=all_commodities, destinations=all_destinations)

def get_destinations():
    commodity = request.json.get("commodity")
    destinations = sorted(set(
        row["destination"] for row in mapping_data if row["commodity"] == commodity
    ))
    return jsonify(destinations)

def get_commodities():
    destination = request.json.get("destination")
    commodities = sorted(set(
        row["commodity"] for row in mapping_data if row["destination"] == destination
    ))
    return jsonify(commodities)

def get_curve_root():
    data = request.json
    commodity = data["commodity"]
    destination = data["destination"]
    for row in mapping_data:
        if row["commodity"] == commodity and row["destination"] == destination:
            return jsonify({"curve_root": row["curve_root"]})
    return jsonify({"curve_root": "Not Found"})

def get_available_months():
    months = pd.date_range("2024-01-01", "2025-12-01", freq="MS").strftime("%Y-%m").tolist()
    return jsonify(months)
