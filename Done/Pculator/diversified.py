import numpy as np
import pandas as pd

def calc_diversified_pfe(
    df: pd.DataFrame,
    R: np.ndarray,
    unit_col: str = "unit_pfe",
    z: float = 1.645,
) -> pd.DataFrame:
    """
    Calculates diversified PFE contribution for each unit in a portfolio.

    Parameters:
        df: DataFrame containing unit PFE values.
        R: Correlation matrix (must be symmetric positive semi-definite).
        unit_col: Column name for unit PFE (default: 'unit_pfe').
        z: Quantile for confidence level (default: 1.645 for 95% confidence).

    Returns:
        DataFrame with columns:
            'percentage': Percentage risk contribution of each unit.
            'diversified_pfe': Absolute diversified PFE contribution.
    """
    s = df[unit_col].to_numpy()

    # Input validation
    assert len(s) == R.shape[0], "R dimension must match number of units"
    assert R.shape[0] == R.shape[1], "R must be a square matrix"
    assert np.all(np.isfinite(s)), "s contains NaN or Inf values"

    # Calculate portfolio statistics
    Rs = R @ s  # R s vector
    var_port = s.dot(Rs)  # Portfolio variance: sᵀ R s

    # Handle near-zero variance
    if var_port < 1e-10:
        contrib = np.zeros_like(s)
        perc = np.zeros_like(s)
    else:
        std_port = np.sqrt(var_port)  # Portfolio standard deviation
        # Marginal risk contribution: MRC_i = s_i * (R s)_i / σ_p
        mrc = (s * Rs) / std_port
        contrib = z * mrc  # Diversified PFE contribution
        perc = mrc / std_port  # Percentage contribution = MRC_i / σ_p

    return pd.DataFrame(
        {"percentage": perc, "diversified_pfe": contrib},
        index=df.index,
    )

# Sample data
df_sample = pd.DataFrame({
    'unit_pfe': [100.0, 150.0, 200.0, 120.0]
}, index=['T1', 'T2', 'T3', 'T4'])

R_sample = np.array([
    [ 1.0,  0.2,  0.1, -0.1],
    [ 0.2,  1.0,  0.3,  0.0],
    [ 0.1,  0.3,  1.0,  0.4],
    [-0.1,  0.0,  0.4,  1.0]
])

# Compute results
df_result = calc_diversified_pfe(df_sample, R_sample, unit_col='unit_pfe', z=1.645)

print(df_result)