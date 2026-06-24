import os
import json
from datetime import datetime, timedelta, timezone
from garminconnect import Garmin

# 1. Authenticate with Garmin Connect
# These secrets will be securely configured in GitHub settings later
EMAIL = os.environ.get("GARMIN_EMAIL")
PASSWORD = os.environ.get("GARMIN_PASSWORD")

if not EMAIL or not PASSWORD:
    print("Missing Garmin Credentials")
    exit(1)

try:
    garmin = Garmin(EMAIL, PASSWORD)
    garmin.login()
except Exception as e:
    print(f"Failed to log into Garmin: {e}")
    exit(1)

# 2. Define target date (Yesterday / Last night's sleep)
# Garmin indexes sleep by the "calendarDate" you wake up on
today = datetime.now(timezone.utc).astimezone() # Matches local system time execution
date_str = today.strftime("%Y-%m-%d")

print(f"Fetching Garmin data for date: {date_str}")

try:
    # 3. Pull Wellness & Sleep metrics
    sleep_data = garmin.get_sleep_data(date_str)
    
    # Extract the target fields safely
    daily_sleep = sleep_data.get("dailySleepDTO", {})
    score = daily_sleep.get("sleepScore", "")
    
    deep_sleep_sec = daily_sleep.get("deepSleepSeconds", 0) or 0
    rem_sleep_sec = daily_sleep.get("remSleepSeconds", 0) or 0
    total_deep_rem_hours = round((deep_sleep_sec + rem_sleep_sec) / 3600, 1)

    # HRV data is usually located under an independent summary endpoint or deep sleep structure
    hrv_summary = garmin.get_hrv_data(date_str) or {}
    hrv_val = hrv_summary.get("hrvSummaryDTO", {}).get("lastNightAvg", "")
    
    # If get_hrv_data fails to resolve, fallback onto standard container
    if not hrv_val:
        hrv_val = daily_sleep.get("averageHRV", "")

    # 4. Read the existing layout database or construct a fresh one
    db_filename = "sleep_database.json"
    if os.path.exists(db_filename):
        with open(db_filename, "r") as f:
            try:
                db = json.load(f)
            except:
                db = {}
    else:
        db = {}

    # Initialize nested JSON object for the target day if not present
    key = f"sleep_data_{date_str}"
    if key not in db:
        db[key] = {}

    # 5. Inject automatic metrics while maintaining checked boxes unchanged
    if score: db[key]["garmin_score"] = str(score)
    if hrv_val: db[key]["garmin_hrv"] = str(hrv_val)
    if total_deep_rem_hours > 0: db[key]["garmin_deep"] = str(total_deep_rem_hours)

    # Save tracking file back out
    with open(db_filename, "w") as f:
        json.dump(db, f, indent=4)
        
    print(f"Successfully saved records: Score={score}, HRV={hrv_val}, Deep/REM={total_deep_rem_hours}")

except Exception as e:
    print(f"Error fetching data from Garmin endpoint: {e}")
