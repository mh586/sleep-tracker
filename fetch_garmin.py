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
except Exception as e:
    print(f"Failed to log into Garmin Connect endpoint framework: {e}")
    exit(1)

local_time = datetime.now(timezone.utc) + timedelta(hours=2)
todayStr = local_time.strftime("%Y-%m-%d")
print(f"Executing Deep Search Telemetry Sync for Local Date: {todayStr}")

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

# A deep search function to scan nested dictionaries and lists for a specific key
def find_key_deep(data, target_key):
    if isinstance(data, dict):
        if target_key in data:
            return data[target_key]
        for key, value in data.items():
            result = find_key_deep(value, target_key)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = find_key_deep(item, target_key)
            if result is not None:
                return result
    return None

try:
    sleep_data = garmin.get_sleep_data(todayStr) or {}
    daily_sleep = sleep_data.get("dailySleepDTO", {})
    
    # 1. Base Durations (Already working)
    if daily_sleep:
        m["g_total"] = format_seconds(daily_sleep.get("sleepTimeSeconds", 0))
        m["g_deep"] = format_seconds(daily_sleep.get("deepSleepSeconds", 0))
        m["g_rem"] = format_seconds(daily_sleep.get("remSleepSeconds", 0))
        m["g_light"] = format_seconds(daily_sleep.get("lightSleepSeconds", 0))
        m["g_awake"] = format_seconds(daily_sleep.get("awakeSleepSeconds", 0))
        if daily_sleep.get("averageRespirationValue"):
            m["g_resp"] = f"{round(daily_sleep.get('averageRespirationValue'), 1)} brpm"

    # 2. DYNAMICALLY HUNT MISSING METRICS
    
    # Sleep Score Hunt
    score_hunt = find_key_deep(sleep_data, "sleepScore") or find_key_deep(sleep_data, "value")
    if score_hunt and str(score_hunt).isdigit():
        m["g_score"] = str(score_hunt)
    
    # Overnight Avg HRV Hunt
    hrv_hunt = find_key_deep(sleep_data, "avgOvernightHrv") or find_key_deep(sleep_data, "lastNightAvg") or find_key_deep(sleep_data, "averageHRV")
    if hrv_hunt:
        m["g_hrv"] = f"{int(float(hrv_hunt))} ms"

    # Restlessness Count Hunt
    restless_hunt = find_key_deep(sleep_data, "restlessMomentsCount") or find_key_deep(sleep_data, "restlessSleepMovementsCount")
    if restless_hunt is not None:
        m["g_restless"] = f"{int(restless_hunt)} mvmt"

    # Sleep Stress Hunt
    stress_hunt = find_key_deep(sleep_data, "avgSleepStress") or find_key_deep(sleep_data, "averageStressLevel")
    if stress_hunt:
        m["g_stress"] = f"{int(float(stress_hunt))}/100"

    # Average Sleeping Heart Rate Hunt
    ashr_hunt = find_key_deep(sleep_data, "avgHeartRate") or find_key_deep(sleep_data, "averageSleepHeartRate")
    if ashr_hunt:
        m["g_ashr"] = f"{int(float(ashr_hunt))} bpm"

    # Resting Heart Rate (Baseline)
    rhr_hunt = find_key_deep(sleep_data, "restingHeartRate") or find_key_deep(garmin.get_user_summary(todayStr), "restingHeartRate")
    if rhr_hunt:
        m["g_rhr"] = f"{int(rhr_hunt)} bpm"

except Exception as e:
    print(f"Error during deep crawling sequence: {e}")

# --- 3. WRITE TO LEDGER ---
db_filename = "sleep_database.json"
if os.path.exists(db_filename):
    with open(db_filename, "r") as f:
        try: db = json.load(f)
        except: db = {}
else:
    db = {}

key = f"sleep_data_{todayStr}"

# Ensure the key for today exists as an object so we don't crash
if key not in db:
    db[key] = {}

# Merging Strategy: Only update a metric if the new fetch has actual data
for k, v in m.items():
    if v != "--":
        db[key][k] = v

with open(db_filename, "w") as f:
    json.dump(db, f, indent=4)

print(f"Deep Search Sync Completed for {key}: {db[key]}")
