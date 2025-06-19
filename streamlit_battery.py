import streamlit as st
import scipy.io
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

# 设置中文字体
plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题


# 定义时间转换函数
def convert_to_time(time_data):
    if isinstance(time_data, np.ndarray):
        time_data = time_data[0]  # 取第一个元素
    return str(time_data)  # 转换为字符串


# 加载 .mat 文件并解析数据
@st.cache_data
def loadMat(matfile):
    # 从 UploadedFile 对象获取文件名
    filename = matfile.name.split('.')[0]

    # 读取文件内容
    data = scipy.io.loadmat(matfile)

    col = data[filename]
    col = col[0][0][0][0]
    size = col.shape[0]
    result = []

    for i in range(size):
        fields = list(col[i][3][0].dtype.fields.keys())
        d1, d2 = {}, {}

        if str(col[i][0][0]) == 'discharge':
            for j in range(len(fields)):
                t = col[i][3][0][0][j][0]
                l = [t[m][0][0] if isinstance(t[m], np.ndarray) else t[m] for m in range(len(t))]
                d2[fields[j]] = l

            d1['type'] = str(col[i][0][0])
            d1['temp'] = int(col[i][1][0])
            d1['time'] = convert_to_time(col[i][2][0])
            d1['data'] = d2
            result.append(d1)

    return result


# 计算电压统计量
@st.cache_data
def cov_charge(data):
    results = []
    for entry in data:
        V_data = entry['data']['Voltage_measured']
        V_data = np.array(V_data)

        if len(V_data) > 0:
            mean_voltage = np.mean(V_data)
            std_voltage = np.std(V_data)
            std_to_mean_ratio = std_voltage * 1000 / mean_voltage if mean_voltage != 0 else 0

            results.append({
                'mean_voltage': mean_voltage,
                'std_voltage': std_voltage,
                'std_to_mean_ratio': std_to_mean_ratio
            })
        else:
            results.append({
                'mean_voltage': None,
                'std_voltage': None,
                'std_to_mean_ratio': None
            })

    return results


# 绘制统计图表
def plot_statistics(statistics, selected_metric, color, marker, linestyle):
    metrics = {
        'mean_voltage': 'average voltage',
        'std_voltage': 'voltage standard deviation',
        'std_to_mean_ratio': 'The ratio of standard deviation to mean value'
    }

    values = [stat[selected_metric] for stat in statistics]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(values, marker=marker, linestyle=linestyle, color=color)
    ax.set_title(f'{metrics[selected_metric]} - discharge cycle')
    ax.set_xlabel('discharge cycle index')
    ax.set_ylabel(metrics[selected_metric])
    ax.grid(True)

    return fig


# 绘制电压曲线
def plot_voltage_curve(data, cycle_indices):
    fig, ax = plt.subplots(figsize=(10, 6))

    for idx in cycle_indices:
        if idx < len(data):
            time = data[idx]['data']['Time']
            voltage = data[idx]['data']['Voltage_measured']
            ax.plot(time, voltage, label=f'cycle {idx + 1}')

    ax.set_title('voltage curve')
    ax.set_xlabel('time (S)')
    ax.set_ylabel('voltage (V)')
    ax.legend()
    ax.grid(True)

    return fig


# 主应用
def main():
    st.title('电池数据可视化分析')
    st.markdown("上传MAT格式的电池数据文件，分析放电循环中的电压特性。")

    # 文件上传
    uploaded_file = st.file_uploader("选择MAT文件", type=["mat"])

    if uploaded_file is not None:
        # 缓存加载的数据
        with st.spinner('正在加载数据...'):
            data = loadMat(uploaded_file)

        if not data:
            st.warning("文件中未找到放电数据。")
            return

        st.success('数据加载成功!')

        # 计算统计量
        with st.spinner('正在计算统计数据...'):
            statistics = cov_charge(data)

        # 显示数据摘要
        st.subheader('数据摘要')
        cycles = len(data)
        st.write(f"总放电循环数: {cycles}")

        # 显示前几个循环的数据
        show_data = st.checkbox("显示数据详情", value=False)
        if show_data:
            max_display = st.slider("显示循环数", 1, min(20, cycles), 5)
            for i in range(max_display):
                st.subheader(f"循环 {i + 1}")
                cycle_data = data[i]['data']
                df = pd.DataFrame({
                    '时间(秒)': cycle_data['Time'],
                    '电压(V)': cycle_data['Voltage_measured'],
                    '电流(A)': cycle_data['Current_measured'],
                    '温度(°C)': cycle_data['Temperature_measured']
                })
                st.dataframe(df.head(1000), height=300)

        # 统计图表设置
        st.subheader('统计图表')
        metric = st.selectbox(
            "选择统计指标",
            ('mean_voltage', 'std_voltage', 'std_to_mean_ratio'),
            format_func=lambda x: {
                'mean_voltage': '平均电压',
                'std_voltage': '电压标准差',
                'std_to_mean_ratio': '标准差与平均值的比率(×1000)'
            }[x]
        )

        color = st.color_picker("选择线条颜色", "#FF0000")
        marker = st.selectbox("选择数据点标记", ['o', 's', '^', 'D', 'x'])
        linestyle = st.selectbox("选择线条样式", ['-', '--', '-.', ':'])

        # 绘制统计图表
        fig = plot_statistics(statistics, metric, color, marker, linestyle)
        st.pyplot(fig)

        # 电压曲线可视化
        st.subheader('电压曲线可视化')
        cycle_range = st.slider("选择要显示的循环范围", 1, cycles, (1, min(5, cycles)))
        start, end = cycle_range
        cycle_indices = list(range(start - 1, end))

        voltage_fig = plot_voltage_curve(data, cycle_indices)
        st.pyplot(voltage_fig)

        # 下载数据
        st.subheader('数据导出')
        export_df = pd.DataFrame({
            '循环索引': list(range(1, cycles + 1)),
            '平均电压(V)': [stat['mean_voltage'] for stat in statistics],
            '电压标准差(V)': [stat['std_voltage'] for stat in statistics],
            '标准差与平均值比率(×1000)': [stat['std_to_mean_ratio'] for stat in statistics]
        })

        csv_data = export_df.to_csv(sep='\t', na_rep='nan')
        st.download_button(
            label="下载统计数据",
            data=csv_data,
            file_name=f"{uploaded_file.name.split('.')[0]}_statistics.tsv",
            mime="text/tab-separated-values"
        )


if __name__ == "__main__":
    main()
