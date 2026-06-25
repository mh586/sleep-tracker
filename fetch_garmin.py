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

# --- 2. FETCH DATA FROM GARMIN ---
hr_data = client.get_heart_rates(todayStr)
steps_data = client.get_steps(todayStr)
summary_stats = client.get_stats(todayStr)
total_steps = summary_stats.get("steps", 0)

# Extract core summary properties for your layout metrics
m = {
    "g_score": summary_stats.get("sleepScore", "--"),
    "g_hrv": summary_stats.get("averageHRV", "--"),
    "g_total": summary_stats.get("totalSleepTimeTime", "--"),
    "g_deep": summary_stats.get("deepSleepTime", "--"),
    "g_rem": summary_stats.get("remSleepTime", "--"),
    "g_light": summary_stats.get("lightSleepTime", "--"),
    "g_awake": summary_stats.get("awakeTime", "--"),
    "g_restless": summary_stats.get("restlessTime", "--"),
    "g_stress": summary_stats.get("averageStressLevel", "--"),
    "g_rhr": summary_stats.get("restingHeartRate", "--"),
    "g_ashr": summary_stats.get("averageSleepHeartRate", "--"),
    "g_resp": summary_stats.get("averageRespirationRate", "--")
}

# --- 3. CALCULATE 30-MIN ROLLING METRICS ---
hr_values = hr_data.get("heartRateValues", [])
now_ts = datetime.now()
thirty_mins_ago = now_ts - timedelta(minutes=30)

recent_hrs = [e[1] for e in hr_values if datetime.fromtimestamp(e[0]/1000.0) >= thirty_mins_ago and e[1] is not None]
avg_hr_30m = round(sum(recent_hrs) / len(recent_hrs)) if recent_hrs else "--"

try:
    stress_timeline = client.get_stress(todayStr).get("stressValuesArray", [])
    recent_stress = [s[1] for s in stress_timeline if datetime.fromtimestamp(s[0]/1000.0) >= thirty_mins_ago and s[1] is not None and s[1] >= 0]
    avg_stress_30m = round(sum(recent_stress) / len(recent_stress)) if recent_stress else "--"
except:
    avg_stress_30m = "--"
    stress_timeline = []

# --- 4. INACTIVITY BAR COMPUTATION ---
inactivity_alerts = 0
consecutive_idle = 0
for block in steps_data:
    if block.get("steps", 0) == 0:
        consecutive_idle += 1
        if consecutive_idle == 4: 
            inactivity_alerts += 1
        elif consecutive_idle > 4 and (consecutive_idle - 4) % 1 == 0: 
            inactivity_alerts += 1
    else:
        consecutive_idle = 0

# --- 5. CHART PACKING COMPONENT ---
chart_timeline = []
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

# Add the new telemetry properties directly to your primary metrics data dictionary
m["avg_hr_30m"] = avg_hr_30m
m["avg_stress_30m"] = avg_stress_30m
m["today_steps"] = total_steps
m["inactivity_alerts"] = inactivity_alerts
m["chart_timeline"] = chart_timeline

# --- 6. WRITE TO LEDGER ---
db_filename = "sleep_database.json"
if os.path.exists(db_filename):
    with open(db_filename, "r") as f:
        try: db = json.load(f)
        except: db = {}
else:
    db = {}

key = f"sleep_data_{todayStr}"

# Safe initialization to prevent key crashes
if key not in db:
    db[key] = {}

# Non-destructive merge strategy loop
for k, v in m.items():
    if v != "--":
        db[key][k] = v

with open(db_filename, "w") as f:
    json.dump(db, f, indent=4)

print(f"Deep Search Sync Completed for {key}: {db[key]}")
