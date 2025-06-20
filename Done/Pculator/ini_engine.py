import os
import math
import logging
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from typing import Optional, List

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
from xlsxwriter.utility import xl_col_to_name

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

        return df

    @staticmethod
    def write_results(df: pd.DataFrame, path: str) -> None:
        """
        Export DataFrame to Excel with formatting.
        """
        try:
            with pd.ExcelWriter(path, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='PFE_Results')
                wb, ws = writer.book, writer.sheets['PFE_Results']

                # Create formats
                fmt_num = wb.add_format({'num_format': '#,##0.00'})
                fmt_date = wb.add_format({'num_format': 'yyyy-mm-dd'})
                fmt_header = wb.add_format({'bold': True, 'bg_color': '#D9D9D9'})

                # Apply column formatting
                for col_idx, col_name in enumerate(df.columns):
                    # Set column width
                    width = max(df[col_name].astype(str).map(len).max(), len(col_name)) + 2
                    ws.set_column(col_idx, col_idx, width)

                    # Apply format based on column type
                    if 'date' in col_name.lower():
                        ws.set_column(col_idx, col_idx, width, fmt_date)
                    elif any(k in col_name.lower() for k in ['price', 'mtm', 'pfe', 'exposure', 'vol']):
                        ws.set_column(col_idx, col_idx, width, fmt_num)

                # Format header
                for col_idx, col_name in enumerate(df.columns):
                    ws.write(0, col_idx, col_name, fmt_header)

                # Apply conditional formatting to Total_Exposure
                try:
                    col_idx = df.columns.get_loc('Total_Exposure')
                    col_letter = xl_col_to_name(col_idx)
                    num_rows = len(df)

                    if num_rows > 0:
                        range_str = f'{col_letter}2:{col_letter}{num_rows + 1}'

                        # Positive exposure (red)
                        ws.conditional_format(range_str, {
                            'type': 'cell',
                            'criteria': '>',
                            'value': 0,
                            'format': wb.add_format({'bg_color': '#FFC7CE'})
                        })

                        # Non-positive exposure (green)
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