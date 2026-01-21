import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
from matplotlib.ticker import MaxNLocator

# ==========================================
# 1. 顶刊风格全局设置 (Global Style)
# ==========================================
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Helvetica', 'Arial', 'DejaVu Sans']
plt.rcParams['font.size'] = 15
plt.rcParams['axes.linewidth'] = 1.5
plt.rcParams['xtick.major.width'] = 1.5
plt.rcParams['ytick.major.width'] = 1.5
plt.rcParams['xtick.direction'] = 'out'
plt.rcParams['ytick.direction'] = 'out'
plt.rcParams['axes.labelsize'] = 16
plt.rcParams['legend.fontsize'] = 13
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.bbox'] = 'tight'

# 配色方案
COLOR_CAM = "#3C5488"   # 深蓝 (Camera)
COLOR_ULTRA = "#E64B35" # 橘红 (Ultrasonic)
SENSOR_COLORS = {'Camera': COLOR_CAM, 'Ultrasonic': COLOR_ULTRA}

# 趋势图统一配色
COLOR_CPU_TREND = "#2C3E50"   # 深蓝灰
COLOR_TEMP_TREND = "#C0392B"  # 深红

# TTO 堆叠颜色
COMP_PALETTE = {
    'Detect/Overhead': '#DC0000', 
    'Lookup': '#F39B7F',          
    'Parse': '#00A087',           
    'Pull Image': '#4DBBD5',      
    'Start': '#3C5488',           
    'Advertise': '#8491B4'        
}
STACK_ORDER = ['Detect/Overhead', 'Lookup', 'Parse', 'Pull Image', 'Start', 'Advertise']

# ==========================================
# 2. 数据处理 (Data Prep)
# ==========================================
def load_and_prep_data(filename='result.csv'):
    if not os.path.exists(filename):
        # 尝试回退到 results2.csv
        if os.path.exists('results2.csv'):
            filename = 'results2.csv'
        else:
            print(f"Error: {filename} not found.")
            return None

    df = pd.read_csv(filename)
    df = df[df['success'] == True].copy()

    df['sensor_name'] = df['sensor_name'].str.title()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['run_index'] = df.index + 1 

    required_cols = [
        'duration_lookup_ms', 'duration_parse_ms', 'duration_pull_ms', 
        'duration_start_ms', 'duration_advertise_ms', 'avg_cpu', 'avg_temp'
    ]
    for col in required_cols:
        if col not in df.columns:
            print(f"Warning: Column '{col}' missing. Filling with 0.")
            df[col] = 0

    time_cols = ['duration_lookup_ms', 'duration_parse_ms', 'duration_pull_ms', 'duration_start_ms', 'duration_advertise_ms']
    df['known_sum'] = df[time_cols].sum(axis=1)
    
    df['T_detect'] = df['total_tto_ms'] - df['known_sum']
    df['T_detect'] = df['T_detect'].clip(lower=0)

    rename_map = {
        'T_detect': 'Detect/Overhead',
        'duration_lookup_ms': 'Lookup',
        'duration_parse_ms': 'Parse',
        'duration_pull_ms': 'Pull Image',
        'duration_start_ms': 'Start',
        'duration_advertise_ms': 'Advertise'
    }
    df_renamed = df.rename(columns=rename_map)
    
    return df_renamed

# ==========================================
# 图 1: Mean TTO Composition (堆叠图)
# ==========================================
def plot_fig1(df):
    df_agg = df.groupby('sensor_name')[STACK_ORDER].mean()
    df_stats = df.groupby('sensor_name')['total_tto_ms'].agg(['mean', 'std', 'count'])
    df_stats['ci95'] = 1.96 * (df_stats['std'] / np.sqrt(df_stats['count']))

    fig, ax = plt.subplots(figsize=(10, 6))
    
    sensors = df_agg.index
    left = np.zeros(len(sensors))
    
    for col in STACK_ORDER:
        ax.barh(sensors, df_agg[col], left=left, label=col, 
                color=COMP_PALETTE[col], edgecolor='white', height=0.6, alpha=0.95)
        left += df_agg[col]
    
    y_pos = np.arange(len(sensors))
    totals = df_stats['mean']
    ci = df_stats['ci95']
    ax.errorbar(totals, y_pos, xerr=ci, fmt='none', ecolor='#333333', elinewidth=3, capsize=8, capthick=3)
    
    for i, (sensor, total) in enumerate(totals.items()):
        ax.text(total + ci[sensor] + 50, i, f"{total:.0f} ms", va='center', fontsize=14, fontweight='bold', color='#333')

    ax.set_xlabel('Latency (ms)')
    ax.set_xlim(right=totals.max() * 1.3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, bbox_to_anchor=(1.0, 1.08), loc='lower right', title=None, frameon=False, ncol=3)
    
    plt.savefig('Fig1_TTO_Composition_Clean.png', bbox_inches='tight')
    print("Generated: Fig1_TTO_Composition_Clean.png")

# ==========================================
# 图 2: Timeline (Scatter)
# ==========================================
def plot_fig2(df):
    fig, ax = plt.subplots(figsize=(12, 6))
    
    for sensor in ['Camera', 'Ultrasonic']:
        subset = df[df['sensor_name'] == sensor]
        if subset.empty: continue
        ax.plot(subset['run_index'], subset['total_tto_ms'], 
                marker='o', linestyle='-', linewidth=1.5, markersize=8, 
                color=SENSOR_COLORS.get(sensor, '#333'), label=sensor, alpha=0.8)
        
        cold_start = subset.loc[subset['total_tto_ms'].idxmax()]
        if cold_start['total_tto_ms'] > subset['total_tto_ms'].median() * 1.5:
            ax.annotate(f'Cold Start\n({sensor})', 
                        xy=(cold_start['run_index'], cold_start['total_tto_ms']), 
                        xytext=(cold_start['run_index']+1, cold_start['total_tto_ms']),
                        arrowprops=dict(facecolor='black', shrink=0.05, width=1, headwidth=6),
                        fontsize=11, fontweight='bold')

    ax.set_xlabel('Experiment Sequence (Plug-in Events)')
    ax.set_ylabel('Total TTO (ms)')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(frameon=False, loc='upper right')
    
    plt.savefig('Fig2_Timeline_Clean.png', bbox_inches='tight')
    print("Generated: Fig2_Timeline_Clean.png")

# ==========================================
# 图 3: Average CPU Usage (折线趋势图 - 整体)
# ==========================================
def plot_fig3(df):
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # 1. 绘制散点 (透明度高一点，作为背景)
    ax.scatter(df['run_index'], df['avg_cpu'], 
               color=COLOR_CPU_TREND, alpha=0.5, s=60)
    
    # 2. 绘制平滑趋势线 (Order=2 多项式拟合)
    sns.regplot(data=df, x='run_index', y='avg_cpu', ax=ax, scatter=False,
                color=COLOR_CPU_TREND, order=2,
                line_kws={'linewidth': 3, 'alpha': 0.9, 'label': 'Trend'})

    # 3. 标注平均值
    mean_val = df['avg_cpu'].mean()
    ax.axhline(mean_val, color='gray', linestyle='--', linewidth=1.5, alpha=0.6)
    # 放在最右侧
    ax.text(df['run_index'].max() + 0.5, mean_val, f"Mean: {mean_val:.1f}%", 
            va='center', color='gray', fontsize=12, fontweight='bold')

    # 设置轴
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylabel('Average CPU Usage (%)')
    ax.set_xlabel('Experiment Sequence')
    
    # Y轴范围自适应，保留一点空间
    ax.set_ylim(0, max(50, df['avg_cpu'].max() + 10))
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    plt.savefig('Fig3_CPU_Usage_Clean.png', bbox_inches='tight')
    print("Generated: Fig3_CPU_Usage_Clean.png")

# ==========================================
# 图 4: Temperature (折线趋势图 - 整体)
# ==========================================
def plot_fig4(df):
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # 1. 绘制散点
    ax.scatter(df['run_index'], df['avg_temp'], 
               color=COLOR_TEMP_TREND, alpha=0.5, s=60)
    
    # 2. 绘制平滑趋势线
    sns.regplot(data=df, x='run_index', y='avg_temp', ax=ax, scatter=False,
                color=COLOR_TEMP_TREND, order=2,
                line_kws={'linewidth': 3, 'alpha': 0.9, 'label': 'Thermal Trend'})

    # 3. 标注平均温度
    mean_val = df['avg_temp'].mean()
    # 标注放在左侧一点
    ax.text(1, mean_val + 0.5, f"Avg: {mean_val:.1f}°C", 
            color=COLOR_TEMP_TREND, fontsize=12, fontweight='bold')

    # 设置轴
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylabel('Average Temperature (°C)')
    ax.set_xlabel('Experiment Sequence')
    
    # 动态 Y 轴
    y_min = max(0, df['avg_temp'].min() - 3)
    y_max = df['avg_temp'].max() + 3
    ax.set_ylim(y_min, y_max)
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.savefig('Fig4_Temperature_Clean.png', bbox_inches='tight')
    print("Generated: Fig4_Temperature_Clean.png")

# ==========================================
# 主程序
# ==========================================
if __name__ == "__main__":
    df = load_and_prep_data('result.csv')
    
    if df is not None and not df.empty:
        try:
            plot_fig1(df)
            plot_fig2(df)
            plot_fig3(df)
            plot_fig4(df)
            print("\nAll clean plots generated successfully!")
        except Exception as e:
            print(f"\nAn error occurred during plotting: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("No valid data found to plot.")