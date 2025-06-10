from dateutil.relativedelta import relativedelta
import math
import pandas as pd

def date_trans(start_date, month_length):
    result = []
    for i in range(month_length):
        target_date = start_date + relativedelta(months=i)
        eomonth = (target_date.replace(day=1) + relativedelta(months=1)) - relativedelta(days=1)
        month_str = target_date.strftime('%b-%y')
        short_month = MONTH_CODE_MAP[target_date.strftime('%b')] + target_date.strftime('%y')
        date_in_number = (eomonth - datetime(year=1899, month=12, day=30)).days
        result.append({
            'month_str': month_str,
            'short_month': short_month,
            'date_number': date_in_number
        })
    return result

def replace_space_with_underscore(text: str) -> str:
    return text.replace(" ", "_")

def get_vol(rsk_fac: str):
    result = viya_vol.loc[viya_vol['RISK_FACTOR'] == rsk_fac, ['AS_OF_DATE', 'VOLATILITY']]
    time_stamp = pd.to_datetime(result['AS_OF_DATE'].iloc[0]).date()
    vol = result['VOLATILITY'].iloc[0]
    return time_stamp, vol

def pfe_calculator(direction: str, contract_price: float, contract_vol: float, time_to_exp: float) -> float:
    """
    Calculates a value based on the provided inputs, mirroring an Excel formula.
    Args:
        direction: “Buy” or “Sell” (string).
        contract_price: Numeric value.
        contract_vol: Numeric value.
        time_to_exp: Numeric value.
    Returns:
        The calculated result or "ERROR" if an error occurs.
    """
    buy_adjust_term = 1.645 * contract_vol * math.sqrt(time_to_exp) - 0.5 * contract_vol ** 2 * time_to_exp
    sell_adjust_term = -1.645 * contract_vol * math.sqrt(time_to_exp) - 0.5 * contract_vol ** 2 * time_to_exp

    if direction == "Buy":
        result = contract_price * (-1 + math.exp(buy_adjust_term))
    else:
        result = contract_price * (1 - math.exp(sell_adjust_term))
    return result

def country_mapping(commodity: str) -> list:
    country_list = curve_mapping.loc[curve_mapping['Commodity'] == commodity, 'Destination']
    return list(country_list)

def risk_curve_mapping(commodity: str, destination: str) -> list:
    sub_set = curve_mapping.loc[
        (curve_mapping['Commodity'] == commodity) &
        (curve_mapping['Destination'] == destination),
        'Curve_Root'
    ]
    return sub_set.values.tolist()

def commodity_mapping(destination: str) -> list:
    commodity_list = curve_mapping.loc[curve_mapping['Destination'] == destination, 'Commodity']
    return list(commodity_list)

def find_furthest_date(data_source: pd.DataFrame, risk_factor: str):
    factor_set = data_source[data_source['RISK_FACTOR'].str.startswith(risk_factor)]
    if factor_set.empty:
        print(f"The factor {risk_factor} doesn't exist!")
        return None

    copy_set = factor_set.copy()
    copy_set['Month_Code'] = factor_set['RISK_FACTOR'].str[-3:]
    copy_set['Month'] = copy_set['Month_Code'].str[0]
    copy_set['year'] = 2000 + copy_set['Month_Code'].str[1:].astype(int)
    copy_set['Month_NUM'] = copy_set['Month'].map(trading_code_to_month).astype(int)
    sort_data = copy_set.sort_values(by=['year', 'Month_NUM'], ascending=[False, False])
    return sort_data


from dateutil.relativedelta import relativedelta
import math
import pandas as pd
import os
from datetime import datetime


# 假设以下全局变量已在其他位置定义
# MONTH_CODE_MAP, curve_mapping, viya_vol, trading_code_to_month

def create_pfe_template(file_path: str = "PFE_template.xlsx") -> None:
    """
    创建PFE计算模板Excel文件

    Args:
        file_path: 模板文件保存路径
    """
    columns = [
        "commodity",  # 品种
        "destination",  # 交割地
        "deliver_month",  # 交割月 (格式: MMM-YY 如 Jan-25)
        "direction",  # Buy/Sell
        "contract_price",  # 合约价格
        "contract_vol",  # 合约波动率 (可选)
        "time_to_exp"  # 到期时间(年化)
    ]

    # 创建带示例数据的DataFrame
    sample_data = [
        ["Crude", "US", "Jan-25", "Buy", 75.0, 0.25, 0.5],
        ["Gas", "EU", "Feb-25", "Sell", 30.0, 0.18, 0.3]
    ]

    template_df = pd.DataFrame(sample_data, columns=columns)

    # 写入Excel
    with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
        template_df.to_excel(writer, index=False, sheet_name="PFE")

        # 添加数据验证
        workbook = writer.book
        worksheet = writer.sheets["PFE"]

        # 方向列数据验证 (Buy/Sell)
        direction_validation = {
            'validate': 'list',
            'source': ['Buy', 'Sell']
        }
        worksheet.data_validation('D2:D100', direction_validation)

        # 添加说明
        worksheet.write('H1', 'Instructions:')
        worksheet.write('H2', '1. 交割月格式: MMM-YY (如Jan-25)')
        worksheet.write('H3', '2. contract_vol可选: 如留空将自动计算')

    print(f"PFE模板已创建: {file_path}")


def calculate_and_update_pfe(file_path: str = "PFE_template.xlsx") -> pd.DataFrame:
    """
    从Excel读取数据，计算PFE值和风险曲线

    Args:
        file_path: Excel文件路径

    Returns:
        包含计算结果DataFrame
    """
    # 读取Excel数据
    try:
        df = pd.read_excel(file_path, sheet_name="PFE")
    except FileNotFoundError:
        print(f"错误: 文件不存在 {file_path}")
        print("请先创建模板: create_pfe_template()")
        return pd.DataFrame()

    # 数据验证
    required_columns = ["commodity", "destination", "deliver_month",
                        "direction", "contract_price", "time_to_exp"]
    if not all(col in df.columns for col in required_columns):
        missing = set(required_columns) - set(df.columns)
        print(f"错误: 缺少必要列: {', '.join(missing)}")
        return df

    # 1. 计算Risk_Curve
    def get_risk_curve(row):
        curves = risk_curve_mapping(row["commodity"], row["destination"])
        return curves[0] if curves else ""

    df["Risk_Curve"] = df.apply(get_risk_curve, axis=1)

    # 2. 自动填充缺失的波动率 (使用get_vol函数)
    if "contract_vol" not in df.columns or df["contract_vol"].isnull().any():
        print("检测到缺失波动率，自动计算中...")

        def auto_fill_vol(row):
            # 这里需要实现您的get_vol逻辑
            # 示例: timestamp, vol = get_vol(row["Risk_Curve"])
            return 0.2  # 示例值

        df["contract_vol"] = df.apply(auto_fill_vol, axis=1)

    # 3. 计算PFE值
    def calculate_pfe(row):
        try:
            return pfe_calculator(
                row["direction"],
                float(row["contract_price"]),
                float(row["contract_vol"]),
                float(row["time_to_exp"])
            )
        except (ValueError, TypeError) as e:
            print(f"计算错误 行{row.name}: {e}")
            return None

    df["PFE_Value"] = df.apply(calculate_pfe, axis=1)

    # 4. 保存结果到新文件
    result_path = file_path.replace(".xlsx", "_result.xlsx")
    with pd.ExcelWriter(result_path, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="PFE_Results")

        # 设置Excel格式
        workbook = writer.book
        worksheet = writer.sheets["PFE_Results"]

        # 设置数字格式
        num_format = workbook.add_format({"num_format": "#,##0.00"})
        worksheet.set_column("E:E", 15, num_format)  # contract_price
        worksheet.set_column("F:F", 15, num_format)  # contract_vol
        worksheet.set_column("G:G", 15, num_format)  # time_to_exp
        worksheet.set_column("I:I", 15, num_format)  # PFE_Value

        # 设置列宽
        col_widths = {"A": 12, "B": 15, "C": 15, "D": 10, "H": 20}
        for col, width in col_widths.items():
            worksheet.set_column(f"{col}:{col}", width)

    print(f"计算结果已保存至: {result_path}")
    return df


# 使用示例
if __name__ == "__main__":
    # 创建模板 (如果不存在)
    if not os.path.exists("PFE_template.xlsx"):
        create_pfe_template()

    # 计算PFE结果
    result_df = calculate_and_update_pfe()
    print("计算完成!")
    print(result_df.head())