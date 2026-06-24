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

# FORCE LOCAL TIME: Calculate target date using Central European Time offset (UTC+2)
# This guarantees it queries the exact calendar day you woke up on
local_time = datetime.now(timezone.utc) + timedelta(hours=2)
todayStr = local_time.strftime("%Y-%m-%d")
print(f"Executing Deep Telemetry Sync for Local Date: {todayStr}")

# Base dictionary mapping to UI elements
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

# --- 1. DEEP HYPNOGRAM & PARSING STRUCTURAL SLEEP DATA ---
try:
    sleep_data = garmin.get_sleep_data(todayStr) or {}
    daily_sleep = sleep_data.get("dailySleepDTO", {})
    
    if daily_sleep:
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
    elif daily_sleep.get("sleepRestlessnessScaleValue") is not None:
        m["g_restless"] = f"Idx: {daily_sleep.get('sleepRestlessnessScaleValue')}/100"
except Exception as e:
    print(f"Error parsing hypnogram dataset structures: {e}")

# --- 2. RESTING HEART RATE FROM DAILY METADATA USER STRUC ---
try:
    stats = garmin.get_user_summary(todayStr) or {}
    if stats.get("restingHeartRate"):
        m["g_rhr"] = f"{int(stats.get('restingHeartRate'))} bpm"
except Exception as e:
    print(f"Bypassing baseline User Summary payload tracking: {e}")

# --- 3. OVERNIGHT AUTONOMIC HRV ANALYSIS ---
try:
    hrv_data = garmin.get_hrv_data(todayStr) or {}
    hrv_summary = hrv_data.get("hrvSummaryDTO", {})
    if hrv_summary and hrv_summary.get("lastNightAvg"):
        m["g_hrv"] = f"{int(hrv_summary.get('lastNightAvg'))} ms"
except Exception as e:
    print(f"Bypassing HRV specialized timeline parser: {e}")

# --- 4. OVERNIGHT SYMPATHETIC STRESS ARCHITECTURE ---
try:
    if 'sleep_data' in locals() and sleep_data.get("sleepStressDTO"):
        stress_val = sleep_data.get("sleepStressDTO", {}).get("averageStressLevel", 0)
        if stress_val > 0:
            m["g_stress"] = f"{int(stress_val)}/100"
except Exception as e:
    print(f"Bypassing autonomic stress scale module: {e}")

# --- 5. COMPILING FILE CHANGES INTO IN-MEMORY JSON LEDGER ---
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

print(f"Database sync successful for {key}: {db[key]}")
