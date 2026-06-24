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

# Keep your local timezone calculation matching your day layout
local_time = datetime.now(timezone.utc) + timedelta(hours=2)
todayStr = local_time.strftime("%Y-%m-%d")
print(f"Executing Final Precise Sync for Local Date: {todayStr}")

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

# --- 1. SLEEP DATA & STAGES ---
try:
    sleep_data = garmin.get_sleep_data(todayStr) or {}
    daily_sleep = sleep_data.get("dailySleepDTO", {})
    
    if daily_sleep:
        # Extract Nested Sleep Score
        scores_obj = daily_sleep.get("sleepScores", {})
        if scores_obj and scores_obj.get("overall", {}).get("value"):
            m["g_score"] = str(scores_obj["overall"]["value"])
        
        # Durations
        m["g_total"] = format_seconds(daily_sleep.get("sleepTimeSeconds", 0))
        m["g_deep"] = format_seconds(daily_sleep.get("deepSleepSeconds", 0))
        m["g_rem"] = format_seconds(daily_sleep.get("remSleepSeconds", 0))
        m["g_light"] = format_seconds(daily_sleep.get("lightSleepSeconds", 0))
        m["g_awake"] = format_seconds(daily_sleep.get("awakeSleepSeconds", 0))
        
        # Heart Rate & Respiration during sleep
        if daily_sleep.get("avgHeartRate"):
            m["g_ashr"] = f"{int(daily_sleep.get('avgHeartRate'))} bpm"
        if daily_sleep.get("averageRespirationValue"):
            m["g_resp"] = f"{round(daily_sleep.get('averageRespirationValue'), 1)} brpm"
            
    # Restlessness / Movement counts
    if daily_sleep.get("restlessSleepMovementsCount") is not None:
        m["g_restless"] = f"{daily_sleep.get('restlessSleepMovementsCount')} mvmt"
    elif sleep_data.get("restlessMomentsCount") is not None:
        m["g_restless"] = f"{sleep_data.get('restlessMomentsCount')} mvmt"

except Exception as e:
    print(f"Error parsing sleep structures: {e}")

# --- 2. USER SUMMARY (RHR & STRESS) ---
try:
    stats = garmin.get_user_summary(todayStr) or {}
    if stats.get("restingHeartRate"):
        m["g_rhr"] = f"{int(stats.get('restingHeartRate'))} bpm"
    if stats.get("averageStressLevel"):
        m["g_stress"] = f"{int(stats.get('averageStressLevel'))}/100"
except Exception as e:
    print(f"Error parsing user summary: {e}")

# --- 3. OVERNIGHT HRV ---
try:
    hrv_data = garmin.get_hrv_data(todayStr) or {}
    hrv_summary = hrv_data.get("hrvSummary", {})
    if hrv_summary and hrv_summary.get("lastNightAvg"):
        m["g_hrv"] = f"{int(hrv_summary.get('lastNightAvg'))} ms"
except Exception as e:
    print(f"Error parsing HRV data: {e}")

# --- 4. COMPILING FILE CHANGES ---
db_filename = "sleep_database.json"
if os.path.exists(db_filename):
    with open(db_filename, "r") as f:
        try: db = json.load(f)
        except: db = {}
else:
    db = {}

key = f"sleep_data_{todayStr}"
if key not in db:
    db[key] = {}

for k, v in m.items():
    if v != "--":
        db[key][k] = v

with open(db_filename, "w") as f:
    json.dump(db, f, indent=4)

print(f"Database successfully written for {key}: {db[key]}")
