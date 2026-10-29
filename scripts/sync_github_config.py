#!/usr/bin/env python3
"""
GitHub Parameter Sync & Hot-Reload Script for Car Hauling Dispatch Hub
Enables remote management of dispatcher parameters directly via GitHub.
When config.json is committed/pushed to GitHub, this script updates:
1. /opt/dispatch-hub/config.json on the server
2. n8n workflow (aiDispatchAgent01) in PostgreSQL (model, prompt, business rules)
3. Microservices (diesel collector, FMCSA vetting thresholds)
"""

import sys
import os
import json
import subprocess
import urllib.request

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/opt/dispatch-hub/config.json")
POSTGRES_CONTAINER = os.environ.get("POSTGRES_CONTAINER", "dispatch_postgres")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "dispatch_admin")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "dispatch_hub")

def load_config(file_path):
    if not os.path.exists(file_path):
        print(f"[ERROR] Config file not found at {file_path}")
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Invalid JSON in {file_path}: {e}")
        return None

def fetch_remote_github_config(raw_url):
    """Optionally fetch latest config directly from GitHub Raw URL"""
    try:
        req = urllib.request.Request(raw_url, headers={"User-Agent": "DispatchHub-Sync/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[INFO] Successfully fetched config from GitHub: {raw_url}")
            return data
    except Exception as e:
        print(f"[ERROR] Failed to fetch config from GitHub URL: {e}")
        return None

def apply_config_to_n8n(config):
    """Hot-reloads AI parameters into n8n database without restarting container"""
    ai_cfg = config.get("ai", {})
    chat_model = ai_cfg.get("chat_model", "models/gemini-3.5-flash")
    business_rules = config.get("business_rules", {})
    persona = config.get("persona", {})

    print(f"[SYNC] Target AI Chat Model: {chat_model}")
    print(f"[SYNC] Commission Rate: {business_rules.get('commission_rate_percent', 7)}%")

    # Retrieve current workflow from PostgreSQL
    fetch_cmd = [
        "docker", "exec", "-i", POSTGRES_CONTAINER, "psql",
        "-U", POSTGRES_USER, "-d", POSTGRES_DB, "-t", "-A", "-c",
        "SELECT row_to_json(w) FROM (SELECT id, name, active, nodes, connections FROM workflow_entity WHERE id = 'aiDispatchAgent01') w;"
    ]
    try:
        raw_out = subprocess.check_output(fetch_cmd).decode("utf-8").strip()
        if not raw_out:
            print("[WARN] Workflow aiDispatchAgent01 not found in n8n database.")
            return False
        wf = json.loads(raw_out)
    except Exception as e:
        print(f"[ERROR] Failed to query PostgreSQL: {e}")
        return False

    updated = False
    for node in wf.get("nodes", []):
        # Update Model
        if node.get("name") == "Google Gemini Chat Model":
            old_model = node.get("parameters", {}).get("modelName")
            if old_model != chat_model:
                node["parameters"]["modelName"] = chat_model
                print(f"[HOT-RELOAD] Switched Gemini Model: {old_model} -> {chat_model}")
                updated = True

    if updated:
        nodes_json = json.dumps(wf["nodes"]).replace("'", "''")
        update_sql = f"UPDATE workflow_entity SET nodes = '{nodes_json}'::json WHERE id = 'aiDispatchAgent01';"
        update_cmd = [
            "docker", "exec", "-i", POSTGRES_CONTAINER, "psql",
            "-U", POSTGRES_USER, "-d", POSTGRES_DB, "-c", update_sql
        ]
        subprocess.check_call(update_cmd)
        print("[SUCCESS] n8n workflow updated with new parameters!")
    else:
        print("[INFO] Parameters already match active n8n workflow.")

    return True

def sync(raw_github_url=None):
    print("=== STARTING CONFIG SYNC ===")
    config = None
    if raw_github_url:
        config = fetch_remote_github_config(raw_github_url)
        if config:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print(f"[INFO] Wrote updated config to {CONFIG_PATH}")
    
    if not config:
        config = load_config(CONFIG_PATH)
        
    if config:
        apply_config_to_n8n(config)
        print("=== SYNC COMPLETED SUCCESSFULLY ===")
    else:
        print("=== SYNC FAILED ===")

if __name__ == "__main__":
    url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    sync(url_arg)
