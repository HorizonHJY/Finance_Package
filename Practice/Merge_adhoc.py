import pandas as pd
import time
from flask import request, render_template, g
import os


def credit_combine_exposure_calculate():
    if request.method != 'POST':
        return render_template('login.html')

    g.start = time.time()

    # 文件处理函数
    def save_uploaded_file(file_obj):
        """安全保存上传文件并返回路径"""
        if not file_obj or file_obj.filename == '':
            raise ValueError("无效文件上传")

        upload_dir = f"{Vision.GLOBAL_DIR}/data/upload"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, file_obj.filename)
        file_obj.save(file_path)
        return file_path

    try:
        # 保存文件并获取路径
        viterra_path = save_uploaded_file(request.files.get('viterra_file'))
        bunge_path = save_uploaded_file(request.files.get('bunge_file'))

        # 列名映射配置
        VITERRA_COLUMN_MAP = {
            'Supergroup': 'Customer Supergroup',
            'Legal Entity': 'Business Unit Original',
            'Subdivision': 'Subdivision',
            'Position Date': 'Position Date',
            'Sum of Secured AR': 'AR (Secured)',
            'Sum of Unsecured AR': 'AR (Unsecured)',
            'Sum of Total AR': 'AR (Total)',
            'Sum of MTM': 'MTM Original',
            'Sum of MTM Positive': 'MTM (+)',
            'Sum of Current AR': 'AR (Total) (Current)',
            'Sum of Aging 1-31': 'AR (Total) (1-31)',
            'Sum of Aging 32+': 'AR (Total) (Over 32)'
        }

        # 读取Viterra数据
        viterra_data = pd.read_csv(
            viterra_path,
            encoding='ISO-8859-1',
            dtype={'Customer Country': str}  # 明确指定类型
        )

        # 清理列名并过滤列
        viterra_data.columns = viterra_data.columns.str.strip()
        viterra_data = viterra_data.loc[:, ~viterra_data.columns.str.startswith('Unnamed')]
        viterra_data.rename(columns=VITERRA_COLUMN_MAP, inplace=True)
        viterra_data.drop(columns=['Customer Country'], errors='ignore', inplace=True)

        # 数值列清理
        NUMERIC_COLS = [
            'AR (Secured)', 'AR (Unsecured)', 'AR (Total)', 'MTM Original', 'MTM (+)',
            'AR (Total) (Current)', 'AR (Total) (1-31)', 'AR (Total) (Over 32)'
        ]
        for col in NUMERIC_COLS:
            if col in viterra_data:
                viterra_data[col] = (
                    viterra_data[col]
                    .astype(str)
                    .str.replace(r'[,-]', '', regex=True)  # 合并替换操作
                    .replace('', '0')
                    .astype(float)
                    .fillna(0)
                )

        # 添加计算列
        viterra_data['Total Exposure (AR + MTM)'] = (
                viterra_data['AR (Total)'].fillna(0) +
                viterra_data['MTM (+)'].fillna(0)
        )

        # 读取Bunge数据
        bunge_data = pd.read_excel(bunge_path, sheet_name='data')

        # 添加数据源标记
        viterra_data['Data_Source'] = 'Viterra'
        bunge_data['Data_Source'] = 'Bunge'

        # 合并数据集
        combined_data = pd.concat(
            [bunge_data, viterra_data],
            axis=0,
            ignore_index=True,
            sort=False
        )

        # 确保输出目录存在
        output_dir = f"{Vision.GLOBAL_DIR}/data/download"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "credit_combine_exposure_result.csv")

        combined_data.to_csv(output_path, index=False)

        run_time = round(time.time() - g.start, 2)
        return render_template('credit_combine_exposure_result.html', run_time=run_time)

    except Exception as e:
        # 添加错误处理
        error_msg = f"处理失败: {str(e)}"
        return render_template('error.html', error_message=error_msg), 500