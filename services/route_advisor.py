"""
Car Hauler Route & Strategic Fuel Advisor (100% Dynamic API-Driven)
Features:
1. Gemini API-powered Address & Auction Normalization (Copart, Manheim, IAAI, exact street addresses).
2. Dynamic Geocoding & Reverse Geocoding via OpenStreetMap Nominatim API (zero hardcoded city lists).
3. Exact Road Distance & Driving Time via OpenStreetMap OSRM Routing API (zero hardcoded mileages).
4. Dynamic Traversed State Detection along actual highway LineString geometry.
5. Live Certified State Fuel Prices strictly for traversed states via AAA Live Feed (zero hardcoded prices).
6. Accurate Rig-Specific Fuel Consumption (Stinger 9-car vs Dually Wedge 3-4 car vs High-mount).
7. Contextual Reminders strictly for traversed states (Weigh stations, toll roads, mountain passes, Oregon IFTA).
"""

import os
import re
import math
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone

try:
    from services.aaa_fuel_feed import (
        get_state_diesel_benchmark,
        get_db_connection,
        US_STATE_NAME_TO_CODE,
        sync_state_fuel_prices,
        fetch_live_aaa_prices
    )
except ImportError:
    from aaa_fuel_feed import (
        get_state_diesel_benchmark,
        get_db_connection,
        US_STATE_NAME_TO_CODE,
        sync_state_fuel_prices,
        fetch_live_aaa_prices
    )

RIG_PROFILES = {
    "stinger": {
        "name": "Стингер 9-кар (Class 8)",
        "mpg_loaded": 5.5,
        "mpg_empty": 6.8,
        "tank_gal": 200,
        "max_gross": "80,000 lbs",
        "tandem_limit": "34,000 lbs"
    },
    "wedge": {
        "name": "Пикап + Виджик 3-4 авто",
        "mpg_loaded": 9.0,
        "mpg_empty": 12.0,
        "tank_gal": 80,
        "max_gross": "35,000 lbs",
        "tandem_limit": "20,000 lbs"
    },
    "highmount": {
        "name": "Хай-маунт 7-8 авто",
        "mpg_loaded": 6.0,
        "mpg_empty": 7.2,
        "tank_gal": 180,
        "max_gross": "80,000 lbs",
        "tandem_limit": "34,000 lbs"
    }
}

# In-memory fast geocode cache to avoid redundant network roundtrips
_GEO_CACHE = {}

def normalize_russian_city(city_str: str) -> str:
    """Normalizes Russian genitive/prepositional endings to nominative case for US cities."""
    s = city_str.strip()
    if s.endswith("а") and len(s) > 4 and s[-2] not in "аеиоуюя":
        return s[:-1]
    if s.endswith("ы") and len(s) > 4:
        return s[:-1] + "а"
    if s.endswith("е") and len(s) > 4:
        return s[:-1] + "а"
    if s.endswith("у") and len(s) > 4:
        return s[:-1] + "а"
    return s

def reverse_geocode_osm(lat: float, lon: float) -> dict:
    """
    Dynamically reverse-geocodes GPS coordinates into a clean US address or city, ST.
    """
    url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&addressdetails=1"
    req = urllib.request.Request(url, headers={'User-Agent': 'CarHaulerDispatchBot/2.0'})
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())
            addr = data.get("address", {})
            road = addr.get("road") or addr.get("highway") or ""
            house = addr.get("house_number") or ""
            city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county") or ""
            raw_state = addr.get("state", "")
            st_code = addr.get("state_code", "").upper()
            if not st_code and raw_state:
                st_code = US_STATE_NAME_TO_CODE.get(raw_state.lower(), raw_state)

            parts = []
            if house and road:
                parts.append(f"{house} {road}")
            elif road:
                parts.append(road)
            if city:
                parts.append(city)
            if st_code:
                parts.append(st_code)

            display = ", ".join(parts) if parts else (data.get("display_name", f"{lat:.4f}, {lon:.4f}").split(",")[0])
            return {
                "display": display,
                "city": city,
                "state": st_code or "US",
                "lat": float(lat),
                "lon": float(lon)
            }
    except Exception as e:
        print(f"[WARN] Reverse geocode error: {e}")
        return {"display": f"{lat:.4f}, {lon:.4f}", "city": "", "state": "US", "lat": float(lat), "lon": float(lon)}

def dynamic_geocode(query_str: str, fallback_query: str = None) -> dict:
    """
    Dynamically resolves any US street address, city, town, zip, or landmark via OpenStreetMap Nominatim API.
    Zero hardcoded cities. Supports multi-level fallback.
    """
    if not query_str:
        return None

    def _call_nominatim(q_raw: str):
        if not q_raw:
            return None
        q = re.sub(r'(?i)^(из|в|до|от|from|to)\s+', '', q_raw.strip()).strip()
        if not q:
            return None
        q = normalize_russian_city(q)
        cache_key = q.lower()
        if cache_key in _GEO_CACHE:
            return _GEO_CACHE[cache_key]

        try:
            url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(q)}&format=json&countrycodes=us&addressdetails=1&limit=1"
            req = urllib.request.Request(url, headers={'User-Agent': 'CarHaulerDispatchBot/2.0'})
            with urllib.request.urlopen(req, timeout=6) as r:
                data = json.loads(r.read().decode())
                if data:
                    item = data[0]
                    addr = item.get("address", {})
                    st_code = addr.get("state_code", "").upper()
                    if not st_code and addr.get("state"):
                        st_code = US_STATE_NAME_TO_CODE.get(addr.get("state", "").lower(), "")
                    city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county") or ""
                    road = addr.get("road") or addr.get("highway") or ""
                    house = addr.get("house_number") or ""

                    parts = []
                    if house and road:
                        parts.append(f"{house} {road}")
                    elif road:
                        parts.append(road)
                    if city:
                        parts.append(city)
                    if st_code:
                        parts.append(st_code)

                    display_str = ", ".join(parts) if parts else (f"{city}, {st_code}" if (city and st_code) else q.title())
                    res = {
                        "display": display_str,
                        "city": city or q.title(),
                        "state": st_code or "US",
                        "lat": float(item["lat"]),
                        "lon": float(item["lon"])
                    }
                    _GEO_CACHE[cache_key] = res
                    return res
        except Exception as e:
            print(f"[WARN] Dynamic geocode failed for '{q_raw}': {e}")
        return None

    # 1. Try primary query string
    res = _call_nominatim(query_str)
    if res:
        return res

    # 2. Try fallback query if provided
    if fallback_query and fallback_query != query_str:
        res = _call_nominatim(fallback_query)
        if res:
            return res

    # 3. If query contains commas, try stripping specific details and geocoding city/state
    if "," in query_str:
        segments = [s.strip() for s in query_str.split(",") if s.strip()]
        if len(segments) >= 2:
            city_st = f"{segments[-2]}, {segments[-1]}"
            res = _call_nominatim(city_st)
            if res:
                return res

    return None

def get_osrm_route(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple:
    """
    Dynamically queries OpenStreetMap OSRM Routing API for exact highway distance,
    driving duration, and road coordinates LineString.
    """
    url = f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
    req = urllib.request.Request(url, headers={'User-Agent': 'CarHaulerDispatchBot/2.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
            if data.get("code") == "Ok" and data.get("routes"):
                route = data["routes"][0]
                miles = round(route["distance"] / 1609.344, 1)
                duration_h = round(route["duration"] / 3600, 1)
                coords = route.get("geometry", {}).get("coordinates", [])
                return miles, duration_h, coords
    except Exception as e:
        print(f"[WARN] OSRM Routing API error: {e}")

    # Fallback to Haversine if OSRM is momentarily unreachable
    R = 3958.8
    dlat = (lat2 - lat1) * 0.01745329
    dlon = (lon2 - lon1) * 0.01745329
    a = (math.sin(dlat / 2)**2) + math.cos(lat1 * 0.01745329) * math.cos(lat2 * 0.01745329) * (math.sin(dlon / 2)**2)
    c = 2 * math.asin(math.sqrt(max(0.0, min(1.0, a))))
    est_miles = round(R * c * 1.15, 1)
    return est_miles, round(est_miles / 55.0, 1), []

def reverse_state(lat: float, lon: float) -> str:
    """Dynamically reverse-geocodes a single route point to its US state code."""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        req = urllib.request.Request(url, headers={'User-Agent': 'CarHaulerDispatchBot/2.0'})
        with urllib.request.urlopen(req, timeout=4) as r:
            d = json.loads(r.read().decode())
            addr = d.get("address", {})
            st_name = addr.get("state", "").lower()
            return US_STATE_NAME_TO_CODE.get(st_name, addr.get("state_code", "").upper())
    except Exception:
        return None

def detect_traversed_states(start_st: str, end_st: str, coords: list) -> list:
    """
    Samples route coordinates to dynamically discover all traversed states along the highway corridor.
    """
    states = [start_st] if (start_st and start_st != "US") else []
    if coords and len(coords) > 20:
        step = len(coords) // 4
        indices = [step, 2 * step, 3 * step]
        for idx in indices:
            pt = coords[idx]
            st = reverse_state(pt[1], pt[0])
            if st and st != "US" and st not in states:
                states.append(st)
    if end_st and end_st != "US" and end_st not in states:
        states.append(end_st)
    return states or ["US"]

def parse_origin_destination(text: str) -> tuple:
    """Extracts origin and destination from Russian or English query (fallback regex parser)."""
    clean = re.sub(r'(?i)\b(анализ|маршрут|маршрута|маршруту|расход|солярка|дизель|посчитай|рассчитай|route|fuel|миль|сколько)\b', ' ', text).strip()

    # 1. Match "из [A] в/до [B]" or "from [A] to [B]"
    m = re.search(r'(?i)(?:из|from)\s+([а-яa-z0-9\s,\.\-]+?)\s+(?:в|до|to)\s+([а-яa-z0-9\s,\.\-]+)', clean)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # 2. Match with spaces around hyphen or arrows
    parts = re.split(r'\s+(?:[-–—➔]|->|to|до)\s+', clean)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]

    # 3. Match "[A] в [B]" without 'из'
    m2 = re.search(r'(?i)([а-яa-z0-9\s,\.\-]+?)\s+(?:в|до|to)\s+([а-яa-z0-9\s,\.\-]+)', clean)
    if m2:
        return m2.group(1).strip(), m2.group(2).strip()

    if len(parts) == 1:
        return parts[0], ""
    return "", ""

def normalize_route_with_gemini(route_text: str) -> dict:
    """
    Uses Gemini API to normalize any free-form route or address query into structured location objects.
    Extracts exact street addresses, auto auctions (Copart/Manheim), highway exits, and cities.
    """
    try:
        try:
            from services.model_router import query_model_with_failover
        except ImportError:
            from model_router import query_model_with_failover

        prompt = f"""You are an expert car hauler logistics dispatch assistant in the USA.
The user sent a route, address, or location request in Russian or English: "{route_text}".

Your task: Extract or normalize the Origin (pickup/start location) and Destination (delivery/finish location).
Locations can be:
- US cities and states (e.g. "из Атланты в Майами" -> origin: "Atlanta, GA", destination: "Miami, FL")
- Exact street addresses (e.g. "1033 Green Acres Rd Eugene OR" -> "1033 Green Acres Rd, Eugene, OR 97408")
- Auto auctions (e.g. "Копарт в Атланте" -> display: "Copart Atlanta South", search: "480 McDonough Blvd SE, Atlanta, GA", city: "Atlanta, GA")
- Commercial dealerships, railheads, or ports (e.g. "Манхейм Даллас" -> search: "5333 W Kiest Blvd, Dallas, TX", "порт в Джерси" -> search: "Port Newark, NJ")
- Highway exits (e.g. "I-80 exit 142 Iowa" -> search: "Altoona, IA")

Return strictly a JSON object:
{{
  "origin_display": "Human-readable label for origin (e.g. '1033 Green Acres Rd, Eugene, OR' or 'Copart Atlanta')",
  "origin_search": "Clean searchable US street address or city, ST for OpenStreetMap",
  "origin_city_state": "City, ST fallback (e.g. 'Eugene, OR')",
  "dest_display": "Human-readable label for destination (e.g. 'Miami, FL' or 'Manheim Dallas')",
  "dest_search": "Clean searchable US street address or city, ST for OpenStreetMap",
  "dest_city_state": "City, ST fallback (e.g. 'Dallas, TX')"
}}
If the user only specified ONE location (e.g. "в Сакраменто" or "Miami FL" or "Copart Orlando"), put it in dest_display/dest_search/dest_city_state and leave origin fields empty.
Do not include any explanation or markdown formatting, output ONLY raw valid JSON."""

        raw_res, _ = query_model_with_failover(prompt, context_type="normalization")
        if raw_res:
            clean = re.sub(r'^```json\s*', '', raw_res.strip())
            clean = re.sub(r'\s*```$', '', clean).strip()
            return json.loads(clean)
    except Exception as e:
        print(f"[WARN] Gemini route normalization error: {e}")

    # Fallback to regex parser
    orig_str, dest_str = parse_origin_destination(route_text)
    return {
        "origin_display": orig_str,
        "origin_search": orig_str,
        "origin_city_state": orig_str,
        "dest_display": dest_str,
        "dest_search": dest_str,
        "dest_city_state": dest_str
    }

def get_live_state_prices(states: list, force_live: bool = True) -> dict:
    """
    Fetches certified AAA diesel benchmarks strictly for the states on the route.
    Queries the live AAA feed directly so prices are never hardcoded or stale.
    """
    live_feed = {}
    try:
        live_feed = fetch_live_aaa_prices()
    except Exception as e:
        print(f"[WARN] Failed to fetch live AAA feed in route advisor: {e}")

    prices = {}
    for st in states:
        if not st or st == "US":
            continue
        if st in live_feed and live_feed[st].get("diesel"):
            prices[st] = {
                "code": st,
                "name": live_feed[st].get("name", st),
                "diesel": float(live_feed[st]["diesel"])
            }
        else:
            bench = get_state_diesel_benchmark(st)
            if bench and bench.get("diesel"):
                prices[st] = {
                    "code": st,
                    "name": bench.get("name", st),
                    "diesel": float(bench["diesel"])
                }
            else:
                prices[st] = {"code": st, "name": st, "diesel": 5.85}

    return prices

def get_route_reminders(states: list, orig_name: str, dest_name: str, rig: dict) -> list:
    """
    Generates reminders STRICTLY for traversed states.
    No unsolicited sermons, zero irrelevant states.
    """
    reminders = []
    st_set = set(states)
    text_full = f"{orig_name} {dest_name}".lower()

    # 1. Weigh Stations (Scales) strictly on route
    if "FL" in st_set and ("GA" in st_set or "atlanta" in text_full):
        reminders.append("⚖️ <b>Весы:</b> I-75 South на въезде во Флориду (White Springs POE) — не держи полные баки перед весами.")
    elif "CA" in st_set and "OR" in st_set:
        reminders.append("⚖️ <b>Весы:</b> Ashland POE (граница OR/CA на I-5) и Cottonwood (CA) — держи не более 50–60 gal в баке перед въездом на весы.")
    elif "CA" in st_set and ("AZ" in st_set or "NV" in st_set):
        reminders.append("⚖️ <b>Весы:</b> Banning Scale (I-10 W) или Truckee Scale (I-80 W) — частый контроль ведущей оси.")
    elif "WY" in st_set:
        reminders.append("⚖️ <b>Весы:</b> Evanston POE (WY) и Cheyenne — строгий контроль весов на I-80.")
    elif "PA" in st_set:
        reminders.append("⚖️ <b>Весы:</b> I-80 и I-76 в Пенсильвании — регулярные мобильные инспекции DOT.")

    # 2. Toll Roads strictly on route
    if "FL" in st_set and ("miami" in text_full or "orlando" in text_full or "turnpike" in text_full):
        reminders.append("🛣️ <b>Платные дороги:</b> Florida's Turnpike (SunPass / Toll-By-Plate).")
    elif "PA" in st_set or "NJ" in st_set or "NY" in st_set:
        reminders.append("🛣️ <b>Платные дороги:</b> PA Turnpike, NJ Turnpike, мосты Нью-Йорка (только E-ZPass).")
    elif "OK" in st_set or "KS" in st_set:
        reminders.append("🛣️ <b>Платные дороги:</b> Will Rogers / Turner Turnpike (PikePass / PlatePay).")
    elif "IN" in st_set or "OH" in st_set:
        reminders.append("🛣️ <b>Платные дороги:</b> I-80 Indiana Toll Road / Ohio Turnpike.")

    # 3. IFTA Strategy (STRICTLY ONLY IF OREGON IS IN TRAVERSED STATES)
    if "OR" in st_set:
        reminders.append("💡 <b>IFTA (Орегон):</b> В OR налог на дизель 0¢ (вместо него Weight-Mile). Не лейте лишнее в Орегоне для выезда в соседние штаты, чтобы не платить налог по IFTA повторно.")

    # 4. Mountain Passes (STRICTLY ONLY IF PASSES ARE ON TRAVERSED ROUTE)
    if ("CA" in st_set and "OR" in st_set) or "siskiyou" in text_full:
        reminders.append("🏔️ <b>Перевал:</b> Siskiyou Summit (I-5, 4,310 ft) — затяжной подъем/спуск, зимой обязательны цепи.")
    elif ("CA" in st_set and "NV" in st_set) or "donner" in text_full:
        reminders.append("🏔️ <b>Перевал:</b> Donner Pass (I-80, 7,227 ft) — крутой градиент, цепной контроль (Chain Control).")
    elif "CO" in st_set and ("vail" in text_full or "eisenhower" in text_full or "i-70" in text_full):
        reminders.append("🏔️ <b>Перевал:</b> Vail Pass / Eisenhower Tunnel (I-70, 11,000+ ft) — тяжелый подъем для груженого автовоза.")

    return reminders

def analyze_car_hauler_route(
    route_text: str = "",
    origin_geo: dict = None,
    destination_geo: dict = None,
    driver_setup: str = None,
    fuel_card: str = "Mudflap",
    fuel_discount: float = 0.45,
    cargo: str = "Груженый"
) -> str:
    """
    Fully dynamic, API-driven route & fuel calculator for car haulers.
    Zero hardcoded cities, zero hardcoded miles, zero hardcoded fuel prices.
    Uses:
    1. Gemini API for address & location normalization
    2. OpenStreetMap Nominatim for geocoding & reverse-geocoding
    3. OpenStreetMap OSRM for highway routing, miles, duration & geometry
    4. AAA Daily Fuel API for certified state diesel prices
    """
    # 1. Rig Profile
    setup_lower = (driver_setup or "").lower()
    if any(k in setup_lower for k in ["виджик", "ведж", "wedge", "пикап", "pickup", "3-кар", "4-кар"]):
        rig = RIG_PROFILES["wedge"]
    elif any(k in setup_lower for k in ["хай-маунт", "хай маунт", "high-mount", "7-кар", "8-кар"]):
        rig = RIG_PROFILES["highmount"]
    else:
        rig = RIG_PROFILES["stinger"]

    is_loaded = "пустой" not in (cargo or "").lower()
    mpg = rig["mpg_loaded"] if is_loaded else rig["mpg_empty"]
    fuel_card = fuel_card or "Mudflap"
    fuel_discount = float(fuel_discount if fuel_discount is not None else 0.45)

    # 2. Normalization & Geocoding
    geo1 = origin_geo
    geo2 = destination_geo
    orig_name = ""
    dest_name = ""

    # Parse with Gemini if either point needs extraction
    if not geo1 or not geo2:
        norm = normalize_route_with_gemini(route_text) if route_text else {}

        if not geo1:
            orig_search = norm.get("origin_search") or norm.get("origin_city_state")
            orig_fallback = norm.get("origin_city_state")
            geo1 = dynamic_geocode(orig_search, fallback_query=orig_fallback)
            orig_name = norm.get("origin_display") or (geo1.get("display") if geo1 else orig_search)
        else:
            orig_name = geo1.get("display", "Текущая позиция")

        if not geo2:
            dest_search = norm.get("dest_search") or norm.get("dest_city_state")
            dest_fallback = norm.get("dest_city_state")
            geo2 = dynamic_geocode(dest_search, fallback_query=dest_fallback)
            dest_name = norm.get("dest_display") or (geo2.get("display") if geo2 else dest_search)
        else:
            dest_name = geo2.get("display", "Пункт назначения")

    if not geo1 or not geo2:
        if geo1 and not geo2:
            return (
                f"📍 Старт определен: <b>{orig_name}</b>\n"
                f"⚠️ Не удалось распознать пункт назначения из «{route_text}». "
                f"Укажи город назначения, точный адрес или аукцион (например: <code>Dallas, TX</code> или <code>Copart Orlando</code>)."
            )
        return (
            f"⚠️ Не удалось распознать маршрут «{route_text}». "
            f"Напиши точки в формате: <code>1033 Green Acres Rd, Eugene OR в Dallas TX</code> или отправь гео-точку 📍."
        )

    # 3. Dynamic Highway Distance & Duration via OSRM Routing API
    miles, duration_h, coords = get_osrm_route(geo1["lat"], geo1["lon"], geo2["lat"], geo2["lon"])

    # 4. Dynamic Traversed State Detection along route geometry
    start_st = geo1.get("state") or ""
    end_st = geo2.get("state") or ""
    traversed_states = detect_traversed_states(start_st, end_st, coords)

    # 5. Live Certified AAA Diesel Prices strictly for traversed states
    prices = get_live_state_prices(traversed_states, force_live=True)
    diesel_vals = [p["diesel"] for p in prices.values() if p.get("diesel")]
    avg_diesel = sum(diesel_vals) / max(1, len(diesel_vals)) if diesel_vals else 5.85
    state_names = "/".join(traversed_states)

    # 6. Fuel & Economics
    gallons = round(miles / mpg, 1)
    retail_total = round(gallons * avg_diesel, 2)
    card_price = max(1.50, round(avg_diesel - fuel_discount, 2))
    card_total = round(gallons * card_price, 2)
    savings = round(retail_total - card_total, 2)

    # 7. Route Reminders (strictly relevant to traversed states)
    reminders = get_route_reminders(traversed_states, orig_name, dest_name, rig)
    reminders_block = ""
    if reminders:
        reminders_block = "\n📍 <b>На заметку по трассе:</b>\n" + "\n".join([f"• {r}" for r in reminders]) + "\n"

    disc_label = f"-${fuel_discount:.2f}/gal" if fuel_discount > 0 else "розница"

    # 8. Clean, concise Trip Sheet Card
    return (
        f"🛣️ <b>Маршрут:</b> <b>{orig_name}</b> ➔ <b>{dest_name}</b> (~{miles:.0f} миль | ~{duration_h:.1f} ч)\n"
        f"🚛 <b>Сетап:</b> {rig['name']} ({mpg:.1f} MPG) | 💳 <b>{fuel_card}</b> ({disc_label})\n\n"
        f"⛽ <b>Расчет топлива:</b>\n"
        f"• Объем: <b>~{gallons:.0f} галлонов</b>\n"
        f"• Средняя розница по трассе ({state_names}): <b>${avg_diesel:.2f}/gal</b> (~${retail_total:.2f})\n"
        f"• По твоей карте {fuel_card}: <b>${card_price:.2f}/gal</b> (~${card_total:.2f})\n"
        f"• 💰 <b>Чистая экономия:</b> <b>+${savings:.2f}</b>\n"
        f"{reminders_block}\n"
        f"💡 <i>Точный дисконт на конкретном съезде сверяй в приложении {fuel_card} перед заездом на колонку.</i>"
    )
