import requests
from supabase import create_client
import os
import datetime
import time

# ================= 配置区域 =================
# 建议在本地测试时直接填入，或者确保环境变量已设置
# 如果是在 Streamlit Cloud 运行，请保留 os.environ 或 st.secrets
SUPABASE_URL = os.environ.get("SUPABASE_URL") or "你的_SUPABASE_URL"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or "你的_SUPABASE_KEY"
CAIYUN_TOKEN = os.environ.get("CAIYUN_TOKEN") or "你的_彩云_TOKEN"
# ===========================================

def save_weather():
    print(f"[{datetime.datetime.now()}] 🤖 机器人启动...")
    
    if "你的_" in SUPABASE_URL:
        print("❌ 错误: 请配置 Supabase URL 和 Key")
        return

    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return
    
    # 1. 获取活跃监测点
    print("📋 正在获取监测站点列表...")
    try:
        config_resp = supabase.table("monitor_config").select("*").eq("is_active", True).execute()
        monitor_points = config_resp.data
    except Exception as e:
        print(f"❌ 读取配置表失败 (monitor_config): {e}")
        return

    if not monitor_points:
        print("⚠️ 数据库 monitor_config 表为空或无活跃站点，机器人休息中...")
        return

    print(f"✅ 获取到 {len(monitor_points)} 个站点，开始作业。")

    # 2. 遍历执行
    for point in monitor_points:
        # 彩云 API
        url = f"https://api.caiyunapp.com/v2.6/{CAIYUN_TOKEN}/{point['lon']},{point['lat']}/realtime"
        
        try:
            print(f"☁️ 正在请求彩云天气: {point['name']}...")
            resp = requests.get(url, timeout=15).json()
            
            if resp.get('status') == 'ok':
                result = resp['result']['realtime']
                
                # 【核心修改】时间统一：使用 UTC 且去除时区信息，与历史数据保持一致
                # 这样 matplotlib 画图时就不会因为时区问题打架了
                current_time = datetime.datetime.utcnow().replace(microsecond=0)
                
                log_data = {
                    "created_at": current_time.isoformat(),
                    "location_name": point['name'], 
                    "lat": point['lat'],
                    "lon": point['lon'],
                    "rain_intensity": result['precipitation']['local']['intensity'],
                    "temperature": result['temperature'],
                    "description": result['skycon']
                }
                
                # 执行写入
                supabase.table("weather_logs").insert(log_data).execute()
                print(f"✅ [写入成功] {point['name']} | 时间: {current_time} | 雨强: {log_data['rain_intensity']}")
            else:
                print(f"❌ API 错误: {resp.get('status')}")
                
        except Exception as e:
            print(f"❌ 处理站点 {point['name']} 时出错: {e}")

if __name__ == "__main__":
    # 为了测试，立即运行一次
    save_weather()
