import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import math


# 月份代码映射
MONTH_CODE_MAP = {
    "Jan": "F", "Feb": "G", "Mar": "H", "Apr": "J",
    "May": "K", "Jun": "M", "Jul": "N", "Aug": "Q",
    "Sep": "U", "Oct": "V", "Nov": "X", "Dec": "Z"
}

trading_code_to_month = {
    'F': 1,  # Jan
    'G': 2,  # Feb
    'H': 3,  # Mar
    'J': 4,  # Apr
    'K': 5,  # May
    'M': 6,  # Jun
    'N': 7,  # Jul
    'Q': 8,  # Aug
    'U': 9,  # Sep
    'V': 10, # Oct
    'X': 11, # Nov
    'Z': 12  # Dec
}

vol_data = [
    ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_U26", 0.00710643397364407],
    ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_Q26", 0.00708482227348857],
    ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_N26", 0.00710612753436603],
    ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_M26", 0.00956784736505066],
    ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_K26", 0.0096002280257766],
    ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_J26", 0.00945360062276853],
    ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_H26", 0.00958367862919055],
    ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_G26", 0.00931276655325378],
    ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_F26", 0.0116875122485111],
    ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_Z25", 0.012192808719508],
    ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_X25", 0.0121066787877991],
    ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_V25", 0.01252940022954],
    ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_U25", 0.0124320682614375],
    ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_Q25", 0.0128084543445655],
    ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_N25", 0.0144711914706103],
    ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_M25", 0.014418468605279],
]

columns = ["AS_OF_DATE", "RUN_TIME", "RISK_FACTOR", "VOLATILITY"]

viya_vol = pd.DataFrame(vol_data, columns=columns)

# 静态映射数据
curve_mapping_source = [
    {"commodity": "test 1", "destination": "test2", "curve_root": "Prncpl_CNSTNZ_SBMPS_CIF"},
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

curve_mapping = pd.DataFrame(curve_mapping_source)

def get_vol(rsk_fac: str) -> float:
    result = viya_vol.loc[viya_vol['RISK_FACTOR'] == rsk_fac, 'VOLATILITY']
    return result.item()


# a = pfe_calculator('Sell', 357.0, 0.234603017797129, 0.085555555555555)


def pfe_calculator(direction: str, contract_price: float, contract_vol: float, time_to_exp: float) -> float:
    """
    Calculates a value based on the provided inputs, mirroring an Excel formula.

    Args:
        direction: 'Buy' or 'Sell' (string).
        contract_price: Numeric value.
        contract_vol: Numeric value.
        time_to_exp: Numeric value.

    Returns:
        The calculated result or "ERROR" if an error occurs.
    """
    buy_adjust_term = 1.645 * contract_vol * math.sqrt(time_to_exp) - 0.5 * contract_vol ** 2 * time_to_exp
    sell_adjust_term = -1.645 * contract_vol * math.sqrt(time_to_exp) - 0.5 * contract_vol ** 2 * time_to_exp

    if direction == 'Buy':
        result = contract_price * (-1 + math.exp(buy_adjust_term))
    else:  # Assumed to be "Sell" if not "Buy"
        result = contract_price * (1 - math.exp(sell_adjust_term))

    return result


def country_mapping(commodity: str) -> list:
    country_list = curve_mapping.loc[curve_mapping['commodity'] == commodity, 'destination']
    return list(country_list)


def risk_curve_mapping(commodity: str, destination: str) -> str:
    sub_set = curve_mapping.loc[(curve_mapping['commodity'] == commodity) &
                                (curve_mapping['destination'] == destination),'curve_root'
    ]
    return sub_set.values[0]


def commodity_mapping(destination: str) -> list:
    commodity_list = curve_mapping.loc[curve_mapping['Destination'] == destination, 'Commodity']
    return list(commodity_list)


# print(risk_curve_mapping('corn', 'Portugal'))
