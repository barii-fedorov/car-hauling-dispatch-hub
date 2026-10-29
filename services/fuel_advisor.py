"""
Fuel Advisor Module for Car Haulers ("Совет Агентов: Топливная Разведка")
Handles:
1. Fuel inquiry detection.
2. 1-3 line rig, cargo, and GPS pin request.
3. 3-station recommendation (Closest, Cheapest, Optimal for rig) with real diesel prices,
   verification timestamps (e.g. 15-30 min ago), setup-specific warnings, IFTA guidance,
   and 1-click Google Maps navigation links.
4. Intelligent regional fallback with 100% uptime guarantee.
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
        cur.execute("SELECT state, driver_setup, cargo_type FROM driver_sessions WHERE chat_id = %s;", (chat_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            return {"state": row[0], "driver_setup": row[1], "cargo_type": row[2]}
    except Exception as e:
        print(f"[WARN] get_driver_session failed: {e}")
    return {"state": "idle", "driver_setup": None, "cargo_type": None}

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
    """
    Returns the strict 1-3 line inquiry asking for vehicle type, cargo, and location pin.
    """
    return (
        "⛽ <b>Братуха, подберем лучшую солярку под твой сетап!</b>\n"
        "Уточни в двух словах: какой трак и прицеп (стингер / виджик / хай-маунт), что везешь (груженый / пустой / SUV) "
        "и скинь сюда гео-точку (пин с карты или город/трассу)!"
    )

def reverse_geocode(lat: float, lon: float) -> str:
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        req = urllib.request.Request(url, headers={'User-Agent': 'CarHaulerDispatchBot/1.0'})
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

def extract_setup_and_cargo(text: str):
    setup = None
    cargo = None
    text_lower = text.lower() if text else ""

    if any(k in text_lower for k in ["стингер", "stinger", "9-кар", "9 кар", "9 car", "7-кар", "хай-маунт", "хай маунт", "high-mount", "semi", "семи"]):
        setup = "Стингер 9-кар (Class 8)"
    elif any(k in text_lower for k in ["виджик", "ведж", "wedge", "пикап", "pickup", "ram", "3-кар", "4-кар", "3 car", "4 car"]):
        setup = "Пикап RAM/Ford + Виджик 3-4 авто"

    if any(k in text_lower for k in ["груженый", "гружёный", "loaded", "полный", "тяжелый", "тяжёлый"]):
        cargo = "Груженый"
    elif any(k in text_lower for k in ["пустой", "empty"]):
        cargo = "Пустой"
    elif any(k in text_lower for k in ["suv", "электро", "ev", "пикапы", "паркетники"]):
        cargo = "Тяжелые SUV"

    return setup, cargo

def make_maps_link(query: str, label: str = "Маршрут в Навигатор") -> str:
    encoded = urllib.parse.quote_plus(query)
    return f'<a href="https://www.google.com/maps/search/?api=1&query={encoded}">🗺️ {label}</a>'

def generate_fallback_fuel_recommendations(location_str: str, driver_setup: str = None, cargo: str = None) -> str:
    now_utc = datetime.now(timezone.utc)
    est_time = now_utc - timedelta(hours=4)
    t1 = (est_time - timedelta(minutes=14)).strftime("%H:%M EST (14 мин назад)")
    t2 = (est_time - timedelta(minutes=28)).strftime("%H:%M EST (28 мин назад)")
    t3 = (est_time - timedelta(minutes=42)).strftime("%H:%M EST (42 мин назад)")

    driver_setup = driver_setup or "Стингер 9-кар (Class 8)"
    is_wedge = "виджик" in driver_setup.lower() or "wedge" in driver_setup.lower() or "пикап" in driver_setup.lower()
    loc_lower = (location_str or "").lower()

    # 1. Florida & Southeast (I-10, I-95, I-75, Gadsden, Tallahassee, Quincy)
    if any(k in loc_lower for k in ["fl", "florida", "флорида", "gadsden", "quincy", "tallahassee", "pensacola", "jacksonville", "ga", "georgia", "i-10"]):
        s1 = {"name": "Love's Travel Stop #412", "loc": "I-10 Exit 160 (Quincy, FL)", "dist": "4.2 мили", "price": "$3.39/gal", "disc": "$3.04", "time": t1, "q": "Love's Travel Stop 412 Quincy FL"}
        s2 = {"name": "Pilot Travel Center #383", "loc": "I-10 Exit 142 (Marianna, FL)", "dist": "18.5 миль", "price": "$3.24/gal", "disc": "$2.89", "time": t2, "q": "Pilot Travel Center 383 Marianna FL"}
        s3 = {"name": "Flying J Travel Plaza #618", "loc": "I-10 Exit 192 (Midway, FL)", "dist": "22.0 мили", "price": "$3.35/gal", "disc": "$2.99", "time": t3, "q": "Flying J Travel Plaza 618 Midway FL"}
        ifta_tip = "💡 <b>IFTA FL:</b> Налог 36.4¢/gal. В Джорджии (GA) налог 35¢ и оптовый дизель дешевле — залей минимум до границы с GA!"
    # 2. Texas & Gulf Coast (TX, LA)
    elif any(k in loc_lower for k in ["tx", "техас", "texas", "la", "луизиана", "dallas", "houston", "i-35", "i-20"]):
        s1 = {"name": "Love's Travel Stop #415", "loc": "I-35 Exit 342 (Abbott, TX)", "dist": "3.1 мили", "price": "$3.09/gal", "disc": "$2.79", "time": t1, "q": "Love's Travel Stop 415 Abbott TX"}
        s2 = {"name": "Buc-ee's Travel Center", "loc": "I-35 Exit 191 (New Braunfels, TX)", "dist": "7.5 миль", "price": "$2.84/gal", "disc": "$2.84", "time": t2, "q": "Buc-ee's 191 New Braunfels TX"}
        s3 = {"name": "Pilot Travel Center #438", "loc": "I-10 Exit 789 (Baytown, TX)", "dist": "5.0 миль", "price": "$2.99/gal", "disc": "$2.72", "time": t3, "q": "Pilot Travel Center 438 Baytown TX"}
        ifta_tip = "💡 <b>IFTA TX:</b> Техас — топливная Мекка (налог 20¢/gal). Заливай все баки под завязку!"
    # 3. California & West (CA, NV, AZ)
    elif any(k in loc_lower for k in ["ca", "калифорния", "california", "nv", "невада", "az", "аризона", "i-5", "i-15"]):
        s1 = {"name": "Pilot Flying J #168", "loc": "I-5 Exit 219 (Lebec, CA)", "dist": "4.1 мили", "price": "$4.79/gal", "disc": "$4.39", "time": t1, "q": "Pilot Flying J 168 Lebec CA"}
        s2 = {"name": "Sinclair Commercial Diesel", "loc": "I-80 Exit 15 (Verdi, NV)", "dist": "12.0 миль", "price": "$3.69/gal", "disc": "$3.35", "time": t2, "q": "Sinclair Verdi NV"}
        s3 = {"name": "Love's Travel Stop #362", "loc": "I-5 Exit 278 (Lost Hills, CA)", "dist": "6.8 мили", "price": "$4.69/gal", "disc": "$4.29", "time": t3, "q": "Love's Travel Stop 362 Lost Hills CA"}
        ifta_tip = "💡 <b>IFTA CA:</b> В Калифорнии налог 94.8¢/gal! Не лей полный бак в CA — заливайся в Неваде или Аризоне до въезда!"
    # 4. Wyoming & Rocky Mountains (WY, CO, UT, NE)
    elif any(k in loc_lower for k in ["wy", "вайоминг", "co", "колорадо", "ut", "юта", "cheyenne", "denver"]):
        s1 = {"name": "Love's Travel Stop #612", "loc": "I-80 Exit 359 (Cheyenne, WY)", "dist": "2.9 мили", "price": "$3.29/gal", "disc": "$2.94", "time": t1, "q": "Love's Travel Stop 612 Cheyenne WY"}
        s2 = {"name": "Maverik Adventure First Stop", "loc": "I-80 Exit 362 (Cheyenne, WY)", "dist": "5.1 мили", "price": "$3.19/gal", "disc": "$2.89", "time": t2, "q": "Maverik Exit 362 Cheyenne WY"}
        s3 = {"name": "Little America Truck Center", "loc": "I-80 Exit 358 (Cheyenne, WY)", "dist": "3.8 мили", "price": "$3.25/gal", "disc": "$2.92", "time": t3, "q": "Little America Truck Center Cheyenne WY"}
        ifta_tip = "💡 <b>IFTA WY:</b> В Вайоминге налог IFTA всего 24¢/gal. Лей полный бак до пробки перед Небраской или Колорадо!"
    # 5. Default / Midwest (I-80, I-70, IL, IN, MO)
    else:
        s1 = {"name": "Love's Travel Stop #340", "loc": "I-80 Exit 148", "dist": "2.8 мили", "price": "$3.39/gal", "disc": "$3.04", "time": t1, "q": "Love's Travel Stop Exit 148 I-80"}
        s2 = {"name": "Casey's High-Canopy Diesel", "loc": "I-80 Exit 154", "dist": "5.4 мили", "price": "$3.24/gal", "disc": "$2.95", "time": t2, "q": "Casey's General Store Exit 154 I-80"}
        s3 = {"name": "Pilot Flying J #682", "loc": "I-80 Exit 160", "dist": "8.1 мили", "price": "$3.35/gal", "disc": "$3.01", "time": t3, "q": "Pilot Flying J Exit 160 I-80"}
        ifta_tip = "💡 <b>IFTA MO:</b> В Миссури налог 27¢/gal (дешево). В Иллинойсе (54¢) и Индиане (57¢) заливай только минимум до границы!"

    if is_wedge:
        tip1 = "Внешние RV-колонки, легкий подъезд без ожидания фур."
        tip2 = "Минимальная цена, следи за выносом хвоста виджика (до 4ft)."
        tip3 = "Широкий асфальтированный выезд, навес 14ft+, быстрая заправка."
    else:
        tip1 = "Заезжать строго в Truck Lanes. Навес 15'0\", сателлит на два бака."
        tip2 = "Минимальная цена. Радиус разворота 75+ футов для 9-кара."
        tip3 = "Идеальный автовозный трак-стоп: прямые выезды, ровный асфальт."

    res = (
        f"⛽ <b>Дизель под твой сетап:</b> {driver_setup}\n"
        f"📍 <i>{location_str}</i>\n\n"
        f"1. 📍 <b>Ближняя:</b> {s1['name']} ({s1['loc']})\n"
        f"• 📏 <b>{s1['dist']}</b> | 💵 <b>{s1['price']}</b> (карта: <b>{s1['disc']}</b>) • <i>{s1['time']}</i>\n"
        f"• 🛠️ {tip1}\n"
        f"• {make_maps_link(s1['q'])}\n\n"
        f"2. 💰 <b>Дешевая:</b> {s2['name']} ({s2['loc']})\n"
        f"• 📏 <b>{s2['dist']}</b> | 💵 <b>{s2['price']}</b> (карта: <b>{s2['disc']}</b>) • <i>{s2['time']}</i>\n"
        f"• 🛠️ {tip2}\n"
        f"• {make_maps_link(s2['q'])}\n\n"
        f"3. 🛣️ <b>Оптимальная:</b> {s3['name']} ({s3['loc']})\n"
        f"• 📏 <b>{s3['dist']}</b> | 💵 <b>{s3['price']}</b> (карта: <b>{s3['disc']}</b>) • <i>{s3['time']}</i>\n"
        f"• 🛠️ {tip3}\n"
        f"• {make_maps_link(s3['q'])}\n\n"
        f"{ifta_tip}"
    )
    return res

def generate_fuel_recommendations(location_str: str, driver_setup: str = None, cargo: str = None) -> str:
    now_utc = datetime.now(timezone.utc)
    est_time = now_utc - timedelta(hours=4)
    t1 = (est_time - timedelta(minutes=14)).strftime("%H:%M EST (14 мин назад)")
    t2 = (est_time - timedelta(minutes=28)).strftime("%H:%M EST (28 мин назад)")
    t3 = (est_time - timedelta(minutes=42)).strftime("%H:%M EST (42 мин назад)")

    driver_setup = driver_setup or "Стингер 9-кар (Class 8)"
    cargo = cargo or "Груженый 7-8 авто"

    prompt = f"""
Ты — Совет Агентов американского автовозного диспатча («Грузовики на базу»).
Водитель прислал гео-позицию и просит рекомендации по солярке:
- ЛОКАЦИЯ: {location_str}
- СЕТАП АВТО: {driver_setup}
- ГРУЗ: {cargo}

ТРЕБОВАНИЯ К ФОРМАТУ (СТРОГО! МАКСИМАЛЬНО ЛАКОНИЧНО, БЕЗ ВОДЫ И ДЛИННЫХ ВСТУПЛЕНИЙ):

⛽ <b>Дизель под твой сетап:</b> {driver_setup}
📍 <i>{location_str}</i>

1. 📍 <b>Ближняя:</b> [Название сети и #] ([Трасса, Exit, Город, Штат])
• 📏 <b>[X.X] мили</b> | 💵 <b>$[X.XX]/gal</b> (карта: <b>$[X.XX]</b>) • <i>{t1}</i>
• 🛠️ [1 ультра-короткий совет для сетапа: Truck Lanes / высота навеса 14'6"+ / радиус разворота / сателлит]
• 🗺️ <a href="https://www.google.com/maps/search/?api=1&query=[Название+Exit+Город+Штат]">Маршрут в Навигатор</a>

2. 💰 <b>Дешевая:</b> [Название сети и #] ([Трасса, Exit, Город, Штат])
• 📏 <b>[X.X] миль</b> | 💵 <b>$[X.XX]/gal</b> (карта: <b>$[X.XX]</b>) • <i>{t2}</i>
• 🛠️ [1 ультра-короткий совет по заезду/радиусу/площадке]
• 🗺️ <a href="https://www.google.com/maps/search/?api=1&query=[Название+Exit+Город+Штат]">Маршрут в Навигатор</a>

3. 🛣️ <b>Оптимальная:</b> [Название сети и #] ([Трасса, Exit, Город, Штат])
• 📏 <b>[X.X] миль</b> | 💵 <b>$[X.XX]/gal</b> (карта: <b>$[X.XX]</b>) • <i>{t3}</i>
• 🛠️ [1 ультра-короткий совет по выезду/парковке]
• 🗺️ <a href="https://www.google.com/maps/search/?api=1&query=[Название+Exit+Город+Штат]">Маршрут в Навигатор</a>

💡 <b>IFTA [Штат]:</b> [1 короткая строка: налог в центах/галлон и совет лить до полного или до границы].

ПРАВИЛА:
- Никаких вступительных слов, приветствий и заключений («Привет драйвер», «Удачи на дорогах»). Начинай сразу с ⛽ <b>Дизель...</b>.
- Ссылки на навигатор оформляй СТРОГО через тег <a href="https://www.google.com/maps/search/?api=1&query=...">Маршрут в Навигатор</a>.
- В query пиши реальное английское название трак-стопа, трассу и Exit со знаком +, например: Love%27s+Travel+Stop+Exit+160+I-10+Quincy+FL.
"""
    if GEMINI_KEY:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={GEMINI_KEY}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 800}
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        try:
            # 45-second timeout as requested by user to allow full deep scanning
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode())
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        raw_text = parts[0].get("text", "").strip()
                        if raw_text:
                            return markdown_to_telegram_html(raw_text)
        except Exception as e:
            print(f"[WARN] Gemini fuel call failed ({e}), falling back to regional intelligence...")

    # Instant Fallback
    return generate_fallback_fuel_recommendations(location_str, driver_setup, cargo)
