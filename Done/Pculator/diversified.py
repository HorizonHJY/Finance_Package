import numpy as np
import pandas as pd


def calc_diversified_pfe(
        df: pd.DataFrame,
        R: np.ndarray,
        vol_col: str = "volatility",  # 改为波动率列名
        exposure_col: str = "exposure",  # 新增暴露值列
        z: float = 1.645,
) -> pd.DataFrame:
    """
    Calculates diversified PFE contribution using volatility and exposure.

    Parameters:
        df: DataFrame containing volatility and exposure values.
        R: Correlation matrix (must be symmetric positive semi-definite).
        vol_col: Column name for volatility (default: 'volatility').
        exposure_col: Column name for exposure/PFE (default: 'exposure').
        z: Quantile for confidence level (default: 1.645 for 95% confidence).

    Returns:
        DataFrame with columns:
            'percentage': Percentage risk contribution of each unit.
            'diversified_pfe': Absolute diversified PFE contribution.
    """
    # 获取波动率和暴露值
    σ = df[vol_col].to_numpy()  # 波动率向量
    s = df[exposure_col].to_numpy()  # 暴露值向量

    # 输入验证
    n = len(σ)
    assert R.shape == (n, n), "R must be n x n matrix"
    assert np.all(σ > 0), "Volatility must be positive"
    assert np.all(np.diag(R) == 1.0), "Correlation diagonal must be 1"
    assert np.all(R >= -1) and np.all(R <= 1), "Correlation out of [-1,1] range"

    # 创建对角波动率矩阵
    D = np.diag(σ)

    # 计算协方差矩阵
    cov_matrix = D @ R @ D

    # 计算组合波动率
    port_vol = np.sqrt(s.T @ cov_matrix @ s)

    # 计算边际风险贡献
    mrc = (cov_matrix @ s) / port_vol

    # 计算风险贡献
    risk_contrib = z * mrc * port_vol

    # 计算百分比贡献
    perc_contrib = risk_contrib / (z * port_vol)  # 标准化为百分比

    return pd.DataFrame(
        {
            "percentage": perc_contrib,
            "diversified_pfe": risk_contrib,
            "marginal_risk_contrib": mrc  # 可选：保留边际风险贡献
        },
        index=df.index,
    )


# 示例数据（包含波动率和暴露值）
df_sample = pd.DataFrame({
    'exposure': [100.0, 150.0, 200.0, 120.0],  # PFE/暴露值
    'volatility': [0.15, 0.22, 0.18, 0.12]  # 波动率
}, index=['T1', 'T2', 'T3', 'T4'])

R_sample = np.array([
    [1.0, 0.2, 0.1, -0.1],
    [0.2, 1.0, 0.3, 0.0],
    [0.1, 0.3, 1.0, 0.4],
    [-0.1, 0.0, 0.4, 1.0]
])

# 计算分散化PFE
df_result = calc_diversified_pfe(
    df_sample,
    R_sample,
    vol_col='volatility',
    exposure_col='exposure'
)

print("分散化PFE贡献:")
print(df_result[['percentage', 'diversified_pfe']])

# 验证结果
total_pfe = df_result['diversified_pfe'].sum()
total_exposure = df_sample['exposure'].sum()
print(f"\n总分散化PFE: {total_pfe:.2f}")
print(f"总暴露值: {total_exposure:.2f}")
print(f"分散化比率: {total_pfe / total_exposure:.2%}")