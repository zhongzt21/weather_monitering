import requests
from supabase import create_client
import os

# 这些敏感信息将从 GitHub 的环境变量中读取，不要直接写在代码里上传
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
CAIYUN_TOKEN = os.environ.get("CAIYUN_TOKEN")

# 定义你要自动监测的站点列表
MONITOR_POINTS = [
    {"name": "宁海中心", "lat": 29.29, "lon": 121.43},
    # 你可以在这里增加更多点，比如 {"name": "某水库", "lat": 29.35, "lon": 121.50},
]

def save_weather():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    for point in MONITOR_POINTS:
        url = f"https://api.caiyunapp.com/v2.6/{CAIYUN_TOKEN}/{point['lon']},{point['lat']}/realtime"
        try:
            resp = requests.get(url).json()
            if resp['status'] == 'ok':
                result = resp['result']['realtime']
                
                data = {
                    "location_name": point['name'],
                    "lat": point['lat'],
                    "lon": point['lon'],
                    "rain_intensity": result['precipitation']['local']['intensity'],
                    "temperature": result['temperature'],
                    "description": result['skycon'] # 你可以加映射字典转中文，这里简化
                }
                
                supabase.table("weather_logs").insert(data).execute()
                print(f"Success: {point['name']}")
            else:
                print(f"Failed API: {point['name']}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    save_weather()