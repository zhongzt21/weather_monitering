import streamlit as st
from supabase import create_client, Client
import pandas as pd
import datetime

# --- 1. 配置与连接 ---
st.set_page_config(page_title="宁海降雨历史数据库", page_icon="🌧️", layout="wide")

# ⚠️ 注意：实际部署时，建议将这些 Key 放入 Streamlit Secrets 管理，不要直接暴露
# 这里为了演示方便，请填入你 Supabase 的 URL 和 Key
SUPABASE_URL = "https://vetupomjinhylqpxnrhn.supabase.co"
SUPABASE_KEY = "sb_publishable_MpHqZeFn_U-lM19lpEBtMA_NR3Mx3mO"

@st.cache_resource
def init_connection():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except:
        return None

supabase = init_connection()

# --- 2. 侧边栏：查询条件 ---
st.sidebar.header("🔍 数据查询面板")

# 预设监测点逻辑
PRESETS = {
    "默认": {"name": "全部站点", "lat": None, "lon": None},
    "宁海中心": {"name": "宁海中心", "lat": 29.29, "lon": 121.43},
    # 你可以在这里添加更多固定监测点
}

selected_preset = st.sidebar.selectbox("选择监测点", list(PRESETS.keys()))

# 时间范围选择
today = datetime.date.today()
start_date = st.sidebar.date_input("开始日期", today - datetime.timedelta(days=7))
end_date = st.sidebar.date_input("结束日期", today)

# --- 3. 核心功能：从数据库拉取数据 ---
def get_data_from_db(start, end, location_filter):
    if not supabase:
        st.error("数据库连接失败，请检查 URL 和 Key")
        return pd.DataFrame()

    # 构建查询
    query = supabase.table("weather_logs").select("*")
    
    # 时间过滤 (加一天由 datetime 转为 string 匹配数据库格式)
    query = query.gte("created_at", start.strftime('%Y-%m-%d 00:00:00'))
    query = query.lte("created_at", end.strftime('%Y-%m-%d 23:59:59'))
    
    # 地点过滤
    if location_filter != "全部站点":
        query = query.eq("location_name", location_filter)
        
    # 执行查询
    response = query.execute()
    
    # 转换为 DataFrame
    data = response.data
    if data:
        df = pd.DataFrame(data)
        # 转换时间格式为本地时间 (默认是UTC)
        df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert('Asia/Shanghai')
        return df
    return pd.DataFrame()

# --- 4. 主界面展示 ---
st.title("🌧️ 宁海降雨数据历史查询")
st.markdown(f"当前查询范围: `{start_date}` 至 `{end_date}` | 站点: `{selected_preset}`")

if st.button("🔎 查询数据库", type="primary"):
    with st.spinner("正在从云端提取数据..."):
        df_result = get_data_from_db(start_date, end_date, PRESETS[selected_preset]['name'])
        
        if not df_result.empty:
            # 数据清洗与展示
            display_df = df_result[['created_at', 'location_name', 'rain_intensity', 'temperature', 'description', 'lat', 'lon']].copy()
            display_df.columns = ['记录时间', '监测点', '降雨强度(mm/h)', '温度(°C)', '天气', '纬度', '经度']
            
            # 指标概览
            total_rain = display_df['降雨强度(mm/h)'].sum()
            max_rain = display_df['降雨强度(mm/h)'].max()
            avg_temp = display_df['温度(°C)'].mean()
            
            k1, k2, k3 = st.columns(3)
            k1.metric("区间累计记录数", f"{len(df_result)} 条")
            k2.metric("区间最大降雨强度", f"{max_rain} mm/h")
            k3.metric("区间平均温度", f"{avg_temp:.1f} °C")
            
            # 图表
            st.line_chart(display_df, x='记录时间', y='降雨强度(mm/h)')
            
            # 数据表
            st.dataframe(display_df, use_container_width=True)
            
            # 下载按钮
            csv = display_df.to_csv(index=False).encode('utf-8-sig')
            filename = f"雨量数据_{selected_preset}_{start_date}_{end_date}.csv"
            st.download_button(
                label="📥 下载 Excel/CSV 数据包",
                data=csv,
                file_name=filename,
                mime='text/csv'
            )
        else:
            st.warning("⚠️ 该时间段内数据库没有记录。请确保后台自动记录脚本正在运行。")