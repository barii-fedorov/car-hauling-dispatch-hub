#!/usr/bin/env python3
import json
import urllib.request
import urllib.error
import os

GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://localhost:3000")
GRAFANA_USER = os.environ.get("GRAFANA_USER", "admin")
GRAFANA_PASS = os.environ.get("GRAFANA_PASS", "GrafanaAdminSecure2026!")

current_dir = os.path.dirname(os.path.abspath(__file__))
dash_file = os.path.join(current_dir, "grafana_user_profiles_dashboard.json")

with open(dash_file, "r", encoding="utf-8") as f:
    payload = json.load(f)

# Basic Auth header
import base64
auth_str = f"{GRAFANA_USER}:{GRAFANA_PASS}"
b64_auth = base64.b64encode(auth_str.encode()).decode()

req = urllib.request.Request(
    f"{GRAFANA_URL}/api/dashboards/db",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Basic {b64_auth}"
    }
)

try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        res = json.loads(resp.read().decode())
        print("[SUCCESS] Dashboard uploaded to Grafana:", res)
except urllib.error.HTTPError as e:
    print("[ERROR] Failed to upload dashboard:", e.read().decode())
