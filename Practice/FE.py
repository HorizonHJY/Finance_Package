from dateutil.relativedelta import relativedelta
import math
import pandas as pd
import os
from datetime import datetime


# 假设以下全局变量已在其他位置定义
# MONTH_CODE_MAP, curve_mapping, viya_vol, trading_code_to_month

def convert_deliver_month_to_date(month_str: str) -> datetime.date:
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


def calculate_time_to_expiry(as_of_date: datetime.date, delivery_date: datetime.date) -> float:
    """
    计算到期时间（年化）
    """
    if not isinstance(as_of_date, datetime.date) or not isinstance(delivery_date, datetime.date):
        return 0.0

    # 确保交割日期在评估日期之后
    if delivery_date <= as_of_date:
        return 0.0

    # 计算天数差并年化
    days_diff = (delivery_date - as_of_date).days
    return days_diff / 365.0


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

    # 2. 计算Risk_Curve
    def get_risk_curve(row):
        curves = risk_curve_mapping(row["commodity"], row["destination"])
        return curves[0] if curves else ""

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
                    _, vol = get_vol(row["Risk_Curve"])
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