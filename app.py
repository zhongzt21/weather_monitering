import streamlit as st
from supabase import create_client
import pandas as pd
import datetime

st.set_page_config(page_title="宁海降雨监测系统 Pro", page_icon="🌧️", layout="wide")

# --- 连接数据库 ---
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("数据库连接失败，请检查 Secrets 配置")
    st.stop()

# --- 侧边栏导航 ---
st.sidebar.title("🌧️ 导航")
page = st.sidebar.radio("选择功能", ["📊 数据查询", "⚙️ 站点管理"])

# =======================
# 功能 1: 站点管理 (添加/删除监测点)
# =======================
if page == "⚙️ 站点管理":
    st.title("⚙️ 监测站点配置")
    st.info("在这里添加的站点，后台机器人会在下个整点自动开始监测。")

    # 1. 添加新站点表单
    with st.expander("➕ 添加新监测点", expanded=True):
        with st.form("add_station_form"):
            c1, c2, c3 = st.columns(3)
            new_name = c1.text_input("站点名称", placeholder="例如：宁海县城")
            new_lon = c2.text_input("经度 (Longitude)", value="121.43")
            new_lat = c3.text_input("纬度 (Latitude)", value="29.29")
            
            submitted = st.form_submit_button("保存并开始监测")
            
            if submitted:
                if new_name and new_lon and new_lat:
                    try:
                        data = {
                            "name": new_name,
                            "lon": float(new_lon),
                            "lat": float(new_lat),
                            "is_active": True
                        }
                        supabase.table("monitor_config").insert(data).execute()
                        st.success(f"✅ 站点 [{new_name}] 已添加！机器人将在下个整点开始抓取数据。")
                        st.rerun() # 刷新页面
                    except Exception as e:
                        st.error(f"添加失败: {e}")
                else:
                    st.warning("请填写完整信息")

    # 2. 查看现有站点
    st.subheader("📋 正在运行的监测点")
    
    # 获取配置表数据
    config_data = supabase.table("monitor_config").select("*").order("created_at").execute()
    
    if config_data.data:
        df_config = pd.DataFrame(config_data.data)
        
        # 展示表格
        st.dataframe(
            df_config[['name', 'lon', 'lat', 'created_at', 'is_active']], 
            use_container_width=True,
            column_config={
                "created_at": "创建时间",
                "name": "站点名称",
                "is_active": "状态"
            }
        )
        
        # 删除功能
        st.write("🗑️ **删除站点**")
        del_list = [f"{row['id']} - {row['name']}" for row in config_data.data]
        selected_del = st.selectbox("选择要删除的站点", ["请选择..."] + del_list)
        
        if st.button("确认删除", type="primary"):
            if selected_del != "请选择...":
                del_id = selected_del.split(" - ")[0]
                supabase.table("monitor_config").delete().eq("id", del_id).execute()
                st.success("删除成功！")
                st.rerun()
    else:
        st.write("暂无监测点，请在上方添加。")

# =======================
# 功能 2: 数据查询 (查看历史记录)
# =======================
elif page == "📊 数据查询":
    st.title("📊 降雨历史数据分析")
    
    # 1. 获取所有站点供筛选
    stations_resp = supabase.table("monitor_config").select("name").execute()
    station_names = [item['name'] for item in stations_resp.data] if stations_resp.data else []
    
    if not station_names:
        st.warning("请先去【站点管理】添加监测点！")
        st.stop()

    # 2. 查询过滤器
    col1, col2, col3 = st.columns(3)
    selected_station = col1.selectbox("选择监测点", ["全部"] + station_names)
    start_date = col2.date_input("开始日期", datetime.date.today() - datetime.timedelta(days=7))
    end_date = col3.date_input("结束日期", datetime.date.today() + datetime.timedelta(days=1))

    # 3. 按钮触发查询
    if st.button("🔎 查询数据库"):
        # 构建查询
        query = supabase.table("weather_logs").select("*") \
            .gte("created_at", start_date.strftime('%Y-%m-%d 00:00:00')) \
            .lte("created_at", end_date.strftime('%Y-%m-%d 23:59:59'))
            
        if selected_station != "全部":
            query = query.eq("location_name", selected_station)
            
        # 按时间倒序
        query = query.order("created_at", desc=True)
        response = query.execute()
        
        if response.data:
            df = pd.DataFrame(response.data)
            # 时区转换
            df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert('Asia/Shanghai')
            
            # 统计指标
            total_rain = df['rain_intensity'].sum()
            max_rain = df['rain_intensity'].max()
            
            k1, k2 = st.columns(2)
            k1.metric("累计记录数", f"{len(df)} 条")
            k2.metric("期间最大雨强", f"{max_rain} mm/h")
            
            # 图表 - 只有选了单个站点才画图，不然太乱
            if selected_station != "全部":
                st.line_chart(df, x='created_at', y='rain_intensity')
            else:
                st.info("选择单个站点可查看降雨趋势图")

            # 导出表格
            st.dataframe(df[['created_at', 'location_name', 'rain_intensity', 'temperature', 'description']], use_container_width=True)
            
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下载数据包", csv, "history_data.csv", "text/csv")
            
        else:
            st.warning("📭 查无数据。如果是刚添加的站点，请等待下一个整点。")
