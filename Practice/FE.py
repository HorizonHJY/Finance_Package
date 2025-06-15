from typing import List, Tuple, Optional

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


def get_date_list(data_source: pd.DataFrame, risk_factor: str) -> List[Tuple[datetime, str]]:
    pattern = fr'^{risk_factor}:[A-Z][0-9]{{2}}$'  # 更严格的匹配
    factor_set = data_source[data_source['RISK_FACTOR'].str.contains(pattern, regex=True, na=False)]
    if factor_set.empty:
        print(f"警告: 风险因子 {risk_factor} 不存在或没有有效数据")
        return []
    # 提取日期信息并去重
    date_entries = []
    seen = set()  # 用于去重
    for _, row in factor_set.iterrows():
        rf = row['RISK_FACTOR']
        if rf in seen:
            continue
        seen.add(rf)
        # 解析日期部分 (如 ":M25" 中的 M 和 25)
        month_code = rf[-3:-2]  # 月份代码字母
        year_short = int(rf[-2:])
        try:
            month_num = trading_code_to_month[month_code]
            date_obj = datetime(2000 + year_short, month_num, 1)
            date_entries.append((date_obj, rf))
        except KeyError:
            print(f"警告: 忽略无效的月份代码 {month_code} 在 {rf}")
            continue
    # 按日期降序排序 (最近的日期在前)
    date_entries.sort(reverse=True, key=lambda x: x[0])
    return date_entries


def find_best_match(date_list: List[Tuple[datetime, str]],
                    target_date: datetime,
                    datasource: pd.DataFrame,
                    as_of_date: date) -> Optional[str]:
    # 统一转成 date 类型比较
    datasource['AS_OF_DATE'] = pd.to_datetime(datasource['AS_OF_DATE']).dt.date
    if not isinstance(as_of_date, date):
        as_of_date = pd.to_datetime(as_of_date).date()

    for date_obj, rf in date_list:
        if date_obj > target_date:
            continue
        if not datasource[
            (datasource['RISK_FACTOR'] == rf) &
            (datasource['AS_OF_DATE'] <= as_of_date)
        ].empty:
            return rf

    for date_obj, rf in reversed(date_list):
        if not datasource[
            (datasource['RISK_FACTOR'] == rf) &
            (datasource['AS_OF_DATE'] <= as_of_date)
        ].empty:
            return rf
    return None


def get_vol(datasource: pd.DataFrame, risk_curve: str, deliver_month: str, as_of_date: date) -> tuple:
    """
    简化后的主函数，只保留核心流程
    """
    try:
        # 1. 转换目标日期
        delivery_date = convert_deliver_month_to_date(deliver_month)
        if not delivery_date:
            return None, None

        # 2. 获取预处理好的日期列表
        date_list = get_date_list(datasource, risk_curve)
        if not date_list:
            return None, None

        # 3. 查找最佳匹配
        target_date = datetime(delivery_date.year, delivery_date.month, 1)
        best_rf = find_best_match(date_list, target_date, datasource, as_of_date)

        if not best_rf:
            return None, None

        # 4. 获取波动率
        vol_data = datasource[
            (datasource['RISK_FACTOR'] == best_rf) &
            (datasource['AS_OF_DATE'] <= pd.Timestamp(as_of_date))
            ]
        return best_rf, vol_data['VOLATILITY'].iloc[0] * math.sqrt(252)

    except Exception as e:
        print(f"获取波动率失败: {str(e)}")
        return None, None

    except Exception as e:
        print(f"获取波动率失败: {str(e)}")
        return None, None

# print(risk_curve_mapping('corn', 'Portugal'))
def run_comprehensive_tests():
    print("===== 精确匹配测试 =====")
    # 测试1: 精确匹配存在
    _test_case(
        "精确匹配存在",
        target=datetime(2025, 5, 1),
        expected="CURVE_A:K25",
        as_of=date(2025, 12, 31)
    )

    print("\n===== 早于匹配测试 =====")
    # 测试2: 匹配早于的最接近日期
    _test_case(
        "早于匹配(中间值)",
        target=datetime(2025, 5, 15),
        expected="CURVE_A:K25",
        as_of=date(2025, 12, 31)
    )
    # 新增测试：刚好在两个月中间
    _test_case(
        "早于匹配(等距)",
        target=datetime(2023, 5, 1),  # 在J23(4月)和K23(5月)中间
        expected="CURVE_A:K23",  # 等距时选择较早的
        as_of=date(2023, 12, 31)
    )

    print("\n===== 晚于匹配测试 =====")
    # 测试3: 需要匹配晚于的日期
    _test_case(
        "晚于匹配(所有都晚)",
        target=datetime(2022, 1, 1),
        expected="CURVE_A:J23",  # 最早的可用
        as_of=date(2023, 12, 31)
    )
    # 新增测试：部分晚于
    _test_case(
        "晚于匹配(部分晚于)",
        target=datetime(2024, 1, 15),  # 在J24(6月)和M24(5月)之前
        expected="CURVE_A:M24",  # 选择最接近的晚于日期
        as_of=date(2024, 12, 31)
    )

    print("\n===== 数据有效性测试 =====")
    # 测试5: 过滤过期的as_of_date
    _test_case(
        "全部数据过期",
        target=datetime(2024, 6, 1),
        expected=None,
        as_of=date(2023, 6, 30)
    )
    # 新增测试：部分数据有效
    _test_case(
        "部分数据有效",
        target=datetime(2024, 6, 1),
        expected="CURVE_A:J24",  # 虽然有两个M24但只有2024-01-01的可用
        as_of=date(2024, 6, 30)
    )

    print("\n===== 边界条件测试 =====")
    # 测试空输入
    _test_case(
        "空日期列表",
        target=datetime(2023, 1, 1),
        expected=None,
        as_of=date(2023, 12, 31),
        custom_date_list=[]
    )
    # 测试无效曲线
    _test_case(
        "无效曲线类型",
        target=datetime(2023, 1, 1),
        expected=None,
        as_of=date(2023, 12, 31),
        custom_date_list=[(datetime(2023, 1, 1), "INVALID_CURVE:X99")]
    )


def _test_case(name, target, expected, as_of, custom_date_list=None):
    """执行单个测试用例并打印结果"""
    actual = find_best_match(
        custom_date_list if custom_date_list else date_list,
        target,
        df,
        as_of
    )
    result = "✓" if actual == expected else "✗"
    print(f"{result} {name}:")
    print(f"  目标: {target.strftime('%Y-%m')}")
    print(f"  预期: {expected}")
    print(f"  实际: {actual}")
    if actual != expected:
        print("  !!! 测试失败 !!!")


# 执行增强版测试
run_comprehensive_tests()

