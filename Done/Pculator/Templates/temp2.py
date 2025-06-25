import numpy as np


def calc_diversified_vol(
        volatility_list: list[float],
        cov_matrix: np.ndarray,
) -> np.ndarray:
    """
    计算每个资产对组合波动率的贡献（diversified vol list）

    参数:
        volatility_list: 各资产的波动率列表 [σ1, σ2, ..., σn]
        cov_matrix: 协方差矩阵 (n x n)

    返回:
        diversified_vol: 每个资产对组合波动率的贡献 [贡献1, 贡献2, ..., 贡献n]
    """
    # 转换为numpy数组
    σ = np.array(volatility_list)

    # 输入验证
    n = len(σ)
    assert cov_matrix.shape == (n, n), "协方差矩阵维度必须匹配波动率列表长度"
    assert np.all(σ > 0), "波动率必须为正"

    # 计算组合波动率 (σ_port = √(wᵀΣw))
    # 这里假设等权重 (w_i = 1/n)
    weights = np.ones(n) / n
    port_variance = weights.T @ cov_matrix @ weights
    port_vol = np.sqrt(port_variance)

    # 计算边际风险贡献 (MRC_i = (Σw)_i / σ_port)
    mrc = (cov_matrix @ weights) / port_vol

    # 计算风险贡献 (RC_i = w_i * MRC_i)
    risk_contrib = weights * mrc

    # 计算每个资产的波动率贡献
    # 贡献比例 = RC_i / σ_port
    contrib_ratio = risk_contrib / port_vol

    # 转换为波动率贡献值
    diversified_vol = contrib_ratio * σ

    return diversified_vol


# 示例使用
if __name__ == "__main__":
    # 波动率列表
    volatility_list = [0.15, 0.22, 0.18, 0.12]

    # 相关系数矩阵
    R = np.array([
        [1.0, 0.2, 0.1, -0.1],
        [0.2, 1.0, 0.3, 0.0],
        [0.1, 0.3, 1.0, 0.4],
        [-0.1, 0.0, 0.4, 1.0]
    ])

    # 创建协方差矩阵
    σ = np.array(volatility_list)
    cov_matrix = np.outer(σ, σ) * R

    # 计算diversified vol list
    div_vol = calc_diversified_vol(volatility_list, cov_matrix)

    print("各资产波动率:", volatility_list)
    print("分散化波动率贡献:", div_vol)
    print("总贡献和:", np.sum(div_vol))
    print("组合波动率:", np.sqrt(np.mean(σ) ** 2 * np.mean(np.diag(R))))

#chatgpt
import numpy as np
import pandas as pd

def calc_diversified_vol_df(volatility_list, cov_matrix):
    σ = np.array(volatility_list)
    n = len(σ)
    w = np.ones(n) / n
    port_var = w.T @ cov_matrix @ w
    σ_port = np.sqrt(port_var)
    mrc = (cov_matrix @ w) / σ_port
    rc = w * mrc
    contrib_ratio = rc / σ_port
    diversified_vol = contrib_ratio * σ
    return pd.DataFrame({
        'Original Vol':       σ,
        'Contribution Ratio': contrib_ratio,
        'Diversified Vol':    diversified_vol
    })

# 示例数据
vol_list = [0.15, 0.22, 0.18, 0.12]
R = np.array([
    [1.0, 0.2, 0.1, -0.1],
    [0.2, 1.0, 0.3, 0.0],
    [0.1, 0.3, 1.0, 0.4],
    [-0.1, 0.0, 0.4, 1.0]
])
cov_matrix = np.outer(vol_list, vol_list) * R

# 生成并添加 Total 行
df = calc_diversified_vol_df(vol_list, cov_matrix)
df.loc['Total'] = df.sum()

print(df)

