import os
import json
from datetime import datetime, timedelta, timezone
from garminconnect import Garmin

EMAIL = os.environ.get("GARMIN_EMAIL")
PASSWORD = os.environ.get("GARMIN_PASSWORD")

if not EMAIL or not PASSWORD:
    print("Missing execution secret variables.")
    exit(1)

try:
    garmin = Garmin(EMAIL, PASSWORD)
    garmin.login()
    print("Login successful.")
except Exception as e:
    print(f"Failed to log into Garmin Connect endpoint framework: {e}")
    exit(1)

local_time = datetime.now(timezone.utc) + timedelta(hours=2)
todayStr = local_time.strftime("%Y-%m-%d")
print(f"Querying date: {todayStr}")

m = {
    "g_score": "--", "g_hrv": "--", "g_total": "--", "g_deep": "--", 
    "g_rem": "--", "g_light": "--", "g_awake": "--", "g_restless": "--", 
    "g_stress": "--", "g_rhr": "--", "g_ashr": "--", "g_resp": "--"
}

def format_seconds(sec):
    if not sec or sec <= 0: return "--"
    h = sec // 3600
    m = (sec % 3600) // 60
    return f"{int(h)}h {int(m)}m" if h > 0 else f"{int(m)}m"

# --- DIAGNOSTIC PARSING ---
try:
    sleep_data = garmin.get_sleep_data(todayStr)
    print(f"Raw sleep_data keys found: {list(sleep_data.keys()) if sleep_data else 'None/Empty'}")
    
    if sleep_data and "dailySleepDTO" in sleep_data:
        daily_sleep = sleep_data["dailySleepDTO"]
        print(f"dailySleepDTO keys: {list(daily_sleep.keys())}")
        
        if daily_sleep.get("sleepScore"): m["g_score"] = str(daily_sleep.get("sleepScore"))
        m["g_total"] = format_seconds(daily_sleep.get("sleepTimeSeconds", 0))
        m["g_deep"] = format_seconds(daily_sleep.get("deepSleepSeconds", 0))
        m["g_rem"] = format_seconds(daily_sleep.get("remSleepSeconds", 0))
        m["g_light"] = format_seconds(daily_sleep.get("lightSleepSeconds", 0))
        m["g_awake"] = format_seconds(daily_sleep.get("awakeSleepSeconds", 0))
        
        if daily_sleep.get("averageSleepHeartRate"):
            m["g_ashr"] = f"{int(daily_sleep.get('averageSleepHeartRate'))} bpm"
        if daily_sleep.get("averageRespirationValue"):
            m["g_resp"] = f"{round(daily_sleep.get('averageRespirationValue'), 1)} brpm"
        if daily_sleep.get("restlessSleepMovementsCount") is not None:
            m["g_restless"] = f"{daily_sleep.get('restlessSleepMovementsCount')} mvmt"
except Exception as e:
    print(f"Sleep diagnostic crash: {e}")

try:
    stats = garmin.get_user_summary(todayStr) or {}
    print(f"User summary keys found: {list(stats.keys()) if stats else 'Empty'}")
    if stats.get("restingHeartRate"):
        m["g_rhr"] = f"{int(stats.get('restingHeartRate'))} bpm"
except Exception as e:
    print(f"Summary diagnostic crash: {e}")

try:
    hrv_data = garmin.get_hrv_data(todayStr) or {}
    print(f"HRV data keys found: {list(hrv_data.keys()) if hrv_data else 'Empty'}")
    hrv_summary = hrv_data.get("hrvSummaryDTO", {})
    if hrv_summary and hrv_summary.get("lastNightAvg"):
        m["g_hrv"] = f"{int(hrv_summary.get('lastNightAvg'))} ms"
except Exception as e:
    print(f"HRV diagnostic crash: {e}")

# --- SAVE TO DATABASE ---
db_filename = "sleep_database.json"
if os.path.exists(db_filename):
    with open(db_filename, "r") as f:
        try: db = json.load(f)
        except: db = {}
else:
    db = {}

key = f"sleep_data_{todayStr}"
db[key] = {k: v for k, v in m.items() if v != "--"}
print(f"Writing block to JSON for {key}: {db[key]}")

with open(db_filename, "w") as f:
    json.dump(db, f, indent=4)
