"""
Car Hauler News & Road Alert Engine ("Совет Агентов: Новости и Дорожный Дозор")
Generates:
1. High-relevance Car Hauler Industry News (1-2 times daily during US business hours) with authentic incident photos.
2. Short & frequent Road / DOT / Weather Alerts (incidents, wind, chains, closed interstates, sudden weigh stations).
Applies the Unified Hashtag Taxonomy (#Алерт, #Новости, #Весы, #I80, #WY, #TX, etc.).
"""

import os
import sys
import re
import time
import json
import sqlite3
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime

# Environment Variables
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
CHANNEL_ID = os.environ.get("CHANNEL_CHAT_ID", "-1004424371115")      # "Грузовики на базу"
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "-1004420587350")      # Cabinet Admin Supergroup

DB_PATH = os.environ.get("ALERT_DB_PATH", os.path.join(os.path.dirname(__file__), "feed_history.db"))

FEEDS = [
    {
        "name": "CDLLife",
        "url": "https://cdllife.com/feed/",
        "weight": 1.0,
        "type": "mixed"
    },
    {
        "name": "LandLine",
        "url": "https://landline.media/feed/",
        "weight": 0.8,
        "type": "news"
    },
    {
        "name": "FreightWaves",
        "url": "https://www.freightwaves.com/feed",
        "weight": 0.9,
        "type": "news"
    }
]

ALERT_KEYWORDS = [
    "crash", "closed", "shut down", "overturned", "pileup", "chains required",
    "high wind", "blowover", "inspection", "blitz", "weigh station", "low clearance",
    "bridge strike", "detour", "jackknife", "blizzard", "icy", "road closure"
]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS processed_items (
            guid TEXT PRIMARY KEY,
            title TEXT,
            published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            post_type TEXT
        )
    """)
    conn.commit()
    conn.close()

def is_processed(guid):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM processed_items WHERE guid = ?", (guid,))
    res = cur.fetchone()
    conn.close()
    return res is not None

def mark_processed(guid, title, post_type):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO processed_items (guid, title, post_type) VALUES (?, ?, ?)", (guid, title, post_type))
    conn.commit()
    conn.close()

def extract_image_url(item_xml, full_text=""):
    """
    Extracts high-resolution real incident / story image URL from RSS tags or HTML content.
    """
    # 1. Enclosure
    enclosure = item_xml.find("enclosure")
    if enclosure is not None and "image" in enclosure.attrib.get("type", ""):
        return enclosure.attrib.get("url")

    # 2. Media content / thumbnail
    for child in item_xml:
        if "content" in child.tag or "thumbnail" in child.tag:
            url = child.attrib.get("url")
            if url and any(url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                return url

    # 3. Regex inside description or content:encoded
    combined = full_text
    for tag_name in ["description", "{http://purl.org/rss/1.0/modules/content/}encoded"]:
        elem = item_xml.find(tag_name)
        if elem is not None and elem.text:
            combined += " " + elem.text

    img_match = re.search(r'<img[^>]+src=["\']([^"\']+\.(?:jpg|jpeg|png|webp))["\']', combined, re.IGNORECASE)
    if img_match:
        return img_match.group(1)

    return None

def fetch_feed_items():
    items = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for source in FEEDS:
        try:
            req = urllib.request.Request(source["url"], headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                xml_data = resp.read().decode("utf-8", errors="ignore")
            root = ET.fromstring(xml_data)
            for item in root.findall("./channel/item")[:8]:
                title = item.find("title").text if item.find("title") is not None else ""
                link = item.find("link").text if item.find("link") is not None else ""
                guid = item.find("guid").text if item.find("guid") is not None else link
                pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                desc = item.find("description").text if item.find("description") is not None else ""

                content_elem = item.find("{http://purl.org/rss/1.0/modules/content/}encoded")
                content = content_elem.text if content_elem is not None else desc

                image_url = extract_image_url(item, content)

                items.append({
                    "source": source["name"],
                    "title": title.strip(),
                    "link": link.strip(),
                    "guid": guid.strip(),
                    "pubDate": pub_date,
                    "content": content,
                    "image_url": image_url
                })
        except Exception as e:
            print(f"[WARN] Failed to fetch feed {source['name']}: {e}")
    return items

def ask_gemini_prompt(prompt):
    if not GEMINI_KEY:
        print("[ERROR] GEMINI_API_KEY is not configured!")
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 800}
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
    except Exception as e:
        print(f"[ERROR] Gemini request failed: {e}")
    return None

def generate_news_post(item):
    """
    Creates an in-depth, super relevant news post formatted for Telegram with authentic road slang and unified hashtags.
    """
    prompt = f"""
Ты — Совет Агентов американского автовозного диспатча («Грузовики на базу»).
Напиши пост для Telegram-канала оунер-операторов автовозов на основе следующей американской новости:

ИСТОЧНИК: {item['source']}
ЗАГОЛОВОК: {item['title']}
ТЕКСТ: {item['content'][:1500]}
ССЫЛКА: {item['link']}

ТРЕБОВАНИЯ:
1. Язык: Сочный русский язык американских дальнобойщиков / автовозников (стингер, виджик, оунер, весы, оверхэнг, DOT, инспекция, RPM, ставки).
2. Формат:
   ⚡ **[Яркий емкий заголовок с эмодзи]**
   
   📌 **Суть:** 2-3 предложения, только факты (что произошло, где, кто попал под раздачу).
   
   💰 **Что это значит для нашего оунера:** 2 предложения с практическим выводом (риски, штрафы, как избежать проблем, как это влияет на ставки или проезд).
   
   🏷️ **Хештеги (ОБЯЗАТЕЛЬНО из единой системы):**
   Строго включи:
   - #Новости
   - Трассу, если упомянута (например #I80, #I70, #I95)
   - Штат, если упомянут (например #TX, #PA, #OH, #WY, #IN)
   - Тематику/Сетап (например #Весы, #Ставки, #Стингер, #Виджик, #DOT_Рейд)

Не пиши ничего лишнего, только готовый текст поста для Telegram.
"""
    return ask_gemini_prompt(prompt)

def generate_road_alert_post(item):
    """
    Creates a fast, short road incident or weather alert for car haulers.
    """
    prompt = f"""
Ты — Дорожный Дозор автовозного диспатча («Грузовики на базу»).
Сделай короткий срочный дорожный алерт для водителей автовозов на основе новости:

ЗАГОЛОВОК: {item['title']}
ТЕКСТ: {item['content'][:800]}

ФОРМАТ ПОСТА:
🚨 **ДОРОЖНЫЙ АЛЕРТ: [Трасса/Коридор] ([Штат])**

⚠️ **Ситуация:** (1-2 предложения: что перекрыто, завал, сильный ветер, проверка DOT)
🚛 **Совет автовозам:** (1 предложение: стингерам/виджикам объехать, отстояться на трак-стопе, приготовить цепи)

🏷️ **Хештеги:** #Алерт #[Трасса] #[Штат] #[Сетап] (например #Алерт #I80 #WY #Погода #Стингер)

Кратко, по-деловому, без воды.
"""
    return ask_gemini_prompt(prompt)

def send_telegram_post(text, image_url=None, target_chats=None):
    if not BOT_TOKEN:
        print("[ERROR] TELEGRAM_BOT_TOKEN is missing!")
        return False
    if target_chats is None:
        target_chats = [CHANNEL_ID, ADMIN_CHAT_ID]

    success = True
    for chat_id in target_chats:
        try:
            caption_text = text[:1020]
            delivered = False

            if image_url:
                # Try sendPhoto with Markdown
                photo_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
                payload = {
                    "chat_id": chat_id,
                    "photo": image_url,
                    "caption": caption_text,
                    "parse_mode": "Markdown"
                }
                req = urllib.request.Request(
                    photo_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                try:
                    urllib.request.urlopen(req, timeout=20)
                    print(f"[OK] Photo post delivered to chat {chat_id}")
                    delivered = True
                except urllib.error.HTTPError:
                    # Retry sendPhoto without markdown parse_mode
                    try:
                        payload.pop("parse_mode", None)
                        req = urllib.request.Request(photo_url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                        urllib.request.urlopen(req, timeout=20)
                        print(f"[OK] Photo post delivered to chat {chat_id} (fallback without markdown)")
                        delivered = True
                    except Exception as ex_photo:
                        print(f"[WARN] sendPhoto fallback failed: {ex_photo}")

            if not delivered:
                # Fallback to sendMessage
                msg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": False
                }
                req = urllib.request.Request(
                    msg_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                try:
                    urllib.request.urlopen(req, timeout=15)
                    print(f"[OK] Text post delivered to chat {chat_id}")
                except urllib.error.HTTPError:
                    payload.pop("parse_mode", None)
                    req = urllib.request.Request(msg_url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                    urllib.request.urlopen(req, timeout=15)
                    print(f"[OK] Text post delivered to chat {chat_id} (plain text fallback)")
        except Exception as e:
            print(f"[ERROR] Delivery failed to {chat_id}: {e}")
            success = False
    return success

def run_news_pipeline():
    print(f"[{datetime.now()}] [NEWS PIPELINE] Checking for high-impact car hauler news...")
    items = fetch_feed_items()
    for item in items:
        if is_processed(item["guid"]):
            continue

        # Look for substantive news
        print(f"[FOUND NEWS] {item['title']} (Image: {bool(item['image_url'])})")
        post_text = generate_news_post(item)
        if post_text:
            if send_telegram_post(post_text, image_url=item["image_url"]):
                mark_processed(item["guid"], item["title"], "news")
                print(f"[PUBLISHED NEWS] {item['title']}")
                break # 1 in-depth news article per run
            else:
                print(f"[FAIL] Could not deliver news: {item['title']}")

def run_alerts_pipeline():
    print(f"[{datetime.now()}] [ALERTS PIPELINE] Scanning for highway incidents & road closures...")
    items = fetch_feed_items()
    count = 0
    for item in items:
        if is_processed(item["guid"]):
            continue

        title_lower = item["title"].lower()
        content_lower = item["content"].lower()

        is_alert = any(kw in title_lower or kw in content_lower for kw in ALERT_KEYWORDS)
        if not is_alert:
            continue

        print(f"[CRITICAL ROAD ALERT] {item['title']}")
        alert_text = generate_road_alert_post(item)
        if alert_text:
            if send_telegram_post(alert_text, image_url=item["image_url"]):
                mark_processed(item["guid"], item["title"], "alert")
                print(f"[PUBLISHED ALERT] {item['title']}")
                count += 1
                if count >= 2: # Max 2 rapid alerts per sweep to avoid spam
                    break

def main():
    init_db()
    mode = "news" if len(sys.argv) < 2 else sys.argv[1].lower()
    if mode in ["--news", "news"]:
        run_news_pipeline()
    elif mode in ["--alerts", "alerts"]:
        run_alerts_pipeline()
    elif mode in ["--daemon", "daemon"]:
        print("[START] Running News & Alerts Engine in continuous daemon mode...")
        last_news_time = 0
        while True:
            try:
                # 1. Run road alerts every 20 minutes
                run_alerts_pipeline()

                # 2. Run news 2x daily (every 6 hours or around working hours)
                now = time.time()
                if now - last_news_time > (6 * 3600):
                    run_news_pipeline()
                    last_news_time = now

                time.sleep(1200) # 20 minutes
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[ERROR] Engine loop: {e}")
                time.sleep(60)
    else:
        print("Usage: python news_and_alerts_engine.py [--news | --alerts | --daemon]")

if __name__ == "__main__":
    main()
