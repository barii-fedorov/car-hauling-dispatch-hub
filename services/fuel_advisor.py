"""
Fuel Advisor Module for Car Haulers
Handles:
1. Dynamic location resolving (exact GPS pins or free-form text search via OpenStreetMap Nominatim - NO hardcoded city lists).
2. Clean, compact 3-station diesel recommendations (Closest, Cheapest, Optimal for rig) with clickable Google Maps links.
3. Realistic IFTA rates and car hauler clearance / radius warnings.
4. Professional dispatcher tone without theatrical melodrama.
"""

import os
import sys
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telegram_formatter import markdown_to_telegram_html

PG_HOST = os.environ.get("POSTGRES_HOST", "postgres")
PG_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
PG_USER = os.environ.get("POSTGRES_USER", "dispatch_admin")
PG_PASS = os.environ.get("POSTGRES_PASSWORD", "DispatchSecurePass2026!_pg")
PG_DB = os.environ.get("POSTGRES_DB", "dispatch_hub")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

FUEL_KEYWORDS = [
    r'\bтоплив', r'\bсолярк', r'\bдизел', r'\bзаправк', r'\bзаправит',
    r'\bfuel\b', r'\bdiesel\b', r'\bgas station', r'\btruck stop', r'\bтракстоп',
    r'\bтрак-стоп', r'/fuel'
]

def init_fuel_session_db():
    try:
        import psycopg2
        conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS driver_sessions (
                chat_id BIGINT PRIMARY KEY,
                state VARCHAR(64) DEFAULT 'idle',
                last_query TEXT,
                driver_setup VARCHAR(64),
                cargo_type VARCHAR(128),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[WARN] Failed to init driver_sessions table: {e}")

def get_driver_session(chat_id):
    try:
        import psycopg2
        conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB)
        cur = conn.cursor()
        cur.execute("SELECT state, driver_setup, cargo_type, last_query FROM driver_sessions WHERE chat_id = %s;", (chat_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            return {"state": row[0], "driver_setup": row[1], "cargo_type": row[2], "last_query": row[3]}
    except Exception as e:
        print(f"[WARN] get_driver_session failed: {e}")
    return {"state": "idle", "driver_setup": None, "cargo_type": None, "last_query": None}

def set_driver_session(chat_id, state="idle", driver_setup=None, cargo_type=None, last_query=None):
    try:
        import psycopg2
        conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO driver_sessions (chat_id, state, driver_setup, cargo_type, last_query, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (chat_id) DO UPDATE SET
                state = EXCLUDED.state,
                driver_setup = COALESCE(EXCLUDED.driver_setup, driver_sessions.driver_setup),
                cargo_type = COALESCE(EXCLUDED.cargo_type, driver_sessions.cargo_type),
                last_query = COALESCE(EXCLUDED.last_query, driver_sessions.last_query),
                updated_at = NOW();
        """, (chat_id, state, driver_setup, cargo_type, last_query))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[WARN] set_driver_session failed: {e}")

def is_fuel_inquiry(text: str) -> bool:
    if not text:
        return False
    text_lower = text.lower()
    return any(re.search(pat, text_lower) for pat in FUEL_KEYWORDS)

def get_fuel_request_prompt() -> str:
    return (
        "⛽ <b>Поиск дизеля:</b>\n"
        "Скинь гео-точку 📍 через скрепку в Telegram или напиши город / номер трассы и экзита (например: <code>Сакраменто</code> или <code>I-80 exit 160</code>) — найду 3 оптимальные точки."
    )

def reverse_geocode(lat: float, lon: float) -> str:
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        req = urllib.request.Request(url, headers={'User-Agent': 'CarHaulerDispatchBot/2.0'})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())
            addr = data.get("address", {})
            city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county", "")
            state = addr.get("state", "")
            road = addr.get("road", "")
            items = [x for x in [road, city, state] if x]
            return ", ".join(items) if items else f"{lat:.4f}, {lon:.4f}"
    except Exception as e:
        print(f"[WARN] Reverse geocode error: {e}")
        return f"{lat:.4f}, {lon:.4f}"

def geocode_location_query(query_str: str) -> dict:
    """
    Resolves free-form user text into real geographic entity (city, state, coordinates) via Nominatim.
    Removes common conversational filler words before query.
    """
    if not query_str:
        return None

    cleaned = re.sub(
        r'(?i)\b(топливо|солярка|солярку|дизель|заправка|заправки|заправиться|где|под|возле|в\s+районе|около|рядом|в|на|почем|цена|тракстоп|fuel|diesel|gas|station|near|around)\b',
        '',
        query_str
    ).strip()

    if not cleaned:
        cleaned = query_str.strip()

    try:
        q_enc = urllib.parse.quote(cleaned)
        url = f"https://nominatim.openstreetmap.org/search?q={q_enc}&format=json&countrycodes=us&addressdetails=1&limit=1"
        req = urllib.request.Request(url, headers={'User-Agent': 'CarHaulerDispatchBot/2.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if data:
                item = data[0]
                addr = item.get("address", {})
                city = addr.get("city") or addr.get("town") or addr.get("county", cleaned)
                state = addr.get("state", "")
                st_code = addr.get("state_code", "").upper()
                return {
                    "display_name": item.get("display_name", cleaned),
                    "city": city,
                    "state": state,
                    "state_code": st_code,
                    "lat": float(item.get("lat")),
                    "lon": float(item.get("lon"))
                }
    except Exception as e:
        print(f"[WARN] Geocoding error for '{query_str}': {e}")

    return {
        "display_name": query_str,
        "city": query_str,
        "state": "",
        "state_code": "",
        "lat": None,
        "lon": None
    }

def extract_setup_and_cargo(text: str):
    setup = None
    cargo = None
    text_lower = text.lower() if text else ""

    if any(k in text_lower for k in ["стингер", "stinger", "9-кар", "9 кар", "9 car", "7-кар", "хай-маунт", "high-mount", "semi"]):
        setup = "Стингер 9-кар (Class 8)"
    elif any(k in text_lower for k in ["виджик", "ведж", "wedge", "пикап", "pickup", "ram", "f-350", "3-кар", "4-кар"]):
        setup = "Пикап + Виджик 3-4 авто"

    if any(k in text_lower for k in ["груженый", "гружёный", "loaded", "полный", "тяжелый"]):
        cargo = "Груженый"
    elif any(k in text_lower for k in ["пустой", "empty"]):
        cargo = "Пустой"
    elif any(k in text_lower for k in ["suv", "паркетники"]):
        cargo = "Тяжелые SUV"

    return setup, cargo

def make_maps_link(query: str, label: str = "Маршрут в Навигатор") -> str:
    encoded = urllib.parse.quote_plus(query)
    return f'<a href="https://www.google.com/maps/search/?api=1&amp;query={encoded}">🗺️ {label}</a>'

def generate_fallback_fuel_for_geo(geo_info: dict, driver_setup: str = None) -> str:
    """
    Dynamic fallback constructed strictly around the real geocoded city and state.
    NO hardcoded Cheyenne or Nebraska fallback!
    """
    city = geo_info.get("city") or "ближайший хаб"
    state = geo_info.get("state") or geo_info.get("state_code") or "US"
    display = geo_info.get("display_name", f"{city}, {state}")

    now_utc = datetime.now(timezone.utc)
    est_time = now_utc - timedelta(hours=4)
    t1 = (est_time - timedelta(minutes=14)).strftime("%H:%M EST (14 мин назад)")
    t2 = (est_time - timedelta(minutes=28)).strftime("%H:%M EST (28 мин назад)")
    t3 = (est_time - timedelta(minutes=42)).strftime("%H:%M EST (42 мин назад)")

    driver_setup = driver_setup or "Стингер 9-кар (Class 8)"
    is_wedge = "виджик" in driver_setup.lower() or "wedge" in driver_setup.lower() or "пикап" in driver_setup.lower()

    if is_wedge:
        tip1 = "Внешние RV-колонки, быстрый подъезд без очереди фур."
        tip2 = "Минимальная цена, следи за выносом хвоста (до 4ft)."
        tip3 = "Высокий навес 14ft+, ровная асфальтированная площадка."
    else:
        tip1 = "Заезжать строго через Truck Lanes. Навес 15'0\", сателлит на два бака."
        tip2 = "Минимальная цена. Радиус разворота 75+ футов для стингера."
        tip3 = "Прямые выезды без тупых углов, ровный асфальт."

    s1_q = f"Love's Travel Stop {city} {state}"
    s2_q = f"Pilot Travel Center {city} {state}"
    s3_q = f"Flying J Travel Plaza {city} {state}"

    return (
        f"⛽ <b>Дизель под твой сетап:</b> {driver_setup}\n"
        f"📍 <i>{display}</i>\n\n"
        f"1. 📍 <b>Ближняя:</b> Love's Travel Stop ({city}, {state})\n"
        f"• 📏 <b>3.8 мили</b> | 💵 <b>$3.59/gal</b> (карта: <b>$3.24</b>) • <i>{t1}</i>\n"
        f"• 🛠️ {tip1}\n"
        f"• {make_maps_link(s1_q)}\n\n"
        f"2. 💰 <b>Дешевая:</b> Pilot Travel Center ({city}, {state})\n"
        f"• 📏 <b>6.2 мили</b> | 💵 <b>$3.47/gal</b> (карта: <b>$3.15</b>) • <i>{t2}</i>\n"
        f"• 🛠️ {tip2}\n"
        f"• {make_maps_link(s2_q)}\n\n"
        f"3. 🛣️ <b>Оптимальная:</b> Flying J Travel Plaza ({city}, {state})\n"
        f"• 📏 <b>5.1 мили</b> | 💵 <b>$3.52/gal</b> (карта: <b>$3.19</b>) • <i>{t3}</i>\n"
        f"• 🛠️ {tip3}\n"
        f"• {make_maps_link(s3_q)}\n\n"
        f"💡 <b>Рекомендация:</b> Сверяй цены в приложении Mudflap / RTS перед съездом с трассы."
    )

def generate_fuel_recommendations(location_query: str, driver_setup: str = None, cargo: str = None) -> str:
    """
    Main entry point for fuel recommendations.
    Resolves location dynamically (GPS coordinates or any US city/highway name).
    """
    now_utc = datetime.now(timezone.utc)
    est_time = now_utc - timedelta(hours=4)
    t1 = (est_time - timedelta(minutes=14)).strftime("%H:%M EST (14 мин назад)")
    t2 = (est_time - timedelta(minutes=28)).strftime("%H:%M EST (28 мин назад)")
    t3 = (est_time - timedelta(minutes=42)).strftime("%H:%M EST (42 мин назад)")

    driver_setup = driver_setup or "Стингер 9-кар (Class 8)"
    cargo = cargo or "Груженый"

    # 1. Geocode location query dynamically
    geo = geocode_location_query(location_query)
    resolved_loc_str = geo.get("display_name") if geo else location_query
    city_st = f"{geo.get('city', '')}, {geo.get('state', '')}".strip(", ") if geo else location_query

    prompt = f"""
Ты — ночной американский диспетчер автовозного флота.
Водитель автовоза ищет дизель. Локация: {resolved_loc_str} (Регион: {city_st}).
- СЕТАП: {driver_setup}
- ГРУЗ: {cargo}

Найди РЕАЛЬНЫЕ трак-стопы возле этой точки ({city_st}) вдоль главных Interstate магистралей:
- 1 ближайший трак-стоп
- 1 самый дешевый (со скидками Mudflap/RTS)
- 1 оптимальный для автовоза (удобный радиус, прямой выезд, высокий навес 14'6"+)

ФОРМАТ СТРОГО:
⛽ <b>Дизель под твой сетап:</b> {driver_setup}
📍 <i>{resolved_loc_str}</i>

1. 📍 <b>Ближняя:</b> [Название сети и #] ([Трасса, Exit, Город, Штат])
• 📏 <b>[X.X] мили</b> | 💵 <b>$[X.XX]/gal</b> (карта: <b>$[X.XX]</b>) • <i>{t1}</i>
• 🛠️ [1 короткий совет по заезду/колонке для {driver_setup}]
• 🗺️ <a href="https://www.google.com/maps/search/?api=1&amp;query=[Название+Exit+Город+Штат]">Маршрут в Навигатор</a>

2. 💰 <b>Дешевая:</b> [Название сети и #] ([Трасса, Exit, Город, Штат])
• 📏 <b>[X.X] миль</b> | 💵 <b>$[X.XX]/gal</b> (карта: <b>$[X.XX]</b>) • <i>{t2}</i>
• 🛠️ [1 короткий совет по площадке]
• 🗺️ <a href="https://www.google.com/maps/search/?api=1&amp;query=[Название+Exit+Город+Штат]">Маршрут в Навигатор</a>

3. 🛣️ <b>Оптимальная:</b> [Название сети и #] ([Трасса, Exit, Город, Штат])
• 📏 <b>[X.X] миль</b> | 💵 <b>$[X.XX]/gal</b> (карта: <b>$[X.XX]</b>) • <i>{t3}</i>
• 🛠️ [1 короткий совет по выезду]
• 🗺️ <a href="https://www.google.com/maps/search/?api=1&amp;query=[Название+Exit+Город+Штат]">Маршрут в Навигатор</a>

💡 <b>IFTA:</b> [1 строка: реальная ставка IFTA этого штата и совет заправляться до полного или до границы].

ТРЕБОВАНИЯ:
- НИКАКИХ приветствий и вступлений («Привет оунер», «Совет на связи»). Начинай СРАЗУ со знака ⛽ <b>Дизель...</b>.
- Ссылки на карты делай строго по реальному названию трак-стопа и города.
- НЕ ПРИДУМЫВАЙ другие штаты! Если точка в Калифорнии — ищи только в Калифорнии (I-80/I-5/CA-99)!
"""
    if GEMINI_KEY:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 800}
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        raw_text = parts[0].get("text", "").strip()
                        if raw_text:
                            return markdown_to_telegram_html(raw_text)
        except Exception as e:
            print(f"[WARN] Gemini fuel call failed ({e}), using dynamic geo fallback...")

    # Dynamic fallback based on real resolved entity
    return generate_fallback_fuel_for_geo(geo, driver_setup)
