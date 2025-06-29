import os
import math
import logging
import numpy as np
import pandas as pd
import holidays
import jv
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from typing import Optional, List
from xlsxwriter.utility import xl_col_to_name
from Sandbox.horizon.PFE_Calculator.models.common import (
    CURVE_MAPPING_LIST,
    MONTH_CODE_MAP,
    querys,
    prd_db,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PFEEngine:
    """
    Engine to process Potential Future Exposure (PFE) calculations and template management.
    """

    def __init__(self, template_path: str = 'PFE_template.xlsx'):
        self.template_path = template_path
        # Preload volatility data
        self.vol_data = jv.download_data_db(querys.viya_vol, connection_type=prd_db)
        # Initialize empty holidays - will be dynamically updated
        self.us_holidays = holidays.US(years=[])

    @staticmethod
    def get_prod_list() -> list[str]:
        """
        Return sorted unique list of products (commodities).
        """
        return sorted({row['commodity'] for _, row in CURVE_MAPPING_LIST.iterrows()})

    @staticmethod
    def convert_deliver_month_to_date(date_str: str) -> date | None:
        """
        Convert 'MMM-YY' string to last day of that month.
        """
        try:
            month_str, year_short = date_str.split('-')
            # Handle two-digit year conversion
            full_year = 2000 + int(year_short) if int(year_short) < 100 else int(year_short)
            first = datetime.strptime(f"{month_str}-{full_year}", "%b-%Y")
            last = (first.replace(day=1) + relativedelta(months=1) - relativedelta(days=1)).date()
            return last
        except Exception as e:
            logger.warning(f"Invalid deliver_month '{date_str}': {str(e)}")
            return None

    @staticmethod
    def deliver_month_list(years: int = 5) -> list[str]:
        """
        Generate future 'MMM-YY' labels for next N years.
        """
        today = datetime.today().replace(day=1)
        end = today + relativedelta(years=years, day=31)
        months = pd.date_range(start=today, end=end, freq='M')
        return [d.strftime('%b-%y') for d in months]

    def get_aod_list(self, days: int = 31) -> list[str]:
        """
        Recent workdays (YYYY-MM-DD), excluding weekends and US holidays.
        """
        today = datetime.today().date()
        start_date = today - timedelta(days=days)

        # Update holidays to cover the required date range
        years = range(start_date.year, today.year + 1)
        if years:
            self.us_holidays = holidays.US(years=years)

        workdays = []
        current = today
        while len(workdays) < days:
            current -= timedelta(days=1)
            if current.weekday() < 5 and current not in self.us_holidays:
                workdays.append(current.strftime('%Y-%m-%d'))
        return workdays

    @staticmethod
    def risk_cr(commodity: str, origin: str) -> str:
        """
        Lookup curve root by commodity and destination.
        """
        df = CURVE_MAPPING_LIST
        sel = df[(df['commodity'] == commodity) & (df['destination'] == origin)]['Curve_Root']
        if sel.empty:
            logger.error(f"No curve root found for commodity '{commodity}' and origin '{origin}'")
            return "UNKNOWN"
        return sel.item()

    def get_date_list(self, risk_curve_root: str) -> list[date]:
        """
        Available factor dates (first of month) for a given curve root.
        """
        pattern = fr'^{risk_curve_root}_[A-Z][0-9]{{2}}$'
        mask = self.vol_data['RISK_FACTOR'].str.contains(pattern, regex=True, na=False)
        if not mask.any():
            logger.warning(f"No volatility data found for curve root: {risk_curve_root}")
            return []
        code_to_mon = {v: k for k, v in MONTH_CODE_MAP.items()}
        dates = set()
        for factor in self.vol_data.loc[mask, 'RISK_FACTOR']:
            code = factor.split('_')[-1]
            mon_code, yr = code[0], code[1:]
            mon = code_to_mon.get(mon_code)
            if mon:
                try:
                    dt = datetime.strptime(f"{mon}-{yr}", "%b-%y").date().replace(day=1)
                    dates.add(dt)
                except ValueError:
                    logger.warning(f"Invalid date code in factor: {factor}")
        return sorted(dates, reverse=True)

    def match_curve(self, risk_curve_root: str, deliver_month: str) -> str | None:
        """
        Find nearest RISK_FACTOR code for given deliver_month.
        """
        try:
            target = datetime.strptime(deliver_month, "%b-%y").date().replace(day=1)
        except ValueError:
            logger.error(f"Invalid deliver_month format: {deliver_month}")
            return None

        dates = self.get_date_list(risk_curve_root)
        if not dates:
            logger.warning(f"No available dates for curve root: {risk_curve_root}")
            return None

        # Find the nearest date
        nearest = min(dates, key=lambda d: abs((d - target).days))
        mon_code = next((k for k, v in MONTH_CODE_MAP.items() if v == nearest.strftime('%b')), None)
        if not mon_code:
            logger.error(f"Month code not found for date: {nearest}")
            return None

        yr = str(nearest.year)[-2:]
        return f"{risk_curve_root}_{mon_code}{yr}"

    def get_vol(self, risk_curve: str, as_of: date) -> float | None:
        """
        Fetch annualized volatility (sqrt(252)) from vol_data.
        """
        if not risk_curve:
            return None

        # Try to get volatility from the exact date
        sel = self.vol_data[
            (self.vol_data['RISK_FACTOR'] == risk_curve) &
            (self.vol_data['AS_OF_DATE'] == pd.to_datetime(as_of))
            ]

        # If not found, try recent dates
        if sel.empty:
            for days_back in [1, 2, 3, 7]:
                target_date = as_of - timedelta(days=days_back)
                sel = self.vol_data[
                    (self.vol_data['RISK_FACTOR'] == risk_curve) &
                    (self.vol_data['AS_OF_DATE'] == pd.to_datetime(target_date))
                    ]
                if not sel.empty:
                    break

        if sel.empty:
            logger.warning(f"No volatility found for {risk_curve} as of {as_of} (and recent days)")
            return None

        try:
            val = sel['VOLATILITY'].iloc[0]
            return float(val * math.sqrt(252))  # Annualize daily volatility
        except Exception as e:
            logger.error(f"Error processing volatility for {risk_curve}: {str(e)}")
            return None

    @staticmethod
    def calculate_time_to_expiry(as_of: date, delivery: date) -> float:
        """
        Year fraction between two dates.
        """
        if not delivery or not as_of:
            return 0.0
        days = (delivery - as_of).days
        return days / 365.0 if days > 0 else 0.0

    @staticmethod
    def pfe_calculator(direction: str, price: float, vol: float, t: float) -> float:
        """
        PFE adjustment formula for Buy/Sell.
        """
        # Validate inputs
        if price <= 0 or vol <= 0 or t <= 0:
            return 0.0

        # Ensure valid direction
        direction = direction.lower()
        if direction not in ['buy', 'sell']:
            logger.warning(f"Invalid direction '{direction}'. Using 'buy' as default.")
            direction = 'buy'

        # Calculate factors
        sqrt_t = math.sqrt(t)
        vol_sq_t = vol ** 2 * t
        up = 1.645 * vol * sqrt_t - 0.5 * vol_sq_t
        down = -1.645 * vol * sqrt_t - 0.5 * vol_sq_t

        # Return PFE based on direction
        return price * (-1 + math.exp(up)) if direction == 'buy' else price * (1 - math.exp(down))

    @staticmethod
    def cov_to_corr(cov_matrix: np.ndarray) -> np.ndarray:
        """Convert covariance matrix to correlation matrix"""
        std_dev = np.sqrt(np.diag(cov_matrix))
        denom = np.outer(std_dev, std_dev)
        corr_matrix = cov_matrix / denom
        return corr_matrix

    def get_cov_matrix(self, risk_curve_list: list, as_of_d: date, history_length: int = 121) -> np.ndarray:
        """Compute covariance matrix for risk curves"""

        # Get initial date
        def get_ini_date(as_of_date: date, his_len: int) -> date:
            us_holidays = holidays.US()
            end_date = as_of_date
            start_date = end_date - timedelta(days=300)
            all_days = pd.date_range(start=start_date, end=end_date)
            biz_days = [d for d in all_days if d.weekday() < 5 and d not in us_holidays]
            target_date = biz_days[-(his_len + 2)]
            return target_date.date()

        # Compute EWMA volatility
        def compute_vol_ewma(price_df: pd.DataFrame, lambda_: float = 0.94) -> np.ndarray:
            log_returns = np.log(price_df / price_df.shift(1)).dropna()
            n = len(log_returns)
            weights = np.array([lambda_ ** (n - 1 - i) for i in range(n)], dtype=float)
            weights /= weights.sum()
            weighted_returns = log_returns * np.sqrt(weights)[:, np.newaxis]
            cov_matrix = weighted_returns.T @ weighted_returns
            return cov_matrix.values if isinstance(cov_matrix, pd.DataFrame) else cov_matrix

        cursor_download, con_download = jv.get_cursor_con(prd_db)
        first_pricing_date = get_ini_date(as_of_d, history_length)
        query_price_curve = "', '".join(risk_curve_list)
        query_price_curve = jv.convert_in_to_or(f"SHORT_PRICE_CURVE in ('{query_price_curve}')")

        query_prices = f"""
            SELECT PRICING_DATE, SHORT_PRICE_CURVE, CLOSE_PRICE 
            FROM {jv.DataTable.PRICE.value}
            WHERE PRICING_DATE <= date'{as_of_d.strftime('%Y-%m-%d')}'
              AND PRICING_DATE >= date'{first_pricing_date.strftime('%Y-%m-%d')}'
              AND ({query_price_curve})
        """

        price_db = jv.download_data_db(query_prices, cursor_download)
        price_df = jv.format_price_by_col(
            price_db,
            pricing_date_col="PRICING_DATE",
            curve_name="SHORT_PRICE_CURVE",
            close_price="CLOSE_PRICE"
        )
        return compute_vol_ewma(price_df)

    def process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Full PFE pipeline: date conversion, curve matching, vol fetch, PFE & exposure.
        """
        req = ['as_of_date', 'product', 'origin', 'deliver_month', 'direction', 'contract_price', 'Existing_MTM']
        if missing := set(req) - set(df.columns):
            logger.error(f"Missing required columns: {missing}")
            return df

        # Data validation
        if df['contract_price'].lt(0).any():
            logger.warning("Negative contract prices found. Check data validity.")

        # Ensure position column exists and validate
        if 'position' not in df.columns:
            df['position'] = 1
        elif df['position'].eq(0).any():
            logger.warning("Zero positions found. May affect exposure calculations.")

        # Convert dates
        df['as_of_date'] = pd.to_datetime(df['as_of_date']).dt.date
        df['delivery_date'] = df['deliver_month'].apply(self.convert_deliver_month_to_date)

        # Calculate time to expiry
        df['time_to_exp'] = df.apply(
            lambda r: self.calculate_time_to_expiry(r['as_of_date'], r['delivery_date']),
            axis=1
        )

        # Get risk curve
        df['Risk_Curve'] = df.apply(
            lambda r: self.risk_cr(r['product'], r['origin']),
            axis=1
        )

        # Match curve and get volatility
        df['contract_vol'] = df.apply(
            lambda r: self.get_vol(
                self.match_curve(r['Risk_Curve'], r['deliver_month']),
                r['as_of_date']
            ) if r['time_to_exp'] > 0 else None,
            axis=1
        )

        # Calculate PFE value
        df['PFE_Value'] = df.apply(
            lambda r: self.pfe_calculator(
                r['direction'],
                r['contract_price'],
                r['contract_vol'] or 0.0,
                r['time_to_exp']
            ) if r['contract_vol'] and r['time_to_exp'] > 0 else 0.0,
            axis=1
        )

        # Calculate outputs
        df['PFE_Output'] = df['PFE_Value'] * df['position']
        df['Total_Exposure'] = df['PFE_Output'] + df['Existing_MTM']

        # ===== 优化后的多样化PFE计算 =====
        # 初始化新列
        df['diversified_pfe'] = 0.0
        df['percentage'] = 0.0

        # 只处理有有效PFE的合约
        valid_mask = df['PFE_Output'] != 0
        valid_df = df[valid_mask]

        if not valid_df.empty:
            # 获取所有有效合约的风险曲线（每个都是唯一的）
            unique_curves = valid_df['Risk_Curve'].tolist()
            as_of_date = valid_df['as_of_date'].iloc[0]

            # 计算相关系数矩阵
            try:
                cov_matrix = self.get_cov_matrix(unique_curves, as_of_date)
                corr_matrix = self.cov_to_corr(cov_matrix)
            except Exception as e:
                logger.error(f"计算相关系数矩阵失败: {str(e)}")
                # 使用单位矩阵作为回退
                corr_matrix = np.eye(len(unique_curves))

            # 直接使用每个合约的PFE_Output作为向量s
            s = valid_df['PFE_Output'].values

            # 计算组合方差
            port_variance = s.T @ corr_matrix @ s

            # 检查方差非负
            if port_variance < 0:
                logger.warning("负的资产组合方差，使用未分散PFE")
                total_pfe = np.sum(np.abs(s)) * 1.645
            else:
                total_pfe = 1.645 * np.sqrt(port_variance)  # z = 1.645 (95% confidence)

            # 计算风险贡献
            if port_variance > 0:
                # 计算边际贡献
                marginal_contrib = corr_matrix @ s / np.sqrt(port_variance)
                # 计算每个合约的风险贡献
                risk_contrib = s * marginal_contrib
            else:
                # 如果方差为0，则直接使用原始PFE值
                risk_contrib = s

            # 归一化风险贡献，使其总和等于总PFE
            if (contrib_sum := risk_contrib.sum()) != 0:
                risk_contrib *= total_pfe / contrib_sum

            # 直接赋值给多样化PFE列
            df.loc[valid_mask, 'diversified_pfe'] = risk_contrib

            # 计算百分比
            if total_pfe != 0:
                df.loc[valid_mask, 'percentage'] = risk_contrib / total_pfe

        return df

    def write_results(self, df: pd.DataFrame, path: str) -> None:
        """
        Export DataFrame to Excel with clean formatting and summary row.
        """
        try:
            # 创建汇总行
            summary_data = {
                'as_of_date': 'Total',
                'product': '',
                'origin': '',
                'deliver_month': '',
                'direction': '',
                'contract_price': '',
                'Existing_MTM': df['Existing_MTM'].sum(),
                'position': df['position'].sum(),
                'delivery_date': '',
                'time_to_exp': '',
                'Risk_Curve': '',
                'contract_vol': '',
                'PFE_Value': df['PFE_Value'].sum(),
                'PFE_Output': df['PFE_Output'].sum(),
                'diversified_pfe': df['diversified_pfe'].sum(),
                'percentage': df['percentage'].sum(),
                'Total_Exposure': df['Total_Exposure'].sum()
            }

            # 确保所有列都存在
            for col in df.columns:
                if col not in summary_data:
                    summary_data[col] = ''

            # 创建汇总行并添加到DataFrame
            summary_row = pd.Series(summary_data)
            result_df = pd.concat([df, pd.DataFrame([summary_row])], ignore_index=True)

            with pd.ExcelWriter(path, engine='xlsxwriter') as writer:
                result_df.to_excel(writer, index=False, sheet_name='PFE_Results')
                wb, ws = writer.book, writer.sheets['PFE_Results']

                # 创建基本格式
                fmt_header = wb.add_format({'bold': True})
                fmt_summary = wb.add_format({'bold': True})
                fmt_num = wb.add_format({'num_format': '#,##0.00'})
                fmt_date = wb.add_format({'num_format': 'yyyy-mm-dd'})

                # 应用列格式
                for col_idx, col_name in enumerate(result_df.columns):
                    # 设置列宽
                    width = max(result_df[col_name].astype(str).map(len).max(), len(col_name)) + 2
                    ws.set_column(col_idx, col_idx, width)

                    # 根据列类型应用格式
                    if 'date' in col_name.lower():
                        ws.set_column(col_idx, col_idx, width, fmt_date)
                    elif any(k in col_name.lower() for k in ['price', 'mtm', 'pfe', 'exposure', 'vol', 'percentage']):
                        ws.set_column(col_idx, col_idx, width, fmt_num)

                # 格式化标题行
                for col_idx, col_name in enumerate(result_df.columns):
                    ws.write(0, col_idx, col_name, fmt_header)

                # 格式化汇总行（最后一行）
                last_row = len(result_df) - 1
                for col_idx in range(len(result_df.columns)):
                    ws.write(last_row, col_idx, result_df.iloc[last_row, col_idx], fmt_summary)

                # 应用条件格式到Total_Exposure（不包括汇总行）
                try:
                    col_idx = result_df.columns.get_loc('Total_Exposure')
                    col_letter = xl_col_to_name(col_idx)
                    num_rows = len(result_df) - 1  # 排除汇总行

                    if num_rows > 0:
                        range_str = f'{col_letter}2:{col_letter}{num_rows}'

                        # 正敞口（红色）
                        ws.conditional_format(range_str, {
                            'type': 'cell',
                            'criteria': '>',
                            'value': 0,
                            'format': wb.add_format({'bg_color': '#FFC7CE'})
                        })

                        # 非正敞口（绿色）
                        ws.conditional_format(range_str, {
                            'type': 'cell',
                            'criteria': '<=',
                            'value': 0,
                            'format': wb.add_format({'bg_color': '#C6EFCE'})
                        })
                except KeyError:
                    logger.error("Column 'Total_Exposure' not found. Skipping conditional formatting.")

            logger.info(f"Excel file saved successfully: {path}")
        except Exception as e:
            logger.error(f"Failed to write results to Excel: {str(e)}")
            raise

    def create_template(self, path: str) -> None:
        """
        Generate PFE_template.xlsx with data validation lists.
        """
        try:
            products = self.get_prod_list()
            origins = sorted({row['destination'] for _, row in CURVE_MAPPING_LIST.iterrows()})
            months = self.deliver_month_list()
            aods = self.get_aod_list()
            dirs = ['Buy', 'Sell']

            # Create sample dataframe
            sample = pd.DataFrame([{
                'as_of_date': datetime.today().strftime('%Y-%m-%d'),
                'product': products[0],
                'origin': origins[0],
                'deliver_month': months[0],
                'direction': dirs[0],
                'contract_price': 0.0,
                'Existing_MTM': 0.0,
                'position': 1
            }])

            # Create Excel file
            with pd.ExcelWriter(path, engine='xlsxwriter') as writer:
                sample.to_excel(writer, index=False, sheet_name='PFE Data Input')
                wb, ws = writer.book, writer.sheets['PFE Data Input']

                # Create hidden sheet for validation lists
                list_ws = wb.add_worksheet('lists')
                list_ws.visible = False  # Properly hide the sheet

                # Write validation lists
                arrays = [
                    ('Products', products),
                    ('Origins', origins),
                    ('Months', months),
                    ('AODs', aods),
                    ('Directions', dirs)
                ]

                for idx, (name, arr) in enumerate(arrays):
                    list_ws.write(0, idx, name)  # Header
                    for r, val in enumerate(arr, start=1):
                        list_ws.write(r, idx, val)
                    wb.define_name(name, f"=lists!${chr(65 + idx)}$2:${chr(65 + idx)}${len(arr) + 1}")

                # Apply data validation
                col_mapping = {
                    'as_of_date': 'AODs',
                    'product': 'Products',
                    'origin': 'Origins',
                    'deliver_month': 'Months',
                    'direction': 'Directions'
                }

                for col_name, validation_name in col_mapping.items():
                    col_idx = sample.columns.get_loc(col_name)
                    dv_range = f"={validation_name}"
                    ws.data_validation(
                        1, col_idx, 1048576, col_idx,  # Apply to entire column
                        {'validate': 'list', 'source': dv_range}
                    )

                # Set column widths
                for idx, col_name in enumerate(sample.columns):
                    width = max(len(col_name), 10) + 2
                    ws.set_column(idx, idx, width)

            logger.info(f"Template generated successfully at {path}")
        except Exception as e:
            logger.error(f"Failed to create template: {str(e)}")
            raise

    def run(self) -> None:
        try:
            if not os.path.exists(self.template_path):
                logger.info(f"Template not found. Creating {self.template_path}...")
                self.create_template(self.template_path)
                logger.info("Please fill the template and rerun the program.")
                return

            logger.info(f"Loading template: {self.template_path}")
            df = pd.read_excel(self.template_path, sheet_name='PFE Data Input')

            if df.empty:
                logger.warning("Template is empty. Please fill in the data.")
                return

            logger.info("Processing data...")
            out = self.process_dataframe(df)

            # Generate output filename
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            fname = f"PFE_result_{stamp}.xlsx"

            logger.info(f"Saving results to {fname}")
            self.write_results(out, fname)
            logger.info(f"Processing complete. Results saved to {fname}")
        except Exception as e:
            logger.error(f"An error occurred during processing: {str(e)}")
            logger.exception("Stack trace:")