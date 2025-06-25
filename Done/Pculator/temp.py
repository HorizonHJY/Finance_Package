import pandas as pd
import numpy as np

# Volatility data from the first image
vol_data = {
    'RISK_FACTOR': ['DE_LWRRH_CNM_FOB_N25', 'EURONEXT_ECO_Q25', 'EU_DTCHML_CNODG_FOB_U25'],
    'VOLATILITY': [0.00739695131778717, 0.0113457515835762, 0.0105676054954529]
}

# Correlation matrix from the second image
corr_matrix = [
    [1.0, 0.25085, 0.21820],
    [0.25085, 1.0, 0.74844],
    [0.21820, 0.74844, 1.0]
]

# 计算协方差矩阵
risk_factors = vol_data['RISK_FACTOR']
vol_vector = np.array(vol_data['VOLATILITY'])
corr_df = pd.DataFrame(corr_matrix, index=risk_factors, columns=risk_factors)

# 关键计算步骤
cov_matrix = np.outer(vol_vector, vol_vector) * corr_df.to_numpy()
cov_df = pd.DataFrame(cov_matrix, index=risk_factors, columns=risk_factors)

print("波动率向量:")
print(vol_vector)

print("\n相关系数矩阵:")
print(corr_df)

print("\n协方差矩阵:")
print(cov_df)