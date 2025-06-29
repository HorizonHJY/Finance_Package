
import holidays
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import jarvis as jv

prd_db = jv.ConnectionType.PROD

def get_ini_date(as_of_date: datetime, his_len: int):
    us_holidays = holidays.US()
    end_date = as_of_date
    start_date = end_date - timedelta(days=300)
    all_days = pd.date_range(start=start_date, end=end_date)
    biz_days = [d for d in all_days if d.weekday() < 5 and d not in us_holidays]
    target_date = biz_days[-(his_len + 2)]
    return target_date.date()

def compute_vol_ewma(price_df: pd.DataFrame, lambda_: float = 0.94) -> pd.DataFrame:
    log_returns = np.log(price_df / price_df.shift(1)).dropna()
    n = len(log_returns)
    weights = np.array([lambda_ ** (n - 1 - i) for i in range(n)], dtype=float)
    weights /= weights.sum()
    weighted_returns = log_returns * np.sqrt(weights)[:, np.newaxis]
    cov_matrix = weighted_returns.T @ weighted_returns
    return cov_matrix

def get_cov_matrix(risk_curve_list: list, as_of_d, history_length: int = 121) -> pd.DataFrame:
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

    cov_matrix_df = compute_vol_ewma(price_df)
    return cov_matrix_df

def cov_to_corr(cov_matrix):
    std_dev = np.sqrt(np.diag(cov_matrix))
    denom = np.outer(std_dev, std_dev)
    corr_matrix = cov_matrix / denom
    return corr_matrix

def calc_diversified_pfe_use_corr(
        df: pd.DataFrame,
        R: np.ndarray,
        unit_col: str = 'unit_pfe',
        z: float = 1.645
    ) -> pd.DataFrame:

    s = df[unit_col].to_numpy()
    port_variance = s.T @ R @ s
    total_pfe = z * np.sqrt(port_variance)

    marginal_contrib = R @ s / np.sqrt(port_variance)
    risk_contrib = s * marginal_contrib
    risk_contrib *= total_pfe / risk_contrib.sum()

    df['diversified_pfe'] = risk_contrib
    df['percentage'] = risk_contrib / total_pfe
    return df

# Example execution
if __name__ == "__main__":
    test_date = datetime(year=2025, month=6, day=12)
    curve_list = ['DE_LWRRH_CNM_FOB_N25', 'EURONEXT_ECO_Q25', 'EU_DTCHML_CNDD05_FOB_U25']
    test_list = [0.12, 0.14, 0.06]
    pd_test = pd.DataFrame({'unit_pfe': test_list})

    result = get_cov_matrix(curve_list, test_date, history_length=121)
    corr = cov_to_corr(result)

    di_ver_pfe_cor_base = calc_diversified_pfe_use_corr(pd_test, corr, unit_col='unit_pfe')
    print(di_ver_pfe_cor_base)
