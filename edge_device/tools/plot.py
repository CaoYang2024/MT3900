import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# --- 1. 顶刊风格设置 ---
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Helvetica', 'Arial', 'DejaVu Sans']
plt.rcParams['font.size'] = 14
plt.rcParams['axes.linewidth'] = 1.2
plt.rcParams['xtick.major.width'] = 1.2
plt.rcParams['ytick.major.width'] = 1.2
plt.rcParams['xtick.direction'] = 'out'
plt.rcParams['ytick.direction'] = 'out'
plt.rcParams['axes.labelsize'] = 14
plt.rcParams['axes.titlesize'] = 16
plt.rcParams['axes.titleweight'] = 'bold'
plt.rcParams['legend.fontsize'] = 12
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.bbox'] = 'tight'

# --- 2. 配色方案 ---
COLOR_CAM = "#3C5488"  
COLOR_ULTRA = "#E64B35" 
SENSOR_COLORS = {'Camera': COLOR_CAM, 'Ultrasonic': COLOR_ULTRA}

COMP_PALETTE = {
    'Detect/Overhead': '#E64B35', 
    'Lookup': '#F39B7F',          
    'Parse': '#00A087',           
    'Pull Image': '#4DBBD5',      
    'Start': '#3C5488',           
    'Advertise': '#8491B4'        
}
STACK_ORDER = ['Detect/Overhead', 'Lookup', 'Parse', 'Pull Image', 'Start', 'Advertise']

# --- 3. 数据准备 ---
df = pd.read_csv('results2.csv')
df['sensor_name'] = df['sensor_name'].str.title()

known_cols = ['duration_lookup_ms', 'duration_parse_ms', 'duration_pull_ms', 'duration_start_ms', 'duration_advertise_ms']
df['known_sum'] = df[known_cols].sum(axis=1)
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
df.rename(columns=rename_map, inplace=True)

df_agg = df.groupby('sensor_name')[STACK_ORDER].mean()
df_stats = df.groupby('sensor_name')['total_tto_ms'].agg(['mean', 'std', 'count'])
df_stats['ci95'] = 1.96 * (df_stats['std'] / np.sqrt(df_stats['count']))

df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp')
df['run_index'] = range(1, len(df) + 1)

HOT_THR = 3000
hot_means = df[df['total_tto_ms'] < HOT_THR].groupby('sensor_name')['total_tto_ms'].mean()

# --- 4. 开始绘图 (Layout) ---
fig = plt.figure(figsize=(18, 12), constrained_layout=True)
gs = fig.add_gridspec(2, 2, hspace=0.15, wspace=0.05)

# === A. Horizontal Composition (Legend Moved Outside Right) ===
ax1 = fig.add_subplot(gs[0, 0])
sensors = df_agg.index
height = 0.5 
left = np.zeros(len(sensors))

# Horizontal Stack
for col in STACK_ORDER:
    ax1.barh(sensors, df_agg[col], left=left, label=col, 
             color=COMP_PALETTE[col], edgecolor='white', linewidth=0.5, height=height, alpha=0.95)
    left += df_agg[col]

# Error Bars
y_pos = np.arange(len(sensors))
totals = df_stats['mean']
ci = df_stats['ci95']
ax1.errorbar(totals, y_pos, xerr=ci, fmt='none', ecolor='#333333', elinewidth=2.5, capsize=6, capthick=2.5)

# Annotate
for i, (sensor, total) in enumerate(totals.items()):
    ax1.text(total + ci[sensor] + 50, i, f"{total:.0f}", va='center', fontsize=12, fontweight='bold', color='#333333')

ax1.set_title('a  Mean TTO Composition (±95% CI)', loc='left', pad=15)
ax1.set_xlabel('Time (ms)')
# 这里不需要留太多空白了，因为图例移出去了
ax1.set_xlim(right=totals.max() * 1.15) 

# [修改点]：图例移到坐标轴外侧 (bbox_to_anchor)
# (1.02, 1.0) 表示：图例的左上角 (loc='upper left') 对齐坐标轴的右上角 (1.02, 1.0)
handles, labels = ax1.get_legend_handles_labels()
ax1.legend(handles, labels, bbox_to_anchor=(1.02, 1.0), loc='upper left', 
           frameon=False, title='Stage', ncols=1, fontsize=10)

ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)


# === B. Stability Trend (Scatter Only) ===
ax2 = fig.add_subplot(gs[0, 1])

for sensor in ['Camera', 'Ultrasonic']:
    subset = df[df['sensor_name'] == sensor]
    ax2.plot(subset['run_index'], subset['total_tto_ms'], marker='o', linestyle='None', markersize=7, 
             color=SENSOR_COLORS[sensor], label=sensor, alpha=0.9)
    
    val = hot_means[sensor]
    ax2.axhline(val, color=SENSOR_COLORS[sensor], linestyle='--', linewidth=1.5, alpha=0.6)
    
    offset = 200 if sensor == 'Camera' else -300
    ax2.annotate(f"Hot Avg: {val:.0f}", xy=(subset['run_index'].max(), val), 
                 xytext=(subset['run_index'].max()+2, val + offset),
                 arrowprops=dict(arrowstyle='-', color=SENSOR_COLORS[sensor], lw=1),
                 color=SENSOR_COLORS[sensor], fontsize=11, fontweight='bold', va='center')

outlier = df.loc[df['total_tto_ms'].idxmax()]
ax2.annotate('Cold Start Spike', 
             xy=(outlier['run_index'], outlier['total_tto_ms']), 
             xytext=(outlier['run_index']-5, outlier['total_tto_ms']),
             arrowprops=dict(facecolor='black', shrink=0.05, width=1.5, headwidth=8),
             fontsize=11, fontweight='bold', ha='right')

ax2.set_title('b  Temporal Stability (Scatter)', loc='left', pad=15)
ax2.set_ylabel('Total TTO (ms)')
ax2.set_xlabel('Run Sequence')
ax2.set_ylim(bottom=1000)
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)
ax2.legend(frameon=False, loc='upper right')


# === C. Reliability CDF ===
ax3 = fig.add_subplot(gs[1, 0])

for sensor in ['Camera', 'Ultrasonic']:
    subset = df[df['sensor_name'] == sensor]['total_tto_ms']
    x = np.sort(subset)
    y = np.arange(1, len(x)+1) / len(x)
    
    ax3.step(x, y, where='post', label=sensor, color=SENSOR_COLORS[sensor], linewidth=3)
    
    p95 = np.percentile(subset, 95)
    ax3.vlines(p95, 0, 0.95, colors=SENSOR_COLORS[sensor], linestyles=':', linewidth=1.5, alpha=0.7)
    
    y_p95 = 0.5 if sensor == 'Camera' else 0.2
    ax3.text(p95, y_p95, f' P95: {p95:.0f}', color=SENSOR_COLORS[sensor], fontsize=10, fontweight='bold', rotation=90, va='center')

ax3.set_title('c  Reliability Curve (CDF)', loc='left', pad=15)
ax3.set_xlabel('Latency (ms)')
ax3.set_ylabel('Probability')
ax3.spines['top'].set_visible(False)
ax3.spines['right'].set_visible(False)
ax3.grid(axis='x', linestyle=':', alpha=0.3)
ax3.legend(frameon=False, loc='lower right')


# === D. Latency Distribution ===
ax4 = fig.add_subplot(gs[1, 1])

sns.violinplot(data=df, x='sensor_name', y='total_tto_ms', hue='sensor_name', ax=ax4,
               palette=SENSOR_COLORS, inner=None, saturation=1, linewidth=0, width=0.7, alpha=0.3, legend=False) 

sns.boxplot(data=df, x='sensor_name', y='total_tto_ms', ax=ax4,
            width=0.15, boxprops={'facecolor':'white', 'edgecolor':'#333', 'linewidth':2, 'alpha':0.9},
            whiskerprops={'color':'#333', 'linewidth':2},
            capprops={'color':'#333', 'linewidth':2},
            medianprops={'color':'#333', 'linewidth':2.5},
            showfliers=False)

sns.stripplot(data=df, x='sensor_name', y='total_tto_ms', ax=ax4,
              color='#222', alpha=0.6, jitter=True, size=7)

ax4.set_title('d  Latency Distribution', loc='left', pad=15)
ax4.set_ylabel('Total TTO (ms)')
ax4.set_xlabel('')
ax4.spines['top'].set_visible(False)
ax4.spines['right'].set_visible(False)

output_file = 'top_journal_dashboard_final_v3.png'
plt.savefig(output_file, dpi=300, bbox_inches='tight')
print(f"最终版图表已生成: {output_file}")
plt.show()