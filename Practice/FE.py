import numpy as np
from dateutil.relativedelta import relativedelta
import math
import pandas as pd
import os
from datetime import datetime, date

# 1. 月份代码映射
MONTH_CODE_MAP = {
    'Jan': 'F', 'Feb': 'G', 'Mar': 'H', 'Apr': 'J', 'May': 'K', 'Jun': 'M',
    'Jul': 'N', 'Aug': 'Q', 'Sep': 'U', 'Oct': 'V', 'Nov': 'X', 'Dec': 'Z'
}

# 2. 交易代码到月份数字的映射
trading_code_to_month = {
    'F': 1, 'G': 2, 'H': 3, 'J': 4, 'K': 5, 'M': 6,
    'N': 7, 'Q': 8, 'U': 9, 'V': 10, 'X': 11, 'Z': 12
}

# 3. 曲线映射数据
curve_mapping_data = {
    'Commodity': ['Crude', 'Crude', 'Gas', 'Gas', 'Coal', 'Coal'],
    'Destination': ['US', 'EU', 'US', 'EU', 'China', 'India'],
    'Curve_Root': ['CL', 'BRENT', 'HH', 'TTF', 'QINHUANGDAO', 'INDIAN_COAL']
}
risk_curve_mapping = pd.DataFrame(curve_mapping_data)

# 4. 波动率数据 (viya_vol)
# 创建日期范围
dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='ME')  # 修正为 'ME'
# 创建风险因子
risk_factors = []
for curve in risk_curve_mapping['Curve_Root'].unique():
    for year in [24, 25, 26]:
        for month_code in ['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z']:
            risk_factors.append(f"{curve}_{month_code}{year}")

# 随机生成波动率数据
np.random.seed(42)
vol_data = {
    'RISK_FACTOR': np.random.choice(risk_factors, size=100),
    'AS_OF_DATE': np.random.choice(dates, size=100),
    'VOLATILITY': np.random.uniform(0.1, 0.5, size=100)
}
viya_vol = pd.DataFrame(vol_data)


def convert_deliver_month_to_date(month_str: str) -> date:
    """
    将交割月字符串（如"Jan-25"）转换为日期对象（该月的最后一天）
    """
    try:
        # 解析字符串，例如："Jan-25" -> 2025-01-01
        date_obj = datetime.strptime(month_str, '%b-%y').date()
        # 计算当月最后一天
        next_month = date_obj.replace(day=1) + relativedelta(months=1)
        last_day = next_month - relativedelta(days=1)
        return last_day
    except Exception as e:
        print(f"转换交割月字符串错误: {month_str} - {e}")
        return None


def calculate_time_to_expiry(as_of_date: date, delivery_date: date) -> float:
    """
    计算到期时间（年化）
    """
    # 修复类型检查
    if not isinstance(as_of_date, date) or not isinstance(delivery_date, date):
        return 0.0

    # 确保交割日期在评估日期之后
    if delivery_date <= as_of_date:
        return 0.0

    # 计算天数差并年化
    days_diff = (delivery_date - as_of_date).days
    return days_diff / 365.0


def pfe_calculator(direction: str, price: float, vol: float, time_to_exp: float) -> float:
    """
    计算PFE值

    Args:
        direction: 交易方向 (Buy/Sell)
        price: 合约价格
        vol: 波动率
        time_to_exp: 到期时间 (年化)

    Returns:
        计算后的PFE值
    """
    if vol <= 0 or time_to_exp <= 0:
        return 0.0

    # 95%置信水平的乘数 (1.645)
    multiplier = 1.645
    base_pfe = price * vol * math.sqrt(time_to_exp) * multiplier

    # 根据方向确定符号
    if direction == "Buy":
        return base_pfe
    elif direction == "Sell":
        return -base_pfe
    else:
        return 0.0


def get_vol(risk_curve: str, deliver_month: str, as_of_date: date):
    """
    获取风险曲线的波动率

    Args:
        risk_curve: 风险曲线
        deliver_month: 交割月 (格式: MMM-YY)
        as_of_date: 评估日期

    Returns:
        (风险因子, 波动率)
    """
    try:
        # 转换交割月为日期
        delivery_date = convert_deliver_month_to_date(deliver_month)
        if not delivery_date:
            return None, None

        # 获取月份代码和两位年份
        month_str = delivery_date.strftime('%b')
        month_code = MONTH_CODE_MAP.get(month_str)
        year_short = delivery_date.strftime('%y')

        # 构建风险因子
        risk_factor = f"{risk_curve}_{month_code}{year_short}"

        # 转换为Timestamp用于比较
        as_of_timestamp = pd.Timestamp(as_of_date)

        # 筛选匹配的风险因子和日期
        filtered = viya_vol[
            (viya_vol['RISK_FACTOR'] == risk_factor) &
            (viya_vol['AS_OF_DATE'] <= as_of_timestamp)
            ]

        if filtered.empty:
            return None, None

        # 获取最近的波动率
        latest_vol = filtered.sort_values('AS_OF_DATE', ascending=False).iloc[0]
        return risk_factor, latest_vol['VOLATILITY']

    except Exception as e:
        print(f"获取波动率错误: {risk_curve}, {deliver_month} - {e}")
        return None, None


def create_pfe_template(file_path: str = "PFE_template.xlsx") -> None:
    """
    创建PFE计算模板Excel文件

    Args:
        file_path: 模板文件保存路径
    """
    columns = [
        "as_of_date",  # 评估日期（日期格式）
        "commodity",  # 品种
        "destination",  # 交割地
        "deliver_month",  # 交割月 (格式: MMM-YY 如 Jan-25)
        "direction",  # Buy/Sell
        "contract_price",  # 合约价格
        "Existing_MTM",  # 现有市值
        "contract_vol"  # 合约波动率 (可选)
    ]

    # 创建带示例数据的DataFrame
    sample_data = [
        [datetime(2023, 12, 31).date(), "Crude", "US", "Jan-25", "Buy", 75.0, 1000.0, 0.25],
        [datetime(2023, 12, 31).date(), "Gas", "EU", "Feb-25", "Sell", 30.0, -500.0, 0.18]
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
        worksheet.data_validation('E2:E100', direction_validation)

        # 添加说明
        worksheet.write('I1', 'Instructions:')
        worksheet.write('I2', '1. 评估日期: YYYY-MM-DD 格式')
        worksheet.write('I3', '2. 交割月格式: MMM-YY (如Jan-25)')
        worksheet.write('I4', '3. contract_vol可选: 如留空将自动计算')
        worksheet.write('I5', '4. Existing_MTM: 现有市值')

        # 设置日期格式
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})
        worksheet.set_column('A:A', 15, date_format)

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

        # 确保日期列是日期类型
        df['as_of_date'] = pd.to_datetime(df['as_of_date']).dt.date

    except FileNotFoundError:
        print(f"错误: 文件不存在 {file_path}")
        print("请先创建模板: create_pfe_template()")
        return pd.DataFrame()
    except Exception as e:
        print(f"读取文件错误: {e}")
        return pd.DataFrame()

    # 数据验证
    required_columns = ["as_of_date", "commodity", "destination", "deliver_month",
                        "direction", "contract_price", "Existing_MTM"]
    if not all(col in df.columns for col in required_columns):
        missing = set(required_columns) - set(df.columns)
        print(f"错误: 缺少必要列: {', '.join(missing)}")
        return df

    # 1. 转换交割月为日期并计算到期时间
    df['delivery_date'] = df['deliver_month'].apply(convert_deliver_month_to_date)
    df['time_to_exp'] = df.apply(
        lambda row: calculate_time_to_expiry(row['as_of_date'], row['delivery_date']),
        axis=1
    )

    # 2. 计算Risk_Curve - 修复DataFrame调用错误
    def get_risk_curve(row):
        # 筛选匹配的商品和目的地
        mask = (risk_curve_mapping['Commodity'] == row['commodity']) & \
               (risk_curve_mapping['Destination'] == row['destination'])
        filtered = risk_curve_mapping.loc[mask, 'Curve_Root']

        # 返回第一个匹配的曲线，如果没有则返回空字符串
        return filtered.values[0] if not filtered.empty else ""

    df["Risk_Curve"] = df.apply(get_risk_curve, axis=1)

    # 3. 自动填充缺失的波动率
    if "contract_vol" not in df.columns:
        df["contract_vol"] = None

    if df["contract_vol"].isnull().any():
        print("检测到缺失波动率，自动计算中...")

        def auto_fill_vol(row):
            if pd.isnull(row["contract_vol"]) and row["Risk_Curve"]:
                try:
                    # 使用风险曲线获取波动率
                    _, vol = get_vol(row["Risk_Curve"], row["deliver_month"], row["as_of_date"])
                    return vol
                except Exception as e:
                    print(f"获取波动率错误 (行{row.name}): {e}")
                    return None
            return row["contract_vol"]

        df["contract_vol"] = df.apply(auto_fill_vol, axis=1)

    # 4. 计算PFE值
    def calculate_pfe(row):
        try:
            # 检查必要字段
            if pd.isnull(row["contract_vol"]) or row["time_to_exp"] <= 0:
                return 0.0

            return pfe_calculator(
                row["direction"],
                float(row["contract_price"]),
                float(row["contract_vol"]),
                float(row["time_to_exp"])
            )
        except (ValueError, TypeError) as e:
            print(f"计算PFE错误 (行{row.name}): {e}")
            return None

    df["PFE_Value"] = df.apply(calculate_pfe, axis=1)

    # 5. 计算总敞口 (PFE + Existing_MTM)
    df["Total_Exposure"] = df["PFE_Value"] + df["Existing_MTM"]

    # 6. 保存结果到新文件
    result_path = file_path.replace(".xlsx", "_result.xlsx")
    try:
        with pd.ExcelWriter(result_path, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="PFE_Results")

            # 设置Excel格式
            workbook = writer.book
            worksheet = writer.sheets["PFE_Results"]

            # 设置数字格式
            num_format = workbook.add_format({"num_format": "#,##0.00"})
            date_format = workbook.add_format({"num_format": "yyyy-mm-dd"})

            # 设置列格式和宽度
            col_settings = [
                ("A", "as_of_date", 15, date_format),
                ("B", "commodity", 12),
                ("C", "destination", 15),
                ("D", "deliver_month", 15),
                ("E", "direction", 10),
                ("F", "contract_price", 15, num_format),
                ("G", "Existing_MTM", 15, num_format),
                ("H", "contract_vol", 15, num_format),
                ("I", "delivery_date", 15, date_format),
                ("J", "time_to_exp", 15, num_format),
                ("K", "Risk_Curve", 20),
                ("L", "PFE_Value", 15, num_format),
                ("M", "Total_Exposure", 15, num_format)
            ]

            for col_letter, col_name, width, *fmt in col_settings:
                col_idx = df.columns.get_loc(col_name)
                if fmt:
                    worksheet.set_column(col_idx, col_idx, width, fmt[0])
                else:
                    worksheet.set_column(col_idx, col_idx, width)

            # 添加条件格式突出显示总敞口
            red_format = workbook.add_format({"bg_color": "#FFC7CE", "font_color": "#9C0006"})
            green_format = workbook.add_format({"bg_color": "#C6EFCE", "font_color": "#006100"})

            # 应用条件格式到总敞口列
            last_row = len(df) + 1
            worksheet.conditional_format(
                f"M2:M{last_row}",
                {
                    "type": "cell",
                    "criteria": ">",
                    "value": 0,
                    "format": red_format
                }
            )
            worksheet.conditional_format(
                f"M2:M{last_row}",
                {
                    "type": "cell",
                    "criteria": "<",
                    "value": 0,
                    "format": green_format
                }
            )

            # 冻结首行
            worksheet.freeze_panes(1, 0)

            # 添加自动筛选
            worksheet.autofilter(0, 0, last_row, len(df.columns) - 1)

        print(f"计算结果已保存至: {result_path}")
    except Exception as e:
        print(f"保存结果文件错误: {e}")
        return df

    return df


# 使用示例
if __name__ == "__main__":
    # 创建模板 (如果不存在)
    template_path = "PFE_template.xlsx"
    if not os.path.exists(template_path):
        create_pfe_template(template_path)
        print("请填写模板文件后重新运行程序")
    else:
        # 计算PFE结果
        result_df = calculate_and_update_pfe(template_path)
        print("计算完成!")
        if not result_df.empty:
            print("\n结果预览:")
            print(result_df[["commodity", "deliver_month", "direction", "PFE_Value", "Existing_MTM",
                             "Total_Exposure"]].head())