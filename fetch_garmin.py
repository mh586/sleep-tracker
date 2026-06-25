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

# --- 2. FETCH HIGH-RESOLUTION TIMELINE TELEMETRY ---
# Fetching intraday heart rate and steps arrays
hr_data = client.get_heart_rates(todayStr)
steps_data = client.get_steps(todayStr) # Returns list of fine-grained intervals

# Extract core summary metrics
summary_stats = client.get_stats(todayStr)
total_steps = summary_stats.get("steps", 0)

# --- 3. COMPUTE TRAILING 30-MINUTE METRICS ---
hr_values = hr_data.get("heartRateValues", [])
now_ts = datetime.now()
thirty_mins_ago = now_ts - timedelta(minutes=30)

recent_hrs = []
for entry in hr_values:
    # entry format: [timestamp_ms, bpm]
    entry_time = datetime.fromtimestamp(entry[0] / 1000.0)
    if entry_time >= thirty_mins_ago and entry[1] is not None:
        recent_hrs.append(entry[1])

avg_hr_30m = round(sum(recent_hrs) / len(recent_hrs)) if recent_hrs else "--"

# Estimate stress from HR variations in the last 30 mins if not explicitly exposed
# (Garmin packages detailed stress separately, we map a representative sample or direct fetch if available)
try:
    stress_timeline = client.get_stress(todayStr).get("stressValuesArray", [])
    recent_stress = [s[1] for s in stress_timeline if datetime.fromtimestamp(s[0]/1000.0) >= thirty_mins_ago and s[1] is not None and s[1] >= 0]
    avg_stress_30m = round(sum(recent_stress) / len(recent_stress)) if recent_stress else "--"
except:
    avg_stress_30m = "--"
    stress_timeline = []

# --- 4. COUNT INACTIVITY ALERTS ---
# Inactivity alerts are triggered when movement blocks drop to zero for prolonged intervals
inactivity_alerts = 0
consecutive_idle = 0
for block in steps_data:
    steps_in_interval = block.get("steps", 0)
    if steps_in_interval == 0:
        consecutive_idle += 1
        # Garmin triggers a move bar at 60 mins of inactivity, then increments every 15 mins
        if consecutive_idle == 4: # Assuming 15-minute chunk resolutions
            inactivity_alerts += 1
        elif consecutive_idle > 4 and (consecutive_idle - 4) % 1 == 0:
            inactivity_alerts += 1
    else:
        consecutive_idle = 0

# --- 5. COMPILE TIMELINE FOR GRAPHING ---
# Downsample timeline data to hourly intervals to keep JSON lightweight
chart_timeline = []
for hr_entry in hr_values[::15]: # Step through array to map trends since morning
    ts_ms = hr_entry[0]
    hr_val = hr_entry[1]
    
    # Find matching stress entry near this time index
    matching_stress = "--"
    for s in stress_timeline:
        if abs(s[0] - ts_ms) < 300000: # within 5 minutes
            if s[1] is not None and s[1] >= 0:
                matching_stress = s[1]
                break
                
    time_label = datetime.fromtimestamp(ts_ms / 1000.0).strftime("%H:%M")
    chart_timeline.append({
        "time": time_label,
        "hr": hr_val if hr_val else 0,
        "stress": matching_stress if matching_stress != "--" else 0
    })

# --- 6. WRITE BACK TO LEDGER NON-DESTRUCTIVELY ---
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

# Pack new parameters into state ledger
db[key]["avg_hr_30m"] = avg_hr_30m
db[key]["avg_stress_30m"] = avg_stress_30m
db[key]["today_steps"] = total_steps
db[key]["inactivity_alerts"] = inactivity_alerts
db[key]["chart_timeline"] = chart_timeline

with open(db_filename, "w") as f:
    json.dump(db, f, indent=4)

print(f"Telemetry sync payload updated for {key}")
