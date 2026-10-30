"""
Dynamic Repair & Roadside Mechanic Advisor for Car Haulers (Open Maps & Gemini Powered)
Features:
1. Native Telegram Geolocation pin & address resolution via OpenStreetMap Nominatim.
2. Problem Classification via Gemini:
   - 'truck_rig': Car hauler equipment breakdown (hydraulics, hoses, ramps, welding, air, DPF regen, tires).
   - 'cargo_stealth': Client vehicle damaged on trailer (PDR dent removal, scratch touchup, rim curb rash, glass chip).
     Includes stealth protocol to repair without client/broker noticing and without Carfax/insurance record.
3. Live OpenStreetMap POI search for real local shops (Nominatim bounded search).
4. Verified private car-hauler mechanic network from PostgreSQL (Cash/Zelle, no DOT reports).
5. 24/7 Emergency Heavy Duty commercial roadside contacts.
"""

import os
import math
import re
import json
import urllib.request
import urllib.parse

try:
    import psycopg2
except ImportError:
    psycopg2 = None

try:
    from services.model_router import query_model_with_failover
except ImportError:
    from model_router import query_model_with_failover

try:
    from services.route_advisor import dynamic_geocode, reverse_geocode_osm, US_STATE_NAME_TO_CODE
except ImportError:
    from route_advisor import dynamic_geocode, reverse_geocode_osm, US_STATE_NAME_TO_CODE

PG_HOST = os.environ.get("POSTGRES_HOST", "postgres")
PG_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
PG_USER = os.environ.get("POSTGRES_USER", "dispatch_admin")
PG_PASS = os.environ.get("POSTGRES_PASSWORD", "DispatchSecurePass2026!_pg")
PG_DB = os.environ.get("POSTGRES_DB", "dispatch_hub")

def calculate_distance_miles(lat1, lon1, lat2, lon2):
    """Haversine distance in statute miles."""
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 1)

def get_db_connection():
    if not psycopg2:
        return None
    try:
        return psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB)
    except Exception as e:
        print(f"[WARN] DB connection failed in repair_service: {e}")
        return None

def classify_repair_request_with_gemini(raw_text: str) -> dict:
    """
    Classifies repair intent into:
    - 'cargo_stealth': Client vehicle damage to be repaired discreetly (PDR, scratches, rims, glass)
    - 'truck_rig': Car hauler equipment breakdown (hydraulics, hoses, welding, air, DPF, tires)
    """
    prompt = f"""You are an expert car hauler logistics dispatcher in the USA.
A truck driver requested repair or mechanic assistance: "{raw_text}".

Analyze the problem and location:
1. Target:
   - "cargo_stealth": The driver damaged a client's vehicle (cargo loaded on the trailer - scratch, dent, rim scuff, windshield chip, bumper rub) and needs it repaired urgently and discreetly before delivery so the broker/dealer/client doesn't notice and no insurance claim is filed.
   - "truck_rig": The driver's own car hauler equipment (semi-truck, trailer, hydraulic hoses, ramps, air brakes, DPF regen, welding, tires) broke down on the road.
2. Category:
   - If cargo_stealth: "pdr_dents" (вмятина), "scratch_paint" (царапина/бампер), "wheel_rim" (диск/бордюрка), "windshield_chip" (скол стекла), or "general_cargo".
   - If truck_rig: "hydraulic" (шланги/цилиндры), "welding" (рампа/алюминий), "air_brakes", "engine_regen", "tires", or "general_truck".
3. Location:
   - Extract location/city/address if mentioned. If none mentioned, leave location empty.
4. OSM search keywords:
   - 2-3 English search queries to locate nearby shops on OpenStreetMap (e.g. ["paintless dent repair", "auto body shop", "wheel repair"] or ["truck repair", "hydraulic equipment", "semi truck roadside"]).

Return strictly a JSON object:
{{
  "target": "cargo_stealth" or "truck_rig",
  "category": "...",
  "location": "...",
  "problem_ru": "Краткое понятное описание проблемы на русском (например: Вмятина на двери клиентского авто или Лопнул гидрошланг подъема рампы)",
  "osm_queries": ["query 1", "query 2"]
}}
Output ONLY valid raw JSON without markdown."""

    try:
        raw_res, _ = query_model_with_failover(prompt, context_type="normalization")
        if raw_res:
            clean = re.sub(r'^```json\s*', '', raw_res.strip())
            clean = re.sub(r'\s*```$', '', clean).strip()
            return json.loads(clean)
    except Exception as e:
        print(f"[WARN] Gemini repair classification error: {e}")

    # Fallback rule-based classification
    low = raw_text.lower()
    is_cargo = any(w in low for w in [
        "клиент", "груз", "вмятин", "царапин", "диск", "бордюрк", "скол", "стекл",
        "бампер", "покрас", "пдр", "pdr", "не заметил", "скрыт", "тихо", "клиентск"
    ])
    return {
        "target": "cargo_stealth" if is_cargo else "truck_rig",
        "category": "pdr_dents" if is_cargo else "hydraulic",
        "location": "",
        "problem_ru": raw_text,
        "osm_queries": ["paintless dent repair", "auto body shop"] if is_cargo else ["truck repair", "hydraulic equipment"]
    }

def search_osm_repair_shops(lat: float, lon: float, queries: list, limit: int = 3) -> list:
    """
    Searches OpenStreetMap Nominatim API for real repair shops around coordinates.
    """
    if lat is None or lon is None:
        return []

    shops = []
    delta = 0.35  # ~25 miles bounding box
    viewbox = f"{lon-delta},{lat+delta},{lon+delta},{lat-delta}"

    for q in (queries or ["auto repair"]):
        try:
            url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(q)}&format=json&viewbox={viewbox}&bounded=1&limit={limit}&addressdetails=1"
            req = urllib.request.Request(url, headers={'User-Agent': 'CarHaulerDispatchBot/2.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                for item in data:
                    item_lat = float(item["lat"])
                    item_lon = float(item["lon"])
                    dist = calculate_distance_miles(lat, lon, item_lat, item_lon)

                    addr = item.get("address", {})
                    road = addr.get("road") or ""
                    house = addr.get("house_number") or ""
                    city = addr.get("city") or addr.get("town") or addr.get("village") or ""
                    st = addr.get("state_code", "").upper() or addr.get("state", "")

                    addr_line = f"{house} {road}, {city}, {st}".strip(", ") if road else city

                    name = item.get("name") or (item.get("display_name", "").split(",")[0])
                    if not any(s["name"] == name for s in shops):
                        shops.append({
                            "name": name,
                            "address": addr_line or f"{item_lat:.4f}, {item_lon:.4f}",
                            "lat": item_lat,
                            "lon": item_lon,
                            "distance_miles": dist,
                            "category": q
                        })
            if len(shops) >= limit:
                break
        except Exception as e:
            print(f"[WARN] OSM shop search error for '{q}': {e}")

    shops.sort(key=lambda x: x["distance_miles"])
    return shops[:limit]

def find_private_car_hauler_mechanics(lat: float, lon: float, state: str = None, limit: int = 2) -> list:
    """
    Searches internal verified car hauler mechanics (Cash/Zelle, no DOT reports).
    """
    conn = get_db_connection()
    if not conn:
        return []

    results = []
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT mechanic_id, name, contact_phone, languages, city, state, corridor,
                   latitude, longitude, coverage_radius_miles, specialties, payment_methods, notes
            FROM car_hauler_mechanics;
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        for r in rows:
            m = {
                "name": r[1],
                "phone": r[2],
                "languages": r[3],
                "city": r[4],
                "state": r[5],
                "corridor": r[6],
                "lat": r[7],
                "lon": r[8],
                "radius": r[9],
                "specialties": r[10] or [],
                "payment": r[11] or ["Cash", "Zelle"],
                "notes": r[12] or ""
            }
            if lat is not None and lon is not None and m["lat"] and m["lon"]:
                dist = calculate_distance_miles(lat, lon, m["lat"], m["lon"])
                m["distance_miles"] = dist
                if dist <= max(m.get("radius", 90), 120):
                    results.append(m)
            elif state and m["state"] == state.upper():
                m["distance_miles"] = None
                results.append(m)

        results.sort(key=lambda x: x.get("distance_miles") or 999)
    except Exception as e:
        print(f"[WARN] Error fetching private mechanics: {e}")
        if conn:
            conn.close()

    return results[:limit]

def handle_repair_inquiry(
    text: str = "",
    lat: float = None,
    lon: float = None,
    location_str: str = None
) -> str:
    """
    Main entry point for dynamic, Open Maps & Gemini-driven mechanic search.
    Handles both truck rig repairs and stealth client cargo repairs.
    """
    # 1. Classify problem with Gemini
    classification = classify_repair_request_with_gemini(text)
    target = classification.get("target", "truck_rig")
    category = classification.get("category", "")
    problem_ru = classification.get("problem_ru", text or "Техпомощь")
    osm_queries = classification.get("osm_queries", ["car repair"])
    extracted_loc = classification.get("location", "")

    # 2. Determine Coordinates
    geo_point = None
    if lat is not None and lon is not None:
        geo_point = {"lat": lat, "lon": lon, "display": location_str or f"{lat:.4f}, {lon:.4f}"}
    elif extracted_loc:
        geo_point = dynamic_geocode(extracted_loc)
    elif location_str:
        geo_point = dynamic_geocode(location_str)

    curr_lat = geo_point["lat"] if geo_point else None
    curr_lon = geo_point["lon"] if geo_point else None
    loc_display = geo_point.get("display") if geo_point else (extracted_loc or location_str or "США")
    curr_state = geo_point.get("state") if geo_point else None

    # 3. Search OpenStreetMap for real local shops
    osm_shops = search_osm_repair_shops(curr_lat, curr_lon, osm_queries, limit=3) if curr_lat else []

    # 4. Search private car-hauler database if rig repair
    private_mechs = find_private_car_hauler_mechanics(curr_lat, curr_lon, curr_state, limit=2) if (target == "truck_rig" and curr_lat) else []

    # 5. Format dedicated response depending on target
    if target == "cargo_stealth":
        return _format_cargo_stealth_response(problem_ru, loc_display, osm_shops, curr_lat, curr_lon)
    else:
        return _format_truck_rig_response(problem_ru, loc_display, osm_shops, private_mechs, curr_lat, curr_lon)

def _format_cargo_stealth_response(problem_ru: str, loc_display: str, osm_shops: list, lat: float, lon: float) -> str:
    lines = [
        "🤫 <b>СРОЧНЫЙ РЕМОНТ АВТО КЛИЕНТА (STEALTH / БЕЗ ОТМЕТОК В CARFAX)</b>\n",
        f"📍 <b>Локация:</b> <b>{loc_display}</b>",
        f"🎯 <b>Задача:</b> <i>{problem_ru}</i>\n",
        "🔍 <b>Ближайшие специализированные мастерские (Open Maps):</b>"
    ]

    if osm_shops:
        for idx, s in enumerate(osm_shops, 1):
            dist_str = f" (~{s['distance_miles']} миль)" if s.get("distance_miles") else ""
            lines.append(
                f"<b>{idx}. 🛠️ {s['name']}</b>{dist_str}\n"
                f"• Адрес: {s['address']}\n"
                f"• Направление: {s['category'].title()}"
            )
    else:
        lines.append("• <i>Мастера рядом ищутся по направлениям: Paintless Dent Repair (PDR) / Mobile Scratch Doctor / Wheel Refinishing.</i>")

    lines.extend([
        "",
        "🛡️ <b>ПРОТОКОЛ ДИСПЕТЧЕРА: КАК СДАТЬ АВТО БЕЗ СПИСАНИЙ И СТРАХОВЫХ КЛЕЙМОВ:</b>",
        "1. <b>Технология ремонта:</b> Настаивай исключительно на <b>PDR</b> (беспокрасочное удаление вмятин) или микрополировке/локальном touch-up. Никаких шпаклевок и снятия панелей — иначе толщиномер на приемке у дилера покажет вторичный окрас!",
        "2. <b>Оплата строго Cash / Zelle:</b> Категорически <b>НЕ указывай VIN клиентского автомобиля</b> в квитанциях или счетах, чтобы инцидент не улетел в базы Carfax / AutoCheck.",
        "3. <b>Маскировка пыли:</b> Не мой всю машину перед разгрузкой! Чистая машина привлекает инспектора с фонариком. Очисти только зону ремонта и аккуратно выровняй естественный слой пыли по стыкам деталей.",
        "4. <b>Сверка с eBOL:</b> Срочно проверь фотографии в инспекционном листе с погрузки (origin eBOL / Gate Pass). Если повреждение или царапина уже были зафиксированы на аукционе (Copart/Manheim), ты не несешь ответственности — покажи отметку брокеру!"
    ])

    return "\n".join(lines)

def _format_truck_rig_response(problem_ru: str, loc_display: str, osm_shops: list, private_mechs: list, lat: float, lon: float) -> str:
    lines = [
        "🔧 <b>ТЕХПОМОЩЬ НА ТРАССЕ: РЕМОНТ АВТОВОЗА (COMMERCIAL TRUCK REPAIR)</b>\n",
        f"📍 <b>Локация:</b> <b>{loc_display}</b>",
        f"⚠️ <b>Проблема:</b> <i>{problem_ru}</i>\n"
    ]

    # 1. Private Russian-speaking network (Cash/Zelle, no DOT)
    if private_mechs:
        lines.append("🛠️ <b>Проверенные русскоязычные мастера по автовозам (Cash/Zelle):</b>")
        for idx, m in enumerate(private_mechs, 1):
            dist_str = f" (~{m['distance_miles']} миль)" if m.get("distance_miles") else ""
            phone_clean = re.sub(r'[^\d+]', '', m['phone'])
            specs = ", ".join(m['specialties'][:3])
            lines.append(
                f"<b>{idx}. 👨‍🔧 {m['name']}</b>{dist_str}\n"
                f"• 📞 <b>Контакт:</b> <a href=\"tel:{phone_clean}\">{m['phone']}</a> ({m['languages']})\n"
                f"• 💵 <b>Оплата:</b> Cash / Zelle (Без репортов в базы DOT)\n"
                f"• ⚙️ <b>Профиль:</b> {specs} | {m['notes']}"
            )
        lines.append("")

    # 2. Local Open Maps shops
    if osm_shops:
        lines.append("📍 <b>Ближайшие трак-сервисы и мастерские (Open Maps):</b>")
        for idx, s in enumerate(osm_shops, 1):
            dist_str = f" (~{s['distance_miles']} миль)" if s.get("distance_miles") else ""
            lines.append(
                f"<b>• {s['name']}</b>{dist_str}\n"
                f"  Адрес: {s['address']}"
            )
        lines.append("")

    # 3. 24/7 National Emergency Commercial Roadside contacts
    lines.extend([
        "🚨 <b>Круглосуточная коммерческая техпомощь 24/7:</b>",
        "• 📞 <b>PIRTEK Mobile Hydraulic Hoses:</b> <a href=\"tel:18002747835\">1-800-274-7835</a> <i>(Выездная завальцовка шлангов на обочине)</i>",
        "• 📞 <b>Love's Truck Care Roadside:</b> <a href=\"tel:18006875683\">1-800-687-5683</a>",
        "• 📞 <b>TA Commercial Truck Service:</b> <a href=\"tel:18008248762\">1-800-824-8762</a>\n",
        "💡 <b>Совет диспетчера:</b>",
        "• <b>Шланги гидравлики:</b> сними поврежденный кусок и сфотографируй маркировку (обычно 1/4\" или 3/8\", фитинги JIC 37°). У мобильного пресса на выезде должны быть нужные конусы.",
        "• <b>Сварка рампы:</b> требуй мастера со сваркой TIG/MIG по алюминию (6061 alloy), обычная стальная дуговая сварка треснет под весом кроссовера на втором деке.",
        "• Фиксируй ставку за выезд (road call fee) до отправки мастера на точку."
    ])

    return "\n".join(lines)
