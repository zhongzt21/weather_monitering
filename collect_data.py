import requests
from supabase import create_client
import os
import datetime

# --- 配置 ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
CAIYUN_TOKEN = os.environ.get("CAIYUN_TOKEN")

def save_weather():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Error: Secrets 未配置")
        return

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # 1. 【核心变化】先去数据库查：现在有哪些活跃的监测点？
    print("正在从 monitor_config 表获取监测列表...")
    try:
        config_resp = supabase.table("monitor_config").select("*").eq("is_active", True).execute()
        monitor_points = config_resp.data
    except Exception as e:
        print(f"读取配置失败: {e}")
        return

    if not monitor_points:
        print("数据库里没有监测点，机器人休息中...")
        return

    print(f"获取到 {len(monitor_points)} 个监测点，开始执行任务...")

    # 2. 遍历这些点，逐个抓取
    for point in monitor_points:
        # 彩云 API
        url = f"https://api.caiyunapp.com/v2.6/{CAIYUN_TOKEN}/{point['lon']},{point['lat']}/realtime"
        
        try:
            resp = requests.get(url, timeout=15).json()
            
            if resp.get('status') == 'ok':
                result = resp['result']['realtime']
                
                # 准备写入 weather_logs 表的数据
                log_data = {
                    "created_at": datetime.datetime.now().isoformat(),
                    "location_name": point['name'], # 使用配置表里的名字
                    "lat": point['lat'],
                    "lon": point['lon'],
                    "rain_intensity": result['precipitation']['local']['intensity'],
                    "temperature": result['temperature'],
                    "description": result['skycon']
                }
                
                supabase.table("weather_logs").insert(log_data).execute()
                print(f"✅ [成功] {point['name']} - 雨强: {log_data['rain_intensity']}")
            else:
                print(f"❌ [API错误] {point['name']}: {resp}")
                
        except Exception as e:
            print(f"❌ [异常] {point['name']}: {str(e)}")

if __name__ == "__main__":
    save_weather()
