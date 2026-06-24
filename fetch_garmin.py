import os
import json
from datetime import datetime, timezone
from garminconnect import Garmin

EMAIL = os.environ.get("GARMIN_EMAIL")
PASSWORD = os.environ.get("GARMIN_PASSWORD")

if not EMAIL or not PASSWORD:
    print("Missing execution secret variables.")
    exit(1)

try:
    # Initialize and login cleanly without modifying internal hidden attributes
    garmin = Garmin(EMAIL, PASSWORD)
    garmin.login()
except Exception as e:
    print(f"Failed to log into Garmin Connect endpoint framework: {e}")
    exit(1)

todayStr = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
print(f"Executing Deep Telemetry Sync for: {todayStr}")
