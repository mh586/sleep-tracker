import os
import json
from datetime import datetime, timedelta
from garminconnect import Garmin

# --- 1. INITIALIZE CLIENT ---
email = os.getenv("GARMIN_EMAIL")
password = os.getenv("GARMIN_PASSWORD")
client = Garmin(email, password)
client.login()

today = datetime.now()
todayStr = today.strftime("%Y-%m-%d")

# --- 2. FETCH CORE STATISTICS ---
summary_stats = {}
try:
    summary_stats = client.get_stats(todayStr)
except Exception as e:
    print(f"Warning: Primary stats fetch failed due to rate limitations: {e}")

total_steps = summary_stats.get("steps", 0) if summary_stats else "--"

# Map baseline summary properties safely
m = {
    "g_score": summary_stats.get("sleepScore", "--") if summary_stats else "--",
    "g_hrv": summary_stats.get("averageHRV", "--") if summary_stats else "--",
    "g_total": summary_stats.get("totalSleepTimeTime", "--") if summary_stats else "--",
    "g_deep": summary_stats.get("deepSleepTime", "--") if summary_stats else "--",
    "g_rem": summary_stats.get("remSleepTime", "--") if summary_stats else "--",
    "g_light": summary_stats.get("lightSleepTime", "--") if summary_stats else "--",
    "g_awake": summary_stats.get("awakeTime", "--") if summary_stats else "--",
    "g_restless": summary_stats.get("restlessTime", "--") if summary_stats else "--",
    "g_stress": summary_stats.get("averageStressLevel", "--") if summary_stats else "--",
    "g_rhr": summary_stats.get("restingHeartRate", "--") if summary_stats else "--",
    "g_ashr": summary_stats.get("averageSleepHeartRate", "--") if summary_stats else "--",
    "g_resp": summary_stats.get("averageRespirationRate", "--") if summary_stats else "--"
}

# --- 3. HIGH-RESOLUTION TIMELINE FALLBACK WRAPPERS ---
hr_values = []
try:
    hr_data = client.get_heart_rates(todayStr)
    hr_values = hr_data.get("heartRateValues", []) if hr_data else []
except Exception as e:
    print(f"Skipping high-res heart rate parsing (Rate Limited): {e}")

steps_data = []
try:
    # CRITICAL FIX: Changed from get_steps to get_steps_data
    steps_data = client.get_steps_data(todayStr)
except Exception as e:
    print(f"Skipping high-res step timeline parsing (Rate Limited): {e}")

stress_timeline = []
try:
    stress_data = client.get_stress(todayStr)
    stress_timeline = stress_data.get("stressValuesArray", []) if stress_data else []
except Exception as e:
    print(f"Skipping high-res stress parsing (Rate Limited): {e}")

# --- 4. CALCULATE 30-MIN ROLLING METRICS ---
now_ts = datetime.now()
thirty_mins_ago = now_ts - timedelta(minutes=30)

recent_hrs = [e[1] for e in hr_values if e[1] is not None and datetime.fromtimestamp(e[0]/1000.0) >= thirty_mins_ago]
avg_hr_30m = round(sum(recent_hrs) / len(recent_hrs)) if recent_hrs else "--"

recent_stress = [s[1] for s in stress_timeline if s[1] is not None and s[1] >= 0 and datetime.fromtimestamp(s[0]/1000.0) >= thirty_mins_ago]
avg_stress_30m = round(sum(recent_stress) / len(recent_stress)) if recent_stress else "--"

# --- 5. INACTIVITY BAR COMPUTATION ---
inactivity_alerts = 0
consecutive_idle = 0
if isinstance(steps_data, list):
    for block in steps_data:
        # Steps data is typically returned as a dictionary or structured object element block
        steps_in_interval = block.get("steps", 0) if isinstance(block, dict) else 0
        if steps_in_interval == 0:
            consecutive_idle += 1
            if consecutive_idle == 4: 
                inactivity_alerts += 1
            elif consecutive_idle > 4 and (consecutive_idle - 4) % 1 == 0: 
                inactivity_alerts += 1
        else:
            consecutive_idle = 0

# --- 6. CHART PACKING COMPONENT ---
chart_timeline = []
if hr_values:
    for hr_entry in hr_values[::15]:
        ts_ms = hr_entry[0]
        matching_stress = "--"
        for s in stress_timeline:
            if abs(s[0] - ts_ms) < 300000:
                if s[1] is not None and s[1] >= 0:
                    matching_stress = s[1]
                    break
        chart_timeline.append({
            "time": datetime.fromtimestamp(ts_ms / 1000.0).strftime("%H:%M"),
            "hr": hr_entry[1] if hr_entry[1] else 0,
            "stress": matching_stress if matching_stress != "--" else 0
        })

# Assign calculated attributes back to data packet payload
m["avg_hr_30m"] = avg_hr_30m
m["avg_stress_30m"] = avg_stress_30m
m["today_steps"] = total_steps
m["inactivity_alerts"] = inactivity_alerts
if chart_timeline:
    m["chart_timeline"] = chart_timeline

# --- 7. WRITE TO LEDGER ---
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

# Merge changes cleanly without deleting old attributes
for k, v in m.items():
    if v != "--":
        db[key][k] = v

with open(db_filename, "w") as f:
    json.dump(db, f, indent=4)

print(f"Sync execution process cycle completed for {key}")
