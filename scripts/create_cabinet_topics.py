#!/usr/bin/env python3
"""
Create Forum Topics in Telegram Cabinet Supergroup (-1004420587350)
1. 📰 Большие новости (Апрув)
2. 🚨 Дорожные алерты (Дозор)
"""
import urllib.request
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    print("[ERROR] TELEGRAM_BOT_TOKEN is missing!")
    exit(1)
CHAT_ID = "-1004420587350"

TOPICS = [
    {"name": "📰 Большие новости (Апрув)", "icon_color": 7322096},   # Blue
    {"name": "🚨 Дорожные алерты (Дозор)", "icon_color": 16749490}   # Red/Orange
]

def main():
    results = {}
    for t in TOPICS:
        url = f"https://api.telegram.org/bot{TOKEN}/createForumTopic"
        payload = {
            "chat_id": CHAT_ID,
            "name": t["name"],
            "icon_color": t["icon_color"]
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                thread_id = data["result"]["message_thread_id"]
                name = data["result"]["name"]
                results[name] = thread_id
                print(f"[OK] Created topic '{name}' -> message_thread_id: {thread_id}")
        except Exception as e:
            print(f"[ERROR] Failed to create topic '{t['name']}': {e}")

    print("\nTOPIC THREAD IDs:", json.dumps(results, ensure_ascii=False, indent=2))
    return results

if __name__ == "__main__":
    main()
