import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.ticker as ticker
from supabase import create_client
from datetime import datetime, timedelta
import re
import os
import requests
import numpy as np

# ================= 1. 连接配置 (支持 Secrets 和本地) =================
try:
    # 优先尝试从 Streamlit Secrets 读取 (云端部署用)
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except:
    # 本地回退 (请填入你的真实信息)
    SUPABASE_URL = "https://vetupomjinhylqpxnrhn.supabase.co"
    SUPABASE_KEY = "sb_publishable_MpHqZeFn_U-lM19lpEBtMA_NR3Mx3mO"

TABLE_SENSORS = "sensor_measurements"
TABLE_RAIN = "weather_logs"
REGEX_PATTERN = re.compile(r"^([a-zA-Z0-9]+)(?:号)?([\u4e00-\u9fa5]+)\s+([\u4e00-\u9fa5]+)(?:[\(（](.+)[\)）])?(?:\.\d+)?$")
SCI_COLORS = ['#E64B35', '#4DBBD5', '#00A087', '#3C5488', '#F39B7F', '#8491B4', '#91D1C2', '#DC0000']

# ================= 2. 核心功能函数 =================
@st.cache_resource
def init_connection():
    if "你的_" in SUPABASE_URL:
        st.error("请配置数据库连接信息！")
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"数据库连接失败: {e}")
        return None

supabase = init_connection()

@st.cache_resource
def get_chinese_font():
    font_name = "SimHei.ttf"
    if not os.path.exists(font_name):
        try:
            url = "https://github.com/StellarCN/scp_zh/raw/master/fonts/SimHei.ttf"
            response = requests.get(url, timeout=5)
            with open(font_name, "wb") as f: f.write(response.content)
        except: pass
    try: return fm.FontProperties(fname=font_name)
    except: return None

zh_font = get_chinese_font()

# --- 数据获取与处理 ---
def optimize_dataframe(df, time_col='timestamp'):
    if len(df) < 5000: return df
    min_t, max_t = df[time_col].min(), df[time_col].max()
    days = (max_t - min_t).days
    rule = '1D' if days > 365 else '6H' if days > 90 else '1H' if days > 30 else '30T' if days > 7 else None
    if not rule: return df
    
    st.toast(f"数据量较大，已启用智能聚合 ({rule})", icon="⚡")
    df = df.set_index(time_col)
    return df.groupby(['sensor_id', 'variable_type', 'unit'])['value'].resample(rule).mean().reset_index()

def get_sensor_data(start_time, end_time):
    if not supabase: return pd.DataFrame()
    try:
        response = supabase.table(TABLE_SENSORS).select("timestamp, sensor_id, variable_type, value, unit") \
            .gte("timestamp", start_time.isoformat()).lte("timestamp", end_time.isoformat()) \
            .limit(200000).order("timestamp").execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            if df['timestamp'].dt.tz is not None: df['timestamp'] = df['timestamp'].dt.tz_localize(None)
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df = optimize_dataframe(df.dropna(subset=['timestamp', 'value']))
        return df
    except: return pd.DataFrame()

def get_rainfall_data(start_time, end_time):
    if not supabase: return pd.DataFrame()
    try:
        response = supabase.table(TABLE_RAIN).select("created_at, rain_intensity") \
            .gte("created_at", start_time.isoformat()).lte("created_at", end_time.isoformat()) \
            .limit(200000).order("created_at").execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            df = df.rename(columns={"created_at": "timestamp", "rain_intensity": "value"})
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            # 关键：去时区，确保与历史数据一致
            if df['timestamp'].dt.tz is not None: df['timestamp'] = df['timestamp'].dt.tz_localize(None)
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df = df.dropna(subset=['timestamp']).sort_values('timestamp')
        return df
    except: return pd.DataFrame()

# ================= 3. 页面逻辑 =================
st.set_page_config(page_title="SciPlot Cloud Pro", page_icon="🌧️", layout="wide")

if not supabase: st.stop()

# 侧边栏导航
page = st.sidebar.radio("功能导航", ["📈 科研绘图 (SciPlot)", "⚙️ 站点管理", "📂 数据上传"])

# --- 页面 1: 科研绘图 ---
if page == "📈 科研绘图 (SciPlot)":
    st.title("📊 SciPlot Cloud - 科研数据可视化")
    
    with st.sidebar:
        st.markdown("---")
        st.header("绘图控制")
        c1, c2 = st.columns(2)
        start_date = c1.date_input("开始", datetime.now() - timedelta(days=30))
        end_date = c2.date_input("结束", datetime.now())
        show_rainfall = st.checkbox("叠加降雨量", value=True)
        
        st.header("参数微调")
        ma_window = st.slider("平滑窗口", 1, 20, 1)
        spike_thresh = st.number_input("去噪阈值", 0.0, step=0.1)
        plot_mode = st.radio("分窗逻辑", ["按【号码】自动分窗", "按【物理量】自动分窗", "自定义选择"])
        
        if st.button("🔄 刷新数据", type="primary", use_container_width=True):
            st.cache_data.clear() # 清除缓存

    # 数据加载
    t_start = datetime.combine(start_date, datetime.min.time())
    t_end = datetime.combine(end_date, datetime.max.time())
    
    df_sensor = get_sensor_data(t_start, t_end)
    df_rain = get_rainfall_data(t_start, t_end) if show_rainfall else pd.DataFrame()
    
    if df_sensor.empty and df_rain.empty:
        st.warning("当前时间段无数据。请尝试调整日期范围 (历史数据可能在2024年)。")
    else:
        # 配置绘图任务
        plots_config = []
        if not df_sensor.empty:
            all_ids = sorted(df_sensor['sensor_id'].unique())
            all_vars = sorted(df_sensor['variable_type'].unique())
            
            if plot_mode == "按【号码】自动分窗":
                t_ids = st.multiselect("选择号码", all_ids, default=all_ids)
                t_vars = st.multiselect("选择物理量", all_vars, default=all_vars)
                for sid in t_ids: plots_config.append({"title":f"{sid} 数据总览","ids":[sid],"vars":t_vars})
            elif plot_mode == "按【物理量】自动分窗":
                t_vars = st.multiselect("选择物理量", all_vars, default=all_vars)
                t_ids = st.multiselect("选择号码", all_ids, default=all_ids)
                for v in t_vars: plots_config.append({"title":f"{v} 对比分析","ids":t_ids,"vars":[v]})
            else: # 自定义
                st.info("请在代码中开启自定义模式 UI") 

        elif not df_rain.empty:
            plots_config.append({"title":"降雨量趋势图", "ids":[], "vars":[]})

        # 执行绘图
        if plots_config:
            cols_per_row = 1 if len(plots_config) == 1 else 2
            for i in range(0, len(plots_config), cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < len(plots_config):
                        config = plots_config[i + j]
                        with cols[j]:
                            fig, ax1 = plt.subplots(figsize=(10, 6))
                            has_data = False
                            
                            # 左轴：传感器
                            if not df_sensor.empty:
                                for idx, (sid, vtype) in enumerate([(s, v) for s in config['ids'] for v in config['vars']]):
                                    sub = df_sensor[(df_sensor['sensor_id']==sid)&(df_sensor['variable_type']==vtype)].sort_values('timestamp')
                                    if not sub.empty:
                                        has_data = True
                                        y = sub['value'].rolling(ma_window, min_periods=1, center=True).mean() if ma_window > 1 else sub['value']
                                        unit = sub['unit'].iloc[0] if pd.notna(sub['unit'].iloc[0]) else ""
                                        ax1.plot(sub['timestamp'], y, label=f"{sid}-{vtype}", color=SCI_COLORS[idx % len(SCI_COLORS)], linewidth=1.5, alpha=0.9)
                                        ax1.set_ylabel(f"数值 ({unit})", fontproperties=zh_font, fontsize=12)

                            # 右轴：降雨 (折线图)
                            ax2 = ax1.twinx()
                            if show_rainfall and not df_rain.empty:
                                ax2.plot(df_rain['timestamp'], df_rain['value'], color='#3C5488', linestyle='-', linewidth=1.5, alpha=0.8, label='降雨量 (mm)')
                                ax2.set_ylabel("降雨量 (mm)", fontproperties=zh_font, fontsize=12)
                                ax2.set_ylim(bottom=0)
                            else:
                                ax2.set_yticks([])

                            # 样式
                            ax1.set_xlabel("时间", fontproperties=zh_font, fontsize=12)
                            ax1.set_title(config['title'], fontproperties=zh_font, fontsize=14, fontweight='bold')
                            ax1.xaxis.set_major_locator(ticker.MaxNLocator(nbins=6))
                            ax1.grid(True, linestyle=':', alpha=0.3)
                            
                            # 图例
                            lines1, labels1 = ax1.get_legend_handles_labels()
                            lines2, labels2 = ax2.get_legend_handles_labels()
                            leg = ax1.legend(lines1 + lines2, labels1 + labels2, loc='best', frameon=False)
                            if zh_font: 
                                for text in leg.get_texts(): text.set_fontproperties(zh_font)
                            
                            st.pyplot(fig)

# --- 页面 2: 站点管理 (保留你原来的功能) ---
elif page == "⚙️ 站点管理":
    st.title("⚙️ 监测站点配置")
    st.info("在这里添加站点，后台机器人会自动开始监测。")
    
    with st.form("add_station"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("站点名称", "宁海试验点")
        lat = c2.number_input("纬度", value=29.531, format="%.4f")
        lon = c3.number_input("经度", value=121.432, format="%.4f")
        if st.form_submit_button("添加站点"):
            try:
                supabase.table("monitor_config").insert({"name": name, "lat": lat, "lon": lon, "is_active": True}).execute()
                st.success(f"站点 {name} 添加成功！")
            except Exception as e:
                st.error(f"添加失败: {e}")
                
    # 显示现有站点
    try:
        data = supabase.table("monitor_config").select("*").execute().data
        if data: st.dataframe(pd.DataFrame(data))
    except: pass

# --- 页面 3: 数据上传 ---
elif page == "📂 数据上传":
    st.title("📂 补充历史数据")
    # (此处省略 parse_excel_file 和 upload_to_supabase 的调用代码，保持之前一致即可)
    st.info("请直接使用之前的上传功能。")
