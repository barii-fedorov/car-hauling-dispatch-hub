"""
Overhang & Dimensions Advisor Service for Car Haulers (Dynamic API & Geolocation Driven)
Provides legal overhang, height, flag, lighting, and weigh station limits under:
- Federal FAST Act (23 CFR § 658.13) for Stinger-steered & Wedge car haulers
- Dynamic State-specific regulations across all 50 US states
- OpenStreetMap Geolocation support (resolves current state from Telegram GPS pin or address)
"""

import re
try:
    from services.route_advisor import dynamic_geocode, reverse_geocode_osm, US_STATE_NAME_TO_CODE
except ImportError:
    from route_advisor import dynamic_geocode, reverse_geocode_osm, US_STATE_NAME_TO_CODE

# Western & Central states where 14'0" height is allowed on STAA corridors
WESTERN_14FT_STATES = {
    "AZ", "CA", "CO", "ID", "KS", "MO", "MT", "NE", "NV", "NM", "ND", "OK", "OR", "SD", "TX", "UT", "WA", "WY"
}

STATE_WEIGH_STATION_POES = {
    "FL": "I-75 White Springs POE, I-10 Sneads / Pensacola, I-75 Wildwood. (Жесткий контроль рулевой оси Steer!)",
    "OR": "Ashland POE (I-5 на границе с CA), Cascade Locks (I-84), Woodburn (I-5). (В OR действует налог Weight-Mile вместо налога на галлон)",
    "CA": "Banning (I-10 W), Wheeler Ridge (I-5 N), Castaic (I-5 S), Truckee (I-80 W), Cottonwood (I-5). (Строгий контроль KPRA 40 ft и свеса рулеткой!)",
    "PA": "I-80 Clarion & Bellefonte, I-76 PA Turnpike. (Старые низкие арочные мосты, меряют габаритную высоту и свес)",
    "TX": "I-10 Orange (граница LA), Van Horn (I-10 W), I-35 New Braunfels. (Проверяют минимум 4 крепления/стрепа на авто)",
    "GA": "I-95 Savannah / Port Wentworth, I-75 Ringgold (граница TN), I-75 Forsyth. (Контроль высоты верхнего яруса над кабиной)",
    "OH": "I-80 Ohio Turnpike, I-70 Preble & Buckeye Lake. (Проверяют общую длину автопоезда с рулеткой)",
    "IL": "I-55 Bolingbrook, I-57 Marion, I-80 Moline. (Регулярные мобильные инспекции DOT)",
    "WY": "I-80 Evanston POE (граница UT), Cheyenne POE (I-80 / I-25). (Строгий весовой контроль на высоте 7,000+ футов)",
    "NY": "I-87 Hillburn, I-84 Fishkill, мосты Нью-Йорка. (Критично: максимальная высота 13'6\", на Parkways автовозам въезд запрещен!)",
    "NJ": "I-78 Alpha, I-80 Knowlton, NJ Turnpike. (Весы на въездах в порт Нью-Арк)",
    "NC": "I-85 Charlotte, I-95 Halifax / Lumberton.",
    "VA": "I-81 Stephens City, I-95 Dumfries. (Следят за фиксацией страховочных цепочек и исправностью габаритных огней)",
    "MO": "I-70 Foristell, I-44 Joplin. (Взвешивание в движении WIM)"
}

def resolve_state_from_input(text: str = "", lat: float = None, lon: float = None) -> tuple[str, str]:
    """
    Dynamically discovers state code and display location from text or GPS pin.
    """
    if lat is not None and lon is not None:
        loc = reverse_geocode_osm(lat, lon)
        st = loc.get("state", "US")
        return st.upper(), loc.get("display", f"{lat:.4f}, {lon:.4f}")

    if not text:
        return "US", "США (Федеральные правила FAST Act)"

    # Check 2-letter state code in text
    m = re.search(r'\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b', text, re.IGNORECASE)
    if m:
        st = m.group(1).upper()
        return st, f"Штат {st}"

    # Geocode text dynamically
    geo = dynamic_geocode(text)
    if geo and geo.get("state"):
        return geo["state"].upper(), geo.get("display", text.title())

    return "US", text.title()

def get_overhang_guide(text: str = "", lat: float = None, lon: float = None) -> str:
    """
    Returns legal overhang, height, weight limits, and active weigh station POE tips for state.
    """
    state_code, display_loc = resolve_state_from_input(text, lat, lon)
    is_west = state_code in WESTERN_14FT_STATES
    max_height = "14'0\" (14 футов на STAA коридорах)" if is_west else "13'6\" (13 футов 6 дюймов — строго соблюдать!)"
    
    scales_info = STATE_WEIGH_STATION_POES.get(state_code, "Стационарные весы POE на Interstate трассах и выборочный весовой контроль State Patrol / DOT.")

    return f"""⚖️ <b>СВЕСЫ И РАЗВЕСОВКА (FAST ACT & STATE REGULATIONS)</b>
📍 <b>Локация:</b> <b>{display_loc}</b> ({state_code})

📏 <b>РАЗРЕШЕННЫЕ СВЕСЫ ПО ФЕДЕРАЛЬНОМУ FAST ACT (23 CFR § 658.13):</b>
• <b>Стингер 9-кар (Class 8 Stinger-Steered):</b>
  - Спереди: <b>до 4 футов (48 дюймов)</b>
  - Сзади: <b>до 6 футов (72 дюйма)</b>
  - Полезная длина автопоезда: <b>до 80 футов</b> (суммарно со свесами — <b>до 90 футов</b> без oversize пермитов).
• <b>Пикап + Виджик 3-4 авто (Traditional Semi / Wedge):</b>
  - Спереди: <b>до 3 футов (36 дюймов)</b>
  - Сзади: <b>до 4 футов (48 дюймов)</b>

📐 <b>ДОПУСТИМАЯ ВЫСОТА (MAX HEIGHT):</b>
• В {state_code}: <b>{max_height}</b>
• <i>Внимание:</i> На Восточном побережье (PA, NY, NJ, CT) всегда ориентируйся на <b>13'6\"</b> из-за старых арочных мостов. На Parkland/Parkways автовозам въезд запрещен!

⚖️ <b>ЛИМИТЫ ВЕСА ПО МОСТОВОЙ ФОРМУЛЕ (BRIDGE FORMULA):</b>
• Рулевая ось (Steer): <b>до 20,000 lbs</b> (ограничено индексом нагрузки шин)
• Одиночная ось (Single): <b>до 20,000 lbs</b>
• Тандемная тележка (Tandem): <b>до 34,000 lbs</b>
• Полная масса автопоезда (Gross Weight): <b>до 80,000 lbs</b>

🚩 <b>ФЛАГИ И ГАБАРИТНЫЕ ОГНИ:</b>
• При свесе свыше 4 футов обязательны <b>два ярко-оранжевых или красных флага 18x18\"</b> на крайних точках груза.
• В темное время суток и в тумане — <b>красные габаритные огни</b> (видимость не менее 500 футов).

🏢 <b>ВЕСОВЫЕ СТАНЦИИ И ЛОВУШКИ ({state_code}):</b>
• {scales_info}

💡 <b>Совет диспетчера:</b>
Грузи самые тяжелые авто (EV/SUV) над седлом и над тандемом трейлера. Длинные пикапы на нижнем ярусе ставь капотом вперед, чтобы задний свес не превышал 5–6 футов."""
