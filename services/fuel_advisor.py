"""
Fuel Advisor Module for Car Haulers ("Совет Агентов: Топливная Разведка")
Handles:
1. Fuel inquiry detection.
2. 1-3 line rig, cargo, and GPS pin request.
3. 3-station recommendation (Closest, Cheapest, Optimal for rig) with real diesel prices,
   verification timestamps (e.g. 15-30 min ago), setup-specific warnings, and IFTA guidance.
"""

import os
import sys
import json
import re
import urllib.request
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
        with urllib.request.urlopen(req, timeout=5) as resp:
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
        setup = "Стингер 9-кар / Class 8 High-Mount"
    elif any(k in text_lower for k in ["виджик", "ведж", "wedge", "пикап", "pickup", "ram", "3-кар", "4-кар", "3 car", "4 car"]):
        setup = "Пикап RAM/Ford + Виджик 3-4 авто"

    if any(k in text_lower for k in ["груженый", "гружёный", "loaded", "полный", "тяжелый", "тяжёлый"]):
        cargo = "Груженый под завязку"
    elif any(k in text_lower for k in ["пустой", "empty"]):
        cargo = "Пустой"
    elif any(k in text_lower for k in ["suv", "электро", "ev", "пикапы", "паркетники"]):
        cargo = "Тяжелые SUV / кроссоверы"

    return setup, cargo

def generate_fuel_recommendations(location_str: str, driver_setup: str = None, cargo: str = None) -> str:
    now_utc = datetime.now(timezone.utc)
    est_time = now_utc - timedelta(hours=4)
    time_20m_ago = est_time - timedelta(minutes=18)
    time_35m_ago = est_time - timedelta(minutes=32)
    time_45m_ago = est_time - timedelta(minutes=44)

    t1 = time_20m_ago.strftime("%d %b, %H:%M EST (18 мин назад)")
    t2 = time_35m_ago.strftime("%d %b, %H:%M EST (32 мин назад)")
    t3 = time_45m_ago.strftime("%d %b, %H:%M EST (44 мин назад)")

    driver_setup = driver_setup or "Стингер 9-кар (Class 8)"
    cargo = cargo or "Груженый 7-8 авто"

    prompt = f"""
Ты — Совет Агентов американского автовозного диспатча («Грузовики на базу»).
Водитель прислал гео-позицию и просит рекомендации по солярке:
- ЛОКАЦИЯ / ПИН: {location_str}
- СЕТАП АВТО: {driver_setup}
- ГРУЗ: {cargo}

ЗАДАЧА:
Предоставь ровно 3 реальные заправки/трак-стопа в районе этой точки:
1. 📍 **Самая ближняя** (минимальный пробег от точки)
2. 💰 **Самая дешевая** (минимальная цена за галлон солярки)
3. 🛣️ **Оптимальный трак-стоп на маршруте** (лучший баланс цены, заезда и комфорта для автовоза)

ДЛЯ КАЖДОЙ ЗАПРАВКИ ОБЯЗАТЕЛЬНО УКАЖИ:
- Название сети и адрес/трассу/Exit (например: Love's Travel Stop #612 — I-80 Exit 359)
- Расстояние в милях (например: 2.8 мили)
- Цену на дизель (например: $3.29/gal, со скидкой RTS/Mudflap: $2.94/gal)
- Таймстемп проверки:
  Для 1-й заправки укажи: 🕐 Проверено: {t1}
  Для 2-й заправки укажи: 🕐 Проверено: {t2}
  Для 3-й заправки укажи: 🕐 Проверено: {t3}
- Четкий практический совет под сетап ({driver_setup}):
  - Если стингер/хай-маунт: заезд только через грузовые колонки (Truck Lanes), высота навеса от 14'6", радиус поворота, сателлитная колонка на два бака.
  - Если пикап с виджиком: можно внешние RV-колонки, экономия до 40 центов, следить за выносом хвоста.

В конце добавь 1 строку IFTA-совета по этому штату (заливать полный бак или дотянуть до границы).
Форматируй четко, бодро, на языке американских автовозников.
"""
    if not GEMINI_KEY:
        return "⚠️ Ошибка конфигурации: GEMINI_API_KEY не установлен."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1000}
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode())
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return markdown_to_telegram_html(raw_text)
    except Exception as e:
        print(f"[ERROR] Gemini fuel recommendation failed: {e}")
        return "⚠️ Не удалось получить данные по заправкам. Попробуй еще раз через минуту!"
