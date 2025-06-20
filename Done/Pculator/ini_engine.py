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
    def convert_deliver_month_to_date(date_str: str) -> date | None:
        """
        Convert a deliver month string 'MMM-YY' to the last day of that month.
        """
        try:
            month_str, year_short = date_str.strip().split('-')
            first_day = datetime.strptime(f"{month_str}-{year_short}", "%b-%y")
            # go to first day of next month, then subtract one day
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

    @staticmethod
    def get_aod_list(days: int = 31) -> list[date]:
        """
        Get list of recent workdays (excluding weekends and US holidays).
        """
        today = datetime.today().date()
        date_range = [today - timedelta(days=i) for i in range(days)]
        us_holidays = holidays.US(years=today.year)
        workdays = [d for d in date_range if d.weekday() < 5 and d not in us_holidays]
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
        # find nearest
        match = min(date_list, key=lambda d: abs((d - first_day).days))
        # build risk factor code
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
        # convert daily vol to annualized (sqrt(252))
        return float(sub.iloc[0] * math.sqrt(252))

    @staticmethod
    def calculate_time_to_expiry(as_of_date: date, delivery_date: date) -> float:
        """
        Compute year fraction between as_of_date and delivery_date.
        """
        days = (delivery_date - as_of_date).days
        return days / 365.0

    @staticmethod
    def pfe_calculator(
        direction: str,
        contract_price: float,
        contract_vol: float,
        time_to_exp: float
    ) -> float:
        """
        Compute PFE adjustment based on direction, price, vol, and time.
        """
        buy_term = 1.645 * contract_vol * math.sqrt(time_to_exp) - 0.5 * contract_vol**2 * time_to_exp
        sell_term = -1.645 * contract_vol * math.sqrt(time_to_exp) - 0.5 * contract_vol**2 * time_to_exp
        if direction.lower() == 'buy':
            return contract_price * (-1 + math.exp(buy_term))
        else:
            return contract_price * (1 - math.exp(sell_term))

    def process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply full PFE pipeline: convert dates, match curves, fetch vols, compute PFE and exposures.
        """
        # ensure required cols
        required = ['as_of_date','product','origin','deliver_month','direction','contract_price','Existing_MTM']
        missing = set(required) - set(df.columns)
        if missing:
            logger.error(f"Missing columns: {missing}")
            return df
        # convert types
        df['as_of_date'] = pd.to_datetime(df['as_of_date']).dt.date
        df['delivery_date'] = df['deliver_month'].apply(self.convert_deliver_month_to_date)
        df['time_to_exp'] = df.apply(
            lambda r: self.calculate_time_to_expiry(r['as_of_date'], r['delivery_date'])
            if r['delivery_date'] else np.nan,
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
        df['PFE_Output'] = df['PFE_Value'] * df['position']
        df['Total_Exposure'] = df['PFE_Output'] + df['Existing_MTM']
        return df

    @staticmethod
    def write_results(df: pd.DataFrame, file_path: str) -> None:
        """
        Write output DataFrame to Excel with formatting.
        """
        with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='PFE_Results')
            wb = writer.book
            ws = writer.sheets['PFE_Results']
            # add formats
            num_fmt = wb.add_format({'num_format': '#,##0.00'})
            date_fmt = wb.add_format({'num_format': 'yyyy-mm-dd'})
            # auto column widths and formats
            for idx, col in enumerate(df.columns):
                width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                fmt = date_fmt if 'date' in col.lower() else num_fmt
                ws.set_column(idx, idx, width, fmt)
            # conditional formatting for Total_Exposure
            last_row = len(df) + 1
            ws.conditional_format(
                f'M2:M{last_row}',
                {'type': 'cell', 'criteria': '>', 'value': 0, 'format': wb.add_format({'bg_color':'#FFC7CE','font_color':'#9C0006'})}
            )
            ws.conditional_format(
                f'M2:M{last_row}',
                {'type': 'cell', 'criteria': '<=', 'value': 0, 'format': wb.add_format({'bg_color':'#C6EFCE','font_color':'#006100'})}
            )

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
        self.write_results(df_out, out_file)
        logger.info(f"PFE results saved to {out_file}")

    @staticmethod
    def create_template(file_path: str) -> None:
        """
        Create input template with sample data and validation.
        """
        # Implementation omitted for brevity; reuse existing create_pfe_template logic
        from Sandbox.horizon.PFE_Calculator.main import create_pfe_template
        create_pfe_template(file_path)

if __name__ == '__main__':
    engine = PFEEngine()
    engine.run()
