import requests
from supabase import create_client
import os
import datetime

# --- 配置 ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
CAIYUN_TOKEN = os.environ.get("CAIYUN_TOKEN")

def save_weather():
    print(f"[{datetime.datetime.now()}] 开始执行任务...")
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Error: Secrets 未配置")
        return

    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return
    
    # 1. 获取活跃监测点
    try:
        config_resp = supabase.table("monitor_config").select("*").eq("is_active", True).execute()
        monitor_points = config_resp.data
    except Exception as e:
        print(f"❌ 读取配置表失败 (请检查 monitor_config 表是否存在以及 RLS 是否关闭): {e}")
        return

    if not monitor_points:
        print("⚠️ 数据库里没有活跃的监测点。")
        return

    print(f"✅ 获取到 {len(monitor_points)} 个监测点，开始抓取...")

    # 2. 遍历抓取
    for point in monitor_points:
        url = f"https://api.caiyunapp.com/v2.6/{CAIYUN_TOKEN}/{point['lon']},{point['lat']}/realtime"
        
        try:
            resp = requests.get(url, timeout=15).json()
            
            if resp.get('status') == 'ok':
                result = resp['result']['realtime']
                
                # 强制使用 UTC 时间，避免时区混乱
                current_time_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

                log_data = {
                    "created_at": current_time_utc,
                    "location_name": point['name'],
                    "lat": point['lat'],
                    "lon": point['lon'],
                    "rain_intensity": result['precipitation']['local']['intensity'],
                    "temperature": result['temperature'],
                    "description": result['skycon']
                }
                
                # 写入数据库
                data = supabase.table("weather_logs").insert(log_data).execute()
                print(f"✅ [写入成功] {point['name']} | 雨强: {log_data['rain_intensity']}")
                
            else:
                print(f"❌ [API返回错误] {point['name']}: {resp}")
                
        except Exception as e:
            # 这里会打印具体的数据库写入错误
            print(f"❌ [写入/网络异常] {point['name']}: {str(e)}")

if __name__ == "__main__":
    save_weather()
