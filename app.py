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
page = st.sidebar.radio("选择功能", ["📊 数据查询", "⚙️ 站点管理", "🛠️ 系统诊断"])

# =======================
# 功能 1: 站点管理
# =======================
if page == "⚙️ 站点管理":
    st.title("⚙️ 监测站点配置")
    
    with st.expander("➕ 添加新监测点", expanded=False):
        with st.form("add_station_form"):
            c1, c2, c3 = st.columns(3)
            new_name = c1.text_input("站点名称")
            new_lon = c2.text_input("经度", value="121.43")
            new_lat = c3.text_input("纬度", value="29.29")
            if st.form_submit_button("保存"):
                try:
                    data = {"name": new_name, "lon": float(new_lon), "lat": float(new_lat), "is_active": True}
                    supabase.table("monitor_config").insert(data).execute()
                    st.success(f"站点 {new_name} 添加成功")
                    st.rerun()
                except Exception as e:
                    st.error(f"添加失败: {e}")

    # 获取现有站点
    try:
        config_data = supabase.table("monitor_config").select("*").order("created_at").execute()
        if config_data.data:
            df = pd.DataFrame(config_data.data)
            st.dataframe(df[['name', 'lon', 'lat', 'is_active']], use_container_width=True)
            
            # 删除逻辑
            del_list = [f"{row['id']} - {row['name']}" for row in config_data.data]
            to_del = st.selectbox("删除站点", ["请选择..."] + del_list)
            if st.button("确认删除") and to_del != "请选择...":
                del_id = to_del.split(" - ")[0]
                supabase.table("monitor_config").delete().eq("id", del_id).execute()
                st.success("删除成功")
                st.rerun()
    except Exception as e:
        st.error(f"读取配置表失败，请检查数据库: {e}")

# =======================
# 功能 2: 数据查询 (增强版)
# =======================
elif page == "📊 数据查询":
    st.title("📊 降雨历史数据分析")
    
    # 1. 站点选择
    try:
        stations_resp = supabase.table("monitor_config").select("name").execute()
        station_names = [item['name'] for item in stations_resp.data] if stations_resp.data else []
    except:
        station_names = []
    
    col1, col2, col3 = st.columns(3)
    selected_station = col1.selectbox("选择监测点", ["全部"] + station_names)
    start_date = col2.date_input("开始日期", datetime.date.today() - datetime.timedelta(days=1))
    end_date = col3.date_input("结束日期", datetime.date.today() + datetime.timedelta(days=1))

    if st.button("🔎 查询数据库", type="primary"):
        with st.spinner("正在检索..."):
            try:
                # 基础查询
                query = supabase.table("weather_logs").select("*")
                
                # 时间过滤 (转为 UTC 字符串以匹配数据库)
                # 注意：这里直接用字符串比较，要求数据库里的 created_at 是标准格式
                query = query.gte("created_at", start_date.strftime('%Y-%m-%d 00:00:00'))
                query = query.lte("created_at", end_date.strftime('%Y-%m-%d 23:59:59'))
                
                if selected_station != "全部":
                    query = query.eq("location_name", selected_station)
                
                response = query.order("created_at", desc=True).limit(2000).execute() # 限制2000条防止卡死
                
                if response.data:
                    df = pd.DataFrame(response.data)
                    
                    # --- 关键修复：智能时间转换 ---
                    # 尝试将 created_at 转换为 datetime 对象
                    df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
                    
                    # 尝试转换时区，如果已经是 timezone-aware 的则转换，否则本地化
                    try:
                        if df['created_at'].dt.tz is not None:
                            df['created_at'] = df['created_at'].dt.tz_convert('Asia/Shanghai')
                        else:
                            df['created_at'] = df['created_at'].dt.tz_localize('UTC').dt.tz_convert('Asia/Shanghai')
                    except:
                        pass # 如果转换失败，就保持原样
                    
                    # 展示数据
                    k1, k2 = st.columns(2)
                    k1.metric("记录数", len(df))
                    k2.metric("最大雨强", f"{df['rain_intensity'].max()} mm/h")
                    
                    if selected_station != "全部":
                        st.line_chart(df, x='created_at', y='rain_intensity')
                    
                    st.dataframe(df, use_container_width=True)
                else:
                    st.warning("📭 没有查到数据。可能是时间范围不对，或者数据库里真的没数据。")
                    
            except Exception as e:
                st.error(f"查询出错: {e}")

# =======================
# 功能 3: 系统诊断 (新增)
# =======================
elif page == "🛠️ 系统诊断":
    st.title("🛠️ 数据库结构与写入测试")
    st.markdown("如果数据不显示或无法写入，请查看这里。")
    
    st.subheader("1. 数据库表结构检查")
    if st.button("查看 weather_logs 表的前5条原始数据"):
        try:
            # 不带任何过滤条件，直接查最新5条
            raw_data = supabase.table("weather_logs").select("*").limit(5).order("created_at", desc=True).execute()
            if raw_data.data:
                st.write("✅ 成功读到数据！这是数据库里真实的列名和格式：")
                st.json(raw_data.data[0]) # 只展示第一条的详细JSON
                st.dataframe(pd.DataFrame(raw_data.data))
            else:
                st.warning("⚠️ 表是空的，或者权限被拒绝 (RLS)。")
        except Exception as e:
            st.error(f"❌ 读取失败: {e}")
            st.info("提示：如果报错信息包含 'RLS'，请去 Supabase 关闭 RLS。")

    st.subheader("2. 写入测试")
    if st.button("尝试写入一条测试数据"):
        try:
            test_data = {
                "location_name": "DEBUG_TEST",
                "lat": 0, "lon": 0, "rain_intensity": 0, "temperature": 0,
                "description": "test",
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
            supabase.table("weather_logs").insert(test_data).execute()
            st.success("✅ 写入成功！数据库写入权限正常。")
        except Exception as e:
            st.error(f"❌ 写入失败: {e}")
            st.write("如果是 'Column not found'，请检查你导入历史数据时是否改了列名。")


