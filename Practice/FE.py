from typing import List, Tuple, Optional
from bisect import bisect_right
import pandas as pd
from datetime import datetime, date

from astropy.cosmology import available
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
    ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_Z25", 0.012192808719508], # Dec
    ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_X25", 0.0121066787877991],
    # ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_V25", 0.01252940022954], # Oct
    # ["2025-03-13", "2025-03-17 14:40:54", "Prncpl_CNSTNZ_SBMPS_CIF_U25", 0.0124320682614375], # Sep
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

# 1. 构造测试DataFrame
test_data = [
    # risk_factor            volatility  as_of_date
    ("CURVE_A:M23",         0.15,       date(2023,1,1)),
    ("CURVE_A:J23",         0.14,       date(2023,1,1)),
    ("CURVE_A:K23",         0.16,       date(2023,1,1)),
    ("CURVE_A:M24",         0.18,       date(2023,1,1)),  # 故意设置一个过期数据
    ("CURVE_A:M24",         0.19,       date(2024,1,1)),  # 有效数据
    ("CURVE_A:J24",         0.20,       date(2024,1,1)),
    ("CURVE_A:K25",         0.21,       date(2024,1,1)),
    ("CURVE_A:M25",         0.22,       date(2024,1,1)),
    ("OTHER_CURVE:M23",      0.30,       date(2023,1,1)),  # 其他曲线测试
]

df = pd.DataFrame(test_data, columns=["RISK_FACTOR", "VOLATILITY", "AS_OF_DATE"])

# 2. 构造date_list输入 (使用get_date_list函数生成)
date_list = [
    (datetime(2025,6,1), "CURVE_A:M25"),
    (datetime(2025,5,1), "CURVE_A:K25"),
    (datetime(2024,6,1), "CURVE_A:J24"),
    (datetime(2024,5,1), "CURVE_A:M24"),  # 注意有两个M24，不同as_of_date
    (datetime(2023,6,1), "CURVE_A:M23"),
    (datetime(2023,5,1), "CURVE_A:K23"),
    (datetime(2023,4,1), "CURVE_A:J23"),]



def convert_deliver_month_to_date(date_str: str) -> Optional[Tuple[datetime, str]]:
        """
        解析特殊日期格式(如'Jun-25')，返回datetime对象和标准化字符串

        参数:
            date_str: 日期字符串，支持格式:
                - 'Jun-25' (MMM-YY)
                - '2025-06' (YYYY-MM)
                - '202506' (YYYYMM)

        返回:
            (datetime对象, 标准化后的日期字符串) 或 None(解析失败时)
        """
        date_str = date_str.strip()
        try:
            # 尝试解析 MMM-YY 格式 (如 'Jun-25')
            if len(date_str) == 6 and '-' in date_str:
                month_str, year_short = date_str.split('-')
                dt = datetime.strptime(f"{month_str}-{year_short}", "%b-%y")
                return dt, dt.strftime("%b-%y")


        except ValueError as e:
            pass

        print(f"警告: 无法解析日期格式 '{date_str}' - 支持格式: MMM-YY, YYYY-MM, YYYYMM")
        return None


def country_mapping(commodity: str) -> list:
    country_list = curve_mapping.loc[curve_mapping['commodity'] == commodity, 'destination']
    return list(country_list)


def risk_curve_mapping(commodity: str, destination: str) -> str:
    sub_set = curve_mapping.loc[(curve_mapping['commodity'] == commodity) &
                                (curve_mapping['destination'] == destination),'curve_root'
    ]
    return sub_set.values[0]


def get_date_list(data_source: pd.DataFrame, risk_curve_root: str) -> List[Tuple[datetime, str]]:
    """
    从数据源中提取并处理日期信息，返回按日期排序的列表

    参数:
        data_source: 包含风险因子数据的DataFrame
        risk_curve_root: 风险曲线根名称(如"Prncpl_CNSTNZ_SBMPS_CIF")

    返回:
        按日期降序排列的(datetime, risk_factor)元组列表
    """
    # 构造匹配模式 - 更严格的匹配风险曲线格式
    pattern = fr'^{risk_curve_root}_[A-Z][0-9]{{2}}$'
    factor_set = data_source[data_source['RISK_FACTOR'].str.contains(pattern, regex=True, na=False)]

    if factor_set.empty:
        print(f"警告: 风险曲线 {risk_curve_root} 不存在或没有有效数据")
        return []

    date_entries = []
    seen = set()  # 用于去重

    for _, row in factor_set.iterrows():
        risk_factor = row['RISK_FACTOR']
        if risk_factor in seen:
            continue
        seen.add(risk_factor)

        # 提取月份代码和年份
        month_code = risk_factor[-3:-2]  # 如 'Q' in 'Q25'
        year_short = risk_factor[-2:]  # 如 '25' in 'Q25'

        # 反转月份代码映射 (代码->月份数字)
        code_to_month = {v: k for k, v in MONTH_CODE_MAP.items()}
        try:
            month_str = code_to_month[month_code]
            month_num = datetime.strptime(month_str, '%b').month
            year_full = 2000 + int(year_short)
            date_obj = datetime(year_full, month_num, 1)
            date_entries.append((date_obj, risk_factor))
        except (KeyError, ValueError) as e:
            print(f"警告: 忽略无效的月份代码 {month_code} 在 {risk_factor}")
            continue

    # 按日期降序排序 (最近的日期在前)
    date_entries.sort(reverse=True, key=lambda x: x[0])
    return date_entries

# get_date_list(viya_vol,"Prncpl_CNSTNZ_SBMPS_CIF")


def match_curve(risk_curve_root: str, deliver_month: str,
                data_source: pd.DataFrame = None) -> str | None:
    """
    匹配最适合给定交付月份的风险曲线

    参数:
        risk_curve_root: 风险曲线根名称
        deliver_month: 交付月份字符串(支持多种格式)
        data_source: 数据源DataFrame(可选)

    返回:
        匹配的风险因子字符串，或None(如果没有匹配)
    """
    try:
        # 使用新函数解析日期
        parsed = convert_deliver_month_to_date(deliver_month)
        if not parsed:
            return None
        delivery_date, _ = parsed

        # 获取日期列表
        date_list = get_date_list(data_source, risk_curve_root)
        if not date_list:
            return None

        # 处理边界情况
        if delivery_date > date_list[0][0]:  # 大于最大日期
            return date_list[0][1]
        if delivery_date < date_list[-1][0]:  # 小于最小日期
            return date_list[-1][1]

        # 寻找最接近的日期
        closest = None
        min_diff = float('inf')

        for date_obj, risk_factor in date_list:
            diff = abs((delivery_date - date_obj).days)

            if diff < min_diff:
                min_diff = diff
                closest = risk_factor
            elif diff == min_diff:
                # 如果距离相同，选择较早的日期(前一个)
                if date_obj < delivery_date:
                    closest = risk_factor

        return closest

    except Exception as e:
        print(f"错误: 无法匹配风险曲线 {risk_curve_root} - {str(e)}")
        return None

result = match_curve('Prncpl_CNSTNZ_SBMPS_CIF','Sep-25',viya_vol)
print(result)

def get_vol(datasource: pd.DataFrame, risk_curve_root: str, deliver_month: str):
    risk_curve = match_curve(risk_curve_root, deliver_month)
    filtered = datasource[(datasource['RISK_FACTOR'] == risk_curve)]
    if filtered.empty:
        print('there')
        return None, None

    # latest_vol = filtered.sort_values('AS_OF_DATE', ascending=False).iloc[0]
    return risk_curve, filtered['VOLATILITY'].iloc[0] * math.sqrt(252)


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
