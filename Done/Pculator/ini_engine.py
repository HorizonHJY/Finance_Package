import os
import math
import logging
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta

import pandas as pd
import numpy as np
import holidays
import jv
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
    Engine to process Potential Future Exposure (PFE) calculations
    """
    def __init__(self, template_path: str = 'PFE_template.xlsx'):
        self.template_path = template_path
        # Load volatility data once
        self.vol_data = jv.download_data_db(querys.viya_vol, connection_type=prd_db)
        # Cache US holidays for current year
        current_year = datetime.today().year
        self.us_holidays = holidays.US(years=current_year)

    @staticmethod
    def get_prod_list() -> list[str]:
        """
        Return sorted list of available products (commodities) from curve mapping.
        """
        return sorted({row['commodity'] for _, row in CURVE_MAPPING_LIST.iterrows()})

    @staticmethod
    def convert_deliver_month_to_date(date_str: str) -> date | None:
        """
        Convert a deliver month string 'MMM-YY' to the last day of that month.
        """
        try:
            month_str, year_short = date_str.strip().split('-')
            first_day = datetime.strptime(f"{month_str}-{year_short}", "%b-%y")
            last_day = (first_day.replace(day=1) + relativedelta(months=1) - relativedelta(days=1)).date()
            return last_day
        except Exception:
            logger.warning(f"Invalid deliver_month format: '{date_str}', expected MMM-YY")
            return None

    @staticmethod
    def deliver_month_list(years: int = 5) -> list[str]:
        """
        Generate list of future deliver_month labels ('MMM-YY') up to given years.
        """
        start = datetime.today()
        end = start + relativedelta(years=years)
        months = pd.date_range(start=start, end=end, freq='M')
        return [d.strftime('%b-%y') for d in months]

    def get_aod_list(self, days: int = 31) -> list[str]:
        """
        Get list of recent workdays (excluding weekends and US holidays), formatted as 'YYYY-MM-DD'.
        """
        today = datetime.today().date()
        date_range = [today - timedelta(days=i) for i in range(days)]
        workdays = [d.strftime('%Y-%m-%d') for d in date_range if d.weekday() < 5 and d not in self.us_holidays]
        return workdays

    @staticmethod
    def risk_cr(commodity: str, origin: str) -> str:
        """
        Lookup curve root for given commodity and origin.
        """
        subset = CURVE_MAPPING_LIST.loc[
            (CURVE_MAPPING_LIST['commodity'] == commodity) &
            (CURVE_MAPPING_LIST['destination'] == origin),
            'Curve_Root'
        ]
        return subset.item()

    def get_date_list(self, risk_curve_root: str) -> list[date]:
        """
        Parse available dates for a given risk curve root from vol_data.
        """
        pattern = fr'^{risk_curve_root}_[A-Z][0-9]{{2}}$'
        df = self.vol_data
        mask = df['RISK_FACTOR'].str.contains(pattern, regex=True, na=False)
        if not mask.any():
            logger.warning(f"No risk factors found for root {risk_curve_root}")
            return []
        seen = set()
        dates = []
        code_to_month = {v: k for k, v in MONTH_CODE_MAP.items()}
        for factor in df.loc[mask, 'RISK_FACTOR']:
            if factor in seen:
                continue
            seen.add(factor)
            month_code = factor[-3:-2]
            year_short = factor[-2:]
            try:
                month_str = code_to_month[month_code]
                dt = datetime.strptime(f"{month_str}-{year_short}", "%b-%y").date().replace(day=1)
                dates.append(dt)
            except Exception as e:
                logger.debug(f"Skipping factor {factor}: {e}")
        dates.sort(reverse=True)
        return dates

    def match_curve(self, risk_curve_root: str, deliver_month: str) -> str | None:
        """
        For given curve root and deliver_month, find nearest factor date and return full RISK_FACTOR.
        """
        first_day = datetime.strptime(deliver_month, "%b-%y").date().replace(day=1)
        date_list = self.get_date_list(risk_curve_root)
        if not date_list:
            return None
        match = min(date_list, key=lambda d: abs((d - first_day).days))
        month_code = [k for k,v in MONTH_CODE_MAP.items() if v == match.strftime('%b')][0]
        year_short = str(match.year)[-2:]
        return f"{risk_curve_root}_{month_code}{year_short}"

    def get_vol(self, risk_curve: str, as_of_date: date) -> float | None:
        """
        Fetch volatility for specified risk_curve and as_of_date.
        """
        df = self.vol_data
        filt = (df['RISK_FACTOR'] == risk_curve) & (df['AS_OF_DATE'] == pd.to_datetime(as_of_date))
        sub = df.loc[filt, 'VOLATILITY']
        if sub.empty:
            logger.warning(f"No volatility for {risk_curve} on {as_of_date}")
            return None
        return float(sub.iloc[0] * math.sqrt(252))

    @staticmethod
    def calculate_time_to_expiry(as_of_date: date, delivery_date: date) -> float:
        days = (delivery_date - as_of_date).days
        return days / 365.0

    @staticmethod
    def pfe_calculator(
        direction: str,
        contract_price: float,
        contract_vol: float,
        time_to_exp: float
    ) -> float:
        buy_term = 1.645 * contract_vol * math.sqrt(time_to_exp) - 0.5 * contract_vol**2 * time_to_exp
        sell_term = -1.645 * contract_vol * math.sqrt(time_to_exp) - 0.5 * contract_vol**2 * time_to_exp
        if direction.lower() == 'buy':
            return contract_price * (-1 + math.exp(buy_term))
        else:
            return contract_price * (1 - math.exp(sell_term))

    def process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        required = ['as_of_date','product','origin','deliver_month','direction','contract_price','Existing_MTM']
        missing = set(required) - set(df.columns)
        if missing:
            logger.error(f"Missing columns: {missing}")
            return df
        df['as_of_date'] = pd.to_datetime(df['as_of_date']).dt.date
        df['delivery_date'] = df['deliver_month'].apply(self.convert_deliver_month_to_date)
        df['time_to_exp'] = df.apply(
            lambda r: self.calculate_time_to_expiry(r['as_of_date'], r['delivery_date']) if r['delivery_date'] else np.nan,
            axis=1
        )
        df['Risk_Curve'] = df.apply(lambda r: self.risk_cr(r['product'], r['origin']), axis=1)
        df['contract_vol'] = df.apply(
            lambda r: self.get_vol(
                self.match_curve(r['Risk_Curve'], r['deliver_month']),
                r['as_of_date']
            ) if pd.notnull(r['time_to_exp']) and r['time_to_exp']>0 else None,
            axis=1
        )
        df['PFE_Value'] = df.apply(
            lambda r: self.pfe_calculator(
                r['direction'], r['contract_price'], r['contract_vol'], r['time_to_exp']
            ) if r['contract_vol'] and r['time_to_exp']>0 else 0.0,
            axis=1
        )
        df['PFE_Output'] = df['PFE_Value'] * df.get('position', 1)
        df['Total_Exposure'] = df['PFE_Output'] + df['Existing_MTM']
        return df

    @staticmethod
    def write_results(df: pd.DataFrame, file_path: str) -> None:
        with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='PFE_Results')
            wb = writer.book
            ws = writer.sheets['PFE_Results']
            num_fmt = wb.add_format({'num_format': '#,##0.00'})
            date_fmt = wb.add_format({'num_format': 'yyyy-mm-dd'})
            for idx, col in enumerate(df.columns):
                width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                fmt = date_fmt if 'date' in col.lower() else num_fmt
                ws.set_column(idx, idx, width, fmt)
            last_row = len(df) + 1
            ws.conditional_format(
                f'M2:M{last_row}', {'type': 'cell', 'criteria': '>', 'value': 0, 'format': wb.add_format({'bg_color':'#FFC7CE','font_color':'#9C0006'})}
            )
            ws.conditional_format(
                f'M2:M{last_row}', {'type': 'cell', 'criteria': '<=', 'value': 0, 'format': wb.add_format({'bg_color':'#C6EFCE','font_color':'#006100'})}
            )

    def create_template(self, file_path: str) -> None:
        """
        Create an Excel template for PFE input with data validation lists.
        """
        products = self.get_prod_list()
        origins = sorted({row['destination'] for _, row in CURVE_MAPPING_LIST.iterrows()})
        deliver_months = self.deliver_month_list()
        aod_list = self.get_aod_list()
        directions = ['Buy', 'Sell']
        df = pd.DataFrame([{
            'as_of_date': datetime.today().strftime('%Y-%m-%d'),
            'product': products[0] if products else '',
            'origin': origins[0] if origins else '',
            'deliver_month': deliver_months[0],
            'direction': directions[0],
            'contract_price': 0.0,
            'Existing_MTM': 0.0,
            'position': 1
        }])
        with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='PFE Data Input')
            wb = writer.book
            ws = writer.sheets['PFE Data Input']
            # Create hidden sheet for lists
            list_ws = wb.add_worksheet('lists')
            lists = [products, origins, deliver_months, aod_list, directions]
            names = ['Products', 'Origins', 'DeliverMonths', 'AODs', 'Directions']
            for col, lst in enumerate(lists):
                for row, val in enumerate(lst):
                    list_ws.write(row, col, val)
                wb.define_name(names[col], f"=lists!${chr(65+col)}$1:${chr(65+col)}${len(lst)}")
            list_ws.hide()
            # Apply data validation
            header = {col: idx for idx, col in enumerate(df.columns)}
            max_row = 1000
            validations = {
                'as_of_date': 'AODs',
                'product': 'Products',
                'origin': 'Origins',
                'deliver_month': 'DeliverMonths',
                'direction': 'Directions'
            }
            for col, name in validations.items():
                idx = header[col]
                ws.data_validation(1, idx, max_row, idx, {
                    'validate': 'list',
                    'source': f"={name}"
                })
        logger.info(f"Template created at {file_path}")

    def run(self) -> None:
        if not os.path.exists(self.template_path):
            logger.info(f"Template not found, creating {self.template_path}...")
            self.create_template(self.template_path)
            logger.info("Please fill the template and rerun.")
            return
        df_input = pd.read_excel(self.template_path, sheet_name='PFE Data Input')
        df_out = self.process_dataframe(df_input)
        ts = datetime.now().strftime('%Y_%m_%d_%H%M%S')
        out_file = f"PFE_result_{ts}.xlsx"
        self.write_results(df_out, out
