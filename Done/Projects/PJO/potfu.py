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
