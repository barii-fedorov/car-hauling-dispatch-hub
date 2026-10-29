"""
Repair Service Module for Car Haulers
Provides access to verified Russian-speaking mechanics, mobile roadside welders,
and hydraulic technicians across the US.
Strictly confidential: Cash/Zelle payments, no DOT out-of-service reporting, no insurance claims.
"""

import os
import math
import re
import psycopg2

PG_HOST = os.environ.get("POSTGRES_HOST", "postgres")
PG_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
PG_USER = os.environ.get("POSTGRES_USER", "dispatch_admin")
PG_PASS = os.environ.get("POSTGRES_PASSWORD", "DispatchSecurePass2026!_pg")
PG_DB = os.environ.get("POSTGRES_DB", "dispatch_hub")

def calculate_distance_miles(lat1, lon1, lat2, lon2):
    """
    Haversine distance in statute miles.
    """
    R = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_db_connection():
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB)

def find_mechanics(lat=None, lon=None, state=None, query_text="", limit=3):
    """
    Finds the best matching mechanics from PostgreSQL directory.
    Filters by distance (if coordinates present) or state/specialty.
    """
    conn = None
    results = []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT mechanic_id, name, contact_phone, languages, city, state, corridor,
                   latitude, longitude, coverage_radius_miles, is_mobile, has_shop,
                   specialties, payment_methods, no_dot_reports, trust_level, trust_score,
                   verified_reviews_count, notes
            FROM car_hauler_mechanics;
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        for r in rows:
            m = {
                "mechanic_id": r[0],
                "name": r[1],
                "contact_phone": r[2],
                "languages": r[3],
                "city": r[4],
                "state": r[5],
                "corridor": r[6],
                "lat": r[7],
                "lon": r[8],
                "radius": r[9],
                "is_mobile": r[10],
                "has_shop": r[11],
                "specialties": r[12] or [],
                "payment_methods": r[13] or ["Cash", "Zelle"],
                "no_dot_reports": r[14],
                "trust_level": r[15],
                "trust_score": float(r[16] or 4.9),
                "reviews_count": r[17] or 10,
                "notes": r[18] or ""
            }

            # Calculate distance if coords given
            if lat is not None and lon is not None:
                dist = calculate_distance_miles(lat, lon, m["lat"], m["lon"])
                m["distance_miles"] = round(dist, 1)
            else:
                m["distance_miles"] = None

            results.append(m)

    except Exception as e:
        print(f"[WARN] Error loading mechanics from DB: {e}")
        if conn:
            conn.close()
        return []

    # Filtering logic
    # 1. By distance if coords present (strictly within coverage radius or max 100 miles)
    if lat is not None and lon is not None:
        nearby = [m for m in results if m["distance_miles"] <= max(m.get("radius", 90), 100)]
        nearby.sort(key=lambda x: x["distance_miles"])
        return nearby[:limit]

    # 2. By State if provided
    if state:
        st_clean = state.strip().upper()
        state_matches = [m for m in results if m["state"].upper() == st_clean]
        if state_matches:
            return state_matches[:limit]

    # 3. By keyword in text (e.g. 'гидравлика', 'сварка', 'чикаго', 'техас', 'флорида')
    q_low = query_text.lower()
    matched = []
    for m in results:
        score = 0
        if m["state"].lower() in q_low or m["city"].lower() in q_low:
            score += 5
        if "гидравлик" in q_low and any("гидравлик" in s.lower() for s in m["specialties"]):
            score += 3
        if "сварк" in q_low and any("сварк" in s.lower() for s in m["specialties"]):
            score += 3
        if "дизел" in q_low and any("дизел" in s.lower() for s in m["specialties"]):
            score += 3
        if score > 0:
            matched.append((score, m))

    if matched:
        matched.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in matched[:limit]]

    # Default: return empty so we do not show distant mechanics across the country
    return []

def format_mechanics_response(mechanics: list, user_location_str: str = None) -> str:
    """
    Renders structured Telegram HTML card with real verified phone numbers, specialties, and cash status.
    """
    if not mechanics:
        loc_txt = f"в радиусе 100 миль от 📍 <b>{user_location_str}</b>" if user_location_str else "в данном регионе"
        return (
            f"🔧 <b>РЕМОНТ И ТЕХПОМОЩЬ НА ТРАССЕ:</b>\n\n"
            f"В базе {loc_txt} проверенных частных русскоязычных мастеров сейчас нет.\n\n"
            f"🚨 <b>Официальные круглосуточные 24/7 службы дорожной помощи для коммерческих траков:</b>\n"
            f"• 📞 <b>Love's Truck Care Roadside:</b> <a href=\"tel:18006875683\">1-800-687-5683</a> (1-800-OUR-LOVE)\n"
            f"• 📞 <b>TA Truck Service Commercial Roadside:</b> <a href=\"tel:18008248762\">1-800-824-8762</a>\n"
            f"• 📞 <b>Rush Truck Centers Mobile Tech:</b> <a href=\"tel:18557874327\">1-855-787-4327</a>\n"
            f"• 📞 <b>Bridgestone Emergency Fleet Support:</b> <a href=\"tel:18005600099\">1-800-560-0099</a>\n\n"
            f"💡 <b>Рекомендации диспетчера при заказе выезда:</b>\n"
            f"1. Сразу уточняй: <i>'Specialized car hauler / stinger on highway shoulder'</i> и точный характер проблемы (гидравлика/шланг, регенерация DPF, тормоза, воздух).\n"
            f"2. Согласуй фиксированную стоимость выезда (road call fee + почасовая ставка) до отправки мастера на точку.\n"
            f"3. Для поиска частного мастера через закрытую партнерскую сеть напиши запрос в диспетчерский чат."
        )

    loc_header = f"в районе 📍 <b>{user_location_str}</b>" if user_location_str else "по твоему направлению"

    lines = [
        f"🔧 <b>ПРОВЕРЕННЫЕ РУССКОЯЗЫЧНЫЕ МАСТЕРА ({loc_header}):</b>\n",
        "<i>Оплата Cash / Zelle, ремонт без репортов в DOT и без страховых клеймов.</i>\n"
    ]

    for idx, m in enumerate(mechanics, 1):
        dist_str = f"• 📍 <b>Дистанция:</b> ~{m['distance_miles']} миль (выезд по {m['corridor']})\n" if m.get("distance_miles") else f"• 📍 <b>Локация:</b> {m['city']}, {m['state']} ({m['corridor']})\n"
        phone_clean = re.sub(r'[^\d+]', '', m['contact_phone'])
        specs = ", ".join(m['specialties'][:3])
        pay = " / ".join(m['payment_methods'])

        lines.append(
            f"<b>{idx}. 🛠️ {m['name']}</b>\n"
            f"{dist_str}"
            f"• 📞 <b>Прямой контакт:</b> <a href=\"tel:{phone_clean}\">{m['contact_phone']}</a> (Язык: {m['languages']})\n"
            f"• 💵 <b>Оплата:</b> <b>{pay}</b> (Без отметок в базах DOT)\n"
            f"• ⚙️ <b>Профиль:</b> {specs}\n"
            f"• 💬 <i>{m['notes']}</i>\n"
        )

    lines.append(
        "💡 <b>Памятка:</b> Звони напрямую мастеру, уточняй модель автовоза (Cottrell, Boydstun, Kaufman, Infinity) и нужные фитинги перед выездом."
    )

    return "\n".join(lines)

def handle_repair_inquiry(text: str = "", lat: float = None, lon: float = None, location_str: str = None) -> str:
    """
    Main entry point for /repair and repair-related natural language inquiries.
    """
    # Extract state if mentioned (e.g. /repair IL or 'сломался в техасе')
    state = None
    state_match = re.search(r'\b(IL|PA|NJ|FL|TX|CA|GA|OH|IN|NY|NC)\b', text, re.IGNORECASE)
    if state_match:
        state = state_match.group(1).upper()
    else:
        # Check Russian names
        text_low = text.lower()
        if "чикаго" in text_low or "иллинойс" in text_low:
            state = "IL"
        elif "флорид" in text_low or "майами" in text_low or "орландо" in text_low:
            state = "FL"
        elif "техас" in text_low or "даллас" in text_low or "хьюстон" in text_low:
            state = "TX"
        elif "пенсильван" in text_low or "филадельфи" in text_low:
            state = "PA"
        elif "джерси" in text_low:
            state = "NJ"
        elif "калифорни" in text_low:
            state = "CA"
        elif "джорджи" in text_low or "атлант" in text_low:
            state = "GA"

    mechanics = find_mechanics(lat=lat, lon=lon, state=state, query_text=text, limit=3)
    formatted = format_mechanics_response(mechanics, user_location_str=location_str)
    try:
        from services.grounding_verifier import multi_agent_sense_check
        return multi_agent_sense_check(formatted, context_type="repair")
    except Exception:
        return formatted
