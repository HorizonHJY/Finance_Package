import pandas as pd
import numpy as np
from collections import defaultdict
import os
import time
import csv
from typing import Dict, List, Tuple, Optional, Union


class CSVComparator:
    def __init__(self, file1: str, file2: str,
                 key_columns: Optional[List[str]] = None,
                 ignore_columns: Optional[List[str]] = None,
                 tolerance: float = 1e-6,
                 case_sensitive: bool = False,
                 output_format: str = 'console'):
        """
        高级CSV文件比较工具

        参数:
        file1, file2: 要比较的CSV文件路径
        key_columns: 用于匹配行的关键列列表
        ignore_columns: 忽略比较的列列表
        tolerance: 数值比较的容差
        case_sensitive: 是否区分大小写
        output_format: 输出格式 ('console', 'csv', 'excel')
        """
        self.file1 = file1
        self.file2 = file2
        self.key_columns = key_columns
        self.ignore_columns = ignore_columns or []
        self.tolerance = tolerance
        self.case_sensitive = case_sensitive
        self.output_format = output_format
        self.df1 = None
        self.df2 = None
        self.diff_report = defaultdict(list)
        self.stats = {
            'total_rows_df1': 0,
            'total_rows_df2': 0,
            'common_rows': 0,
            'unique_to_df1': 0,
            'unique_to_df2': 0,
            'differing_rows': 0,
            'differing_cells': 0,
            'column_diffs': {}
        }
        self.comparison_time = 0

    def _read_csv(self, file_path: str) -> pd.DataFrame:
        """智能读取CSV文件，处理常见格式问题"""
        try:
            # 尝试自动检测分隔符和编码
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                dialect = csv.Sniffer().sniff(f.read(1024))
                f.seek(0)
                encoding = 'utf-8'

            return pd.read_csv(
                file_path,
                sep=dialect.delimiter,
                encoding=encoding,
                dtype=str,  # 初始读取为字符串以保留原始格式
                na_values=['', 'NA', 'N/A', 'null', 'NULL'],
                keep_default_na=False
            )
        except UnicodeDecodeError:
            # 回退到其他常见编码
            for encoding in ['latin1', 'ISO-8859-1', 'cp1252']:
                try:
                    return pd.read_csv(file_path, encoding=encoding)
                except:
                    continue
            raise ValueError(f"无法确定文件编码: {file_path}")
        except Exception as e:
            raise IOError(f"读取文件失败: {file_path}\n错误: {str(e)}")

    def _preprocess_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据预处理"""
        # 清理列名
        df.columns = df.columns.str.strip()

        # 处理大小写敏感性
        if not self.case_sensitive:
            df = df.applymap(lambda x: x.lower() if isinstance(x, str) else x)
            df.columns = [col.lower() for col in df.columns]

        # 转换数值列
        for col in df.columns:
            if col in self.ignore_columns:
                continue

            # 尝试转换为数值
            numeric_vals = pd.to_numeric(df[col], errors='coerce')
            if not numeric_vals.isna().all():
                df[col] = numeric_vals

        # 处理日期列
        date_cols = [col for col in df.columns if 'date' in col.lower()]
        for col in date_cols:
            try:
                df[col] = pd.to_datetime(df[col], errors='coerce')
            except:
                pass

        return df

    def _validate_columns(self):
        """验证两个数据框的列是否一致"""
        cols1 = set(self.df1.columns)
        cols2 = set(self.df2.columns)

        # 检查列差异
        missing_in_df2 = cols1 - cols2
        missing_in_df1 = cols2 - cols1

        if missing_in_df2:
            self.diff_report['column_diffs'].append(
                f"文件1有但文件2没有的列: {', '.join(missing_in_df2)}"
            )

        if missing_in_df1:
            self.diff_report['column_diffs'].append(
                f"文件2有但文件1没有的列: {', '.join(missing_in_df1)}"
            )

        # 更新公共列
        self.common_columns = list(cols1 & cols2)
        self.comparable_columns = [
            col for col in self.common_columns
            if col not in self.ignore_columns
        ]

        return len(missing_in_df1) == 0 and len(missing_in_df2) == 0

    def _compare_rows(self):
        """比较行内容"""
        # 设置索引用于比较
        if self.key_columns:
            # 验证关键列是否存在
            missing_keys = [key for key in self.key_columns if key not in self.common_columns]
            if missing_keys:
                raise ValueError(f"关键列不存在: {', '.join(missing_keys)}")

            df1 = self.df1.set_index(self.key_columns)
            df2 = self.df2.set_index(self.key_columns)
        else:
            # 没有关键列时使用行号
            df1 = self.df1.reset_index(drop=True)
            df2 = self.df2.reset_index(drop=True)

        # 统计行数
        self.stats['total_rows_df1'] = len(df1)
        self.stats['total_rows_df2'] = len(df2)

        # 找出唯一行
        if self.key_columns:
            index1 = set(df1.index)
            index2 = set(df2.index)

            unique_to_df1 = index1 - index2
            unique_to_df2 = index2 - index1

            self.stats['unique_to_df1'] = len(unique_to_df1)
            self.stats['unique_to_df2'] = len(unique_to_df2)

            # 记录唯一行
            if unique_to_df1:
                self.diff_report['unique_to_df1'] = df1.loc[list(unique_to_df1)].reset_index()
            if unique_to_df2:
                self.diff_report['unique_to_df2'] = df2.loc[list(unique_to_df2)].reset_index()

            # 获取公共行
            common_index = list(index1 & index2)
            common_df1 = df1.loc[common_index]
            common_df2 = df2.loc[common_index]
        else:
            # 没有关键列时，直接比较所有行
            common_df1 = df1
            common_df2 = df2
            self.stats['unique_to_df1'] = 0
            self.stats['unique_to_df2'] = 0

        self.stats['common_rows'] = len(common_df1)

        # 比较公共行
        diff_mask = pd.DataFrame(False, index=common_df1.index, columns=common_df1.columns)

        for col in self.comparable_columns:
            col_diffs = 0

            if pd.api.types.is_numeric_dtype(common_df1[col]) and pd.api.types.is_numeric_dtype(common_df2[col]):
                # 数值列比较（带容差）
                col_diff = np.abs(common_df1[col] - common_df2[col]) > self.tolerance
                col_diff.fillna(True, inplace=True)  # 处理NaN
                col_diffs = col_diff.sum()
                diff_mask[col] = col_diff
            else:
                # 非数值列比较
                col_diff = common_df1[col] != common_df2[col]
                col_diff.fillna(True, inplace=True)  # 处理NaN
                col_diffs = col_diff.sum()
                diff_mask[col] = col_diff

            self.stats['column_diffs'][col] = col_diffs

        # 找出有差异的行
        row_diff = diff_mask.any(axis=1)
        self.stats['differing_rows'] = row_diff.sum()
        self.stats['differing_cells'] = diff_mask.sum().sum()

        if row_diff.sum() > 0:
            # 创建差异报告
            diff_df = pd.DataFrame({
                'row_key': common_df1.index[row_diff] if self.key_columns else row_diff.index[row_diff],
                'columns_changed': diff_mask[row_diff].apply(lambda x: ', '.join(x.index[x]), axis=1),
                'file1_values': common_df1[row_diff].apply(lambda x: x.to_dict(), axis=1),
                'file2_values': common_df2[row_diff].apply(lambda x: x.to_dict(), axis=1)
            })

            self.diff_report['differing_rows'] = diff_df

    def compare(self) -> Dict:
        """执行比较并生成报告"""
        start_time = time.time()

        try:
            # 读取文件
            self.df1 = self._read_csv(self.file1)
            self.df2 = self._read_csv(self.file2)

            # 预处理
            self.df1 = self._preprocess_dataframe(self.df1)
            self.df2 = self._preprocess_dataframe(self.df2)

            # 验证列
            if not self._validate_columns():
                self.diff_report['status'] = '失败: 列不匹配'
                return self.diff_report

            # 比较行
            self._compare_rows()

            # 生成摘要
            summary = [
                f"文件1: {os.path.basename(self.file1)} ({self.stats['total_rows_df1']} 行)",
                f"文件2: {os.path.basename(self.file2)} ({self.stats['total_rows_df2']} 行)",
                f"公共列: {len(self.common_columns)}",
                f"可比较列: {len(self.comparable_columns)}",
                f"文件1独有行: {self.stats['unique_to_df1']}",
                f"文件2独有行: {self.stats['unique_to_df2']}",
                f"公共行: {self.stats['common_rows']}",
                f"差异行: {self.stats['differing_rows']}",
                f"差异单元格: {self.stats['differing_cells']}",
                ""
            ]

            # 添加列差异统计
            if self.stats['differing_cells'] > 0:
                summary.append("列差异统计:")
                for col, count in self.stats['column_diffs'].items():
                    if count > 0:
                        summary.append(f"  - {col}: {count} 个差异")

            self.diff_report['summary'] = "\n".join(summary)
            self.diff_report['status'] = '完成'

            # 输出结果
            self._output_results()

        except Exception as e:
            self.diff_report['status'] = f'错误: {str(e)}'
            self.diff_report['error'] = str(e)

        self.comparison_time = time.time() - start_time
        self.diff_report['comparison_time'] = f"{self.comparison_time:.2f} 秒"

        return self.diff_report

    def _output_results(self):
        """根据指定格式输出结果"""
        if self.output_format == 'console':
            self._print_console_report()
        elif self.output_format == 'csv':
            self._export_csv_report()
        elif self.output_format == 'excel':
            self._export_excel_report()

    def _print_console_report(self):
        """控制台输出报告"""
        print("\n" + "=" * 50)
        print("CSV 文件比较报告")
        print("=" * 50)

        # 打印摘要
        print("\n[摘要]")
        print(self.diff_report['summary'])

        # 打印列差异
        if 'column_diffs' in self.diff_report and self.diff_report['column_diffs']:
            print("\n[列差异]")
            for diff in self.diff_report['column_diffs']:
                print(f"  - {diff}")

        # 打印唯一行
        if 'unique_to_df1' in self.diff_report and not self.diff_report['unique_to_df1'].empty:
            print(f"\n[文件1独有行 ({self.stats['unique_to_df1']} 行)]")
            print(self.diff_report['unique_to_df1'].head(5))
            if self.stats['unique_to_df1'] > 5:
                print(f"... 只显示前5行，共 {self.stats['unique_to_df1']} 行")

        if 'unique_to_df2' in self.diff_report and not self.diff_report['unique_to_df2'].empty:
            print(f"\n[文件2独有行 ({self.stats['unique_to_df2']} 行)]")
            print(self.diff_report['unique_to_df2'].head(5))
            if self.stats['unique_to_df2'] > 5:
                print(f"... 只显示前5行，共 {self.stats['unique_to_df2']} 行")

        # 打印差异行
        if 'differing_rows' in self.diff_report and not self.diff_report['differing_rows'].empty:
            print(f"\n[内容差异行 ({self.stats['differing_rows']} 行)]")
            for _, row in self.diff_report['differing_rows'].head(3).iterrows():
                print(f"\n行标识: {row['row_key']}")
                print(f"差异列: {row['columns_changed']}")
                print("文件1值:")
                for k, v in row['file1_values'].items():
                    if k in row['columns_changed']:
                        print(f"  {k}: {v}")
                print("文件2值:")
                for k, v in row['file2_values'].items():
                    if k in row['columns_changed']:
                        print(f"  {k}: {v}")

            if self.stats['differing_rows'] > 3:
                print(f"\n... 只显示前3行，共 {self.stats['differing_rows']} 行差异")

        print("\n" + "=" * 50)
        print(f"比较完成，耗时: {self.comparison_time:.2f} 秒")
        print("=" * 50)

    def _export_csv_report(self):
        """导出CSV格式的详细报告"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_dir = "csv_comparison_reports"
        os.makedirs(output_dir, exist_ok=True)

        # 导出摘要
        with open(f"{output_dir}/comparison_summary_{timestamp}.txt", 'w') as f:
            f.write(self.diff_report['summary'])

        # 导出唯一行
        if 'unique_to_df1' in self.diff_report and not self.diff_report['unique_to_df1'].empty:
            self.diff_report['unique_to_df1'].to_csv(
                f"{output_dir}/unique_to_file1_{timestamp}.csv", index=False
            )

        if 'unique_to_df2' in self.diff_report and not self.diff_report['unique_to_df2'].empty:
            self.diff_report['unique_to_df2'].to_csv(
                f"{output_dir}/unique_to_file2_{timestamp}.csv", index=False
            )

        # 导出差异行
        if 'differing_rows' in self.diff_report and not self.diff_report['differing_rows'].empty:
            self.diff_report['differing_rows'].to_csv(
                f"{output_dir}/differing_rows_{timestamp}.csv", index=False
            )

        print(f"报告已保存到: {output_dir}/")

    def _export_excel_report(self):
        """导出Excel格式的详细报告"""
        try:
            import openpyxl
        except ImportError:
            print("需要安装 openpyxl 库来导出Excel报告: pip install openpyxl")
            return

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = f"csv_comparison_report_{timestamp}.xlsx"

        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # 摘要表
            summary_df = pd.DataFrame([self.diff_report['summary'].split('\n')], columns=['摘要'])
            summary_df.to_excel(writer, sheet_name='摘要', index=False)

            # 列差异
            if 'column_diffs' in self.diff_report and self.diff_report['column_diffs']:
                col_diff_df = pd.DataFrame(self.diff_report['column_diffs'], columns=['列差异'])
                col_diff_df.to_excel(writer, sheet_name='列差异', index=False)

            # 唯一行
            if 'unique_to_df1' in self.diff_report and not self.diff_report['unique_to_df1'].empty:
                self.diff_report['unique_to_df1'].to_excel(
                    writer, sheet_name='文件1独有行', index=False
                )

            if 'unique_to_df2' in self.diff_report and not self.diff_report['unique_to_df2'].empty:
                self.diff_report['unique_to_df2'].to_excel(
                    writer, sheet_name='文件2独有行', index=False
                )

            # 差异行
            if 'differing_rows' in self.diff_report and not self.diff_report['differing_rows'].empty:
                self.diff_report['differing_rows'].to_excel(
                    writer, sheet_name='内容差异行', index=False
                )

            # 统计数据表
            stats_df = pd.DataFrame.from_dict(self.stats, orient='index', columns=['值'])
            stats_df.index.name = '统计项'
            stats_df.to_excel(writer, sheet_name='统计信息')

        print(f"Excel报告已保存为: {output_file}")


# 使用示例
if __name__ == "__main__":
    # 基本用法
    comparator = CSVComparator(
        file1='file1.csv',
        file2='file2.csv',
        key_columns=['id', 'date'],  # 用于匹配行的关键列
        ignore_columns=['timestamp', 'generated_id'],  # 忽略比较的列
        tolerance=0.01,  # 数值比较容差
        case_sensitive=False,
        output_format='console'  # 可选 'console', 'csv', 'excel'
    )

    report = comparator.compare()

    # 高级用法 - 直接访问报告数据
    if report['status'] == '完成':
        print(f"比较摘要:\n{report['summary']}")
        print(f"耗时: {report['comparison_time']}")

        if 'differing_rows' in report:
            print(f"找到 {len(report['differing_rows'])} 行差异")