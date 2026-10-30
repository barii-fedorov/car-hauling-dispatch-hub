"""
User Profiler Module
Tracks and dynamically updates car hauler driver profiles in PostgreSQL.
Maintains role, confidence levels, rig equipment, fuel discount programs (Mudflap, RTS, TCS, NASTC),
corridor preferences, GDPR-safe indicator flags, and provides memory context to AI so users feel the bot remembers them.
"""

import os
import re
import psycopg2
from datetime import datetime, timezone

PG_HOST = os.environ.get("POSTGRES_HOST", "postgres")
PG_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
PG_USER = os.environ.get("POSTGRES_USER", "dispatch_admin")
PG_PASS = os.environ.get("POSTGRES_PASSWORD", "DispatchSecurePass2026!_pg")
PG_DB = os.environ.get("POSTGRES_DB", "dispatch_hub")

STANDARD_DISCOUNTS = {
    "Mudflap": 0.45,
    "RTS Pro": 0.50,
    "TCS Fuel": 0.40,
    "NASTC": 0.60,
    "Без карты (Retail)": 0.00
}

def get_db_connection():
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB)

def get_or_create_user_profile(telegram_id: int) -> dict:
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT telegram_id, user_role, role_confidence, truck_type, truck_confidence,
                   typical_cargo, primary_corridor, primary_state, satisfaction_score,
                   has_owner_status, has_phone_info, has_mc_info, has_equipment_info,
                   interaction_count, notes_summary, fuel_card, fuel_discount
            FROM user_profiles WHERE telegram_id = %s;
        """, (telegram_id,))
        row = cur.fetchone()
        if row:
            cur.close()
            conn.close()
            f_card = row[15] or "Mudflap"
            f_disc = float(row[16] if row[16] is not None else STANDARD_DISCOUNTS.get(f_card, 0.45))
            return {
                "telegram_id": row[0],
                "user_role": row[1],
                "role_confidence": float(row[2] or 0.0),
                "truck_type": row[3],
                "truck_confidence": float(row[4] or 0.0),
                "typical_cargo": row[5],
                "primary_corridor": row[6],
                "primary_state": row[7],
                "satisfaction_score": float(row[8] or 0.9),
                "has_owner_status": bool(row[9]),
                "has_phone_info": bool(row[10]),
                "has_mc_info": bool(row[11]),
                "has_equipment_info": bool(row[12]),
                "interaction_count": int(row[13] or 1),
                "notes_summary": row[14] or "",
                "fuel_card": f_card,
                "fuel_discount": f_disc
            }

        # Create new default profile
        cur.execute("""
            INSERT INTO user_profiles (telegram_id, user_role, role_confidence, truck_type, truck_confidence,
                                      typical_cargo, primary_corridor, primary_state, satisfaction_score,
                                      has_owner_status, has_phone_info, has_mc_info, has_equipment_info,
                                      interaction_count, notes_summary, fuel_card, fuel_discount, first_seen_at, last_active_at)
            VALUES (%s, 'Не определена', 0.20, 'Неизвестно', 0.00, 'Не указан', 'Вся территория США', 'US', 0.90,
                    FALSE, FALSE, FALSE, FALSE, 1, 'Новый пользователь', 'Mudflap', 0.45, NOW(), NOW())
            ON CONFLICT (telegram_id) DO NOTHING;
        """, (telegram_id,))
        conn.commit()
        cur.close()
        conn.close()
        return {
            "telegram_id": telegram_id,
            "user_role": "Не определена",
            "role_confidence": 0.20,
            "truck_type": "Неизвестно",
            "truck_confidence": 0.00,
            "typical_cargo": "Не указан",
            "primary_corridor": "Вся территория США",
            "primary_state": "US",
            "satisfaction_score": 0.90,
            "has_owner_status": False,
            "has_phone_info": False,
            "has_mc_info": False,
            "has_equipment_info": False,
            "interaction_count": 1,
            "notes_summary": "Новый пользователь",
            "fuel_card": "Mudflap",
            "fuel_discount": 0.45
        }
    except Exception as e:
        print(f"[WARN] Error in get_or_create_user_profile: {e}")
        if conn:
            conn.close()
        return {
            "telegram_id": telegram_id,
            "user_role": "Не определена",
            "role_confidence": 0.0,
            "truck_type": "Неизвестно",
            "truck_confidence": 0.0,
            "typical_cargo": "Не указан",
            "primary_corridor": "US",
            "primary_state": "US",
            "satisfaction_score": 0.90,
            "has_owner_status": False,
            "has_phone_info": False,
            "has_mc_info": False,
            "has_equipment_info": False,
            "interaction_count": 1,
            "notes_summary": "",
            "fuel_card": "Mudflap",
            "fuel_discount": 0.45
        }

def analyze_and_update_profile(telegram_id: int, text: str = "", location_str: str = None) -> dict:
    """
    Parses user message and location to automatically update their profile attributes in PostgreSQL.
    """
    profile = get_or_create_user_profile(telegram_id)
    text_lower = text.lower() if text else ""
    updates = {}

    # 1. Equipment / Rig Detection
    if any(k in text_lower for k in ["стингер", "stinger", "9-кар", "9 кар", "9 car", "9car"]):
        updates["truck_type"] = "Стингер 9-кар (Class 8)"
        updates["truck_confidence"] = 0.95
        updates["has_equipment_info"] = True
    elif any(k in text_lower for k in ["виджик", "ведж", "wedge", "пикап", "pickup", "ram 3500", "f-350", "3-кар", "4-кар", "3 car", "4 car"]):
        updates["truck_type"] = "Пикап + Виджик 3-4 авто"
        updates["truck_confidence"] = 0.95
        updates["has_equipment_info"] = True
    elif any(k in text_lower for k in ["хай-маунт", "хай маунт", "high-mount", "7-кар", "8-кар"]):
        updates["truck_type"] = "Хай-маунт 7-8 авто"
        updates["truck_confidence"] = 0.90
        updates["has_equipment_info"] = True

    # 1b. Fuel Discount Card / Program Detection
    if any(k in text_lower for k in ["mudflap", "мадфлап", "мудфлап"]):
        updates["fuel_card"] = "Mudflap"
        updates["fuel_discount"] = 0.45
    elif any(k in text_lower for k in ["rts", "rts pro", "ртс"]):
        updates["fuel_card"] = "RTS Pro"
        updates["fuel_discount"] = 0.50
    elif any(k in text_lower for k in ["tcs", "ткс"]):
        updates["fuel_card"] = "TCS Fuel"
        updates["fuel_discount"] = 0.40
    elif any(k in text_lower for k in ["nastc", "настк"]):
        updates["fuel_card"] = "NASTC"
        updates["fuel_discount"] = 0.60
    elif any(k in text_lower for k in ["без карты", "кэш", "cash", "нет карты", "без скидок", "по чеку", "карты нет"]):
        updates["fuel_card"] = "Без карты (Retail)"
        updates["fuel_discount"] = 0.00

    # 2. Role / Owner Status Detection
    if any(k in text_lower for k in ["я оунер", "оунер-оператор", "мой трак", "свой трак", "купил трак", "оунерю", "owner-operator", "owner"]):
        updates["user_role"] = "Оунер-Оператор"
        updates["role_confidence"] = 0.95
        updates["has_owner_status"] = True
    elif any(k in text_lower for k in ["я диспетчер", "мой водитель", "мои водители", "диспатчу", "наши траки", "диспетчер", "dispatcher"]):
        updates["user_role"] = "Диспетчер"
        updates["role_confidence"] = 0.95
        updates["has_owner_status"] = True
    elif any(k in text_lower for k in ["я водитель", "на проценте", "работаю на дядю", "трак компании", "company driver"]):
        updates["user_role"] = "Водитель-наймит"
        updates["role_confidence"] = 0.90
        updates["has_owner_status"] = True

    # 3. Cargo Detection
    if any(k in text_lower for k in ["suv", "кроссовер", "тяжелые suv", "паркетники"]):
        updates["typical_cargo"] = "Тяжелые SUV"
    elif any(k in text_lower for k in ["аукцион", "copart", "manheim", "iaai", "ин-оп", "in-op", "не на ходу"]):
        updates["typical_cargo"] = "Аукционы / In-op авто"
    elif any(k in text_lower for k in ["новые авто", "диллерские", "дилерка", "new cars"]):
        updates["typical_cargo"] = "Новые авто"

    # 4. Phone Info Detection
    if re.search(r'(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text or ""):
        updates["has_phone_info"] = True

    # 5. MC / USDOT Number Detection
    if re.search(r'\b(MC|DOT)[\s#]*\d{5,8}\b', text or "", re.IGNORECASE):
        updates["has_mc_info"] = True

    # 6. Location / Corridor / State Detection
    if location_str:
        loc_low = location_str.lower()
        if "florida" in loc_low or "fl" in loc_low:
            updates["primary_state"] = "FL"
            updates["primary_corridor"] = "I-10 (South / FL)"
        elif "texas" in loc_low or "tx" in loc_low:
            updates["primary_state"] = "TX"
            updates["primary_corridor"] = "I-10 / I-35 (Texas)"
        elif "wyoming" in loc_low or "wy" in loc_low:
            updates["primary_state"] = "WY"
            updates["primary_corridor"] = "I-80 (Midwest / WY)"
        elif "california" in loc_low or "ca" in loc_low:
            updates["primary_state"] = "CA"
            updates["primary_corridor"] = "I-5 / I-15 (West)"
        elif "pennsylvania" in loc_low or "pa" in loc_low:
            updates["primary_state"] = "PA"
            updates["primary_corridor"] = "I-80 / I-76 (East)"

    # 7. Satisfaction / Sentiment Detection
    cur_sat = profile.get("satisfaction_score", 0.90)
    if any(k in text_lower for k in ["спасибо", "от души", "красавчик", "огонь", "выручил", "топ", "👍", "🔥", "🤝", "❤️", "благодарю"]):
        updates["satisfaction_score"] = min(1.0, cur_sat + 0.05)
    elif any(k in text_lower for k in ["херня", "не работает", "обман", "отстой", "плохо", "бред", "👎"]):
        updates["satisfaction_score"] = max(0.2, cur_sat - 0.20)

    # 8. Notes Summary Generation
    notes_parts = []
    role = updates.get("user_role", profile["user_role"])
    truck = updates.get("truck_type", profile["truck_type"])
    corridor = updates.get("primary_corridor", profile["primary_corridor"])
    cargo = updates.get("typical_cargo", profile["typical_cargo"])
    card = updates.get("fuel_card", profile.get("fuel_card", "Mudflap"))

    if role != "Не определена":
        notes_parts.append(f"Роль: {role}")
    if truck != "Неизвестно":
        notes_parts.append(f"Сетап: {truck}")
    if card:
        notes_parts.append(f"Топливо: {card}")
    if cargo != "Не указан":
        notes_parts.append(f"Груз: {cargo}")
    if corridor != "Вся территория США":
        notes_parts.append(f"Маршрут: {corridor}")

    if notes_parts:
        updates["notes_summary"] = "; ".join(notes_parts)

    # Update PostgreSQL
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        set_clauses = ["interaction_count = interaction_count + 1", "last_active_at = NOW()"]
        values = []
        for k, v in updates.items():
            set_clauses.append(f"{k} = %s")
            values.append(v)
        values.append(telegram_id)

        sql = f"UPDATE user_profiles SET {', '.join(set_clauses)} WHERE telegram_id = %s;"
        cur.execute(sql, tuple(values))
        conn.commit()
        cur.close()
        conn.close()
        profile.update(updates)
        profile["interaction_count"] = profile.get("interaction_count", 1) + 1
    except Exception as e:
        print(f"[WARN] Error updating user profile: {e}")
        if conn:
            conn.close()

    return profile

def get_profile_ai_context(telegram_id: int) -> str:
    profile = get_or_create_user_profile(telegram_id)
    role = profile.get("user_role", "Не определена")
    truck = profile.get("truck_type", "Неизвестно")
    cargo = profile.get("typical_cargo", "Не указан")
    corridor = profile.get("primary_corridor", "США")
    fuel_card = profile.get("fuel_card", "Mudflap")
    fuel_discount = float(profile.get("fuel_discount", 0.45))

    context = "ИНФОРМАЦИЯ О ВОДИТЕЛЕ (не переспрашивай то, что уже известно):\n"
    if truck not in [None, "Неизвестно", "Не указан"]:
        context += f"• Сетап/Трак: {truck}\n"
    if fuel_card:
        disc_text = f"~${fuel_discount:.2f}/gal" if fuel_discount > 0 else "0¢ (розница)"
        context += f"• Топливная карта / Скидка: {fuel_card} ({disc_text})\n"
    if role not in [None, "Не определена"]:
        context += f"• Роль: {role}\n"
    if corridor != "Вся территория США":
        context += f"• Коридор: {corridor}\n"

    return context

def format_user_profile_card(telegram_id: int) -> tuple:
    """
    Renders a clean, practical equipment and fuel card profile for /profile.
    """
    profile = get_or_create_user_profile(telegram_id)
    truck = profile.get("truck_type", "Не указан")
    fuel_card = profile.get("fuel_card", "Mudflap")
    fuel_discount = float(profile.get("fuel_discount", 0.45))
    
    disc_str = f"~${fuel_discount:.2f}/gal" if fuel_discount > 0 else "0¢ (розница)"

    is_stinger = "Стингер" in truck
    is_wedge = "Виджик" in truck or "Пикап" in truck
    is_highmount = "Хай-маунт" in truck

    text = (
        f"👤 <b>Профиль кархолера / Сетап & Скидки</b>\n\n"
        f"🚛 <b>Текущий сетап:</b> <b>{truck}</b>\n"
        f"💳 <b>Топливная программа:</b> <b>{fuel_card}</b> (скидка {disc_str})\n\n"
        f"<i>Эти параметры бот автоматически учитывает для анализа маршрутов, расчета реального расхода солярки, "
        f"IFTA-оптимизации и предупреждений о перевесе перед весовыми станциями.</i>\n\n"
        f"<b>Переключить сетап или карту:</b>"
    )

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": f"{'✅ ' if is_stinger else ''}🚛 Стингер 9-кар", "callback_data": "setrig_stinger"},
                {"text": f"{'✅ ' if is_wedge else ''}🛻 Пикап + Виджик", "callback_data": "setrig_wedge"}
            ],
            [
                {"text": f"{'✅ ' if is_highmount else ''}🚙 Хай-маунт 7-8", "callback_data": "setrig_highmount"}
            ],
            [
                {"text": f"{'✅ ' if fuel_card == 'Mudflap' else ''}💳 Mudflap (~45¢)", "callback_data": "setcard_mudflap"},
                {"text": f"{'✅ ' if fuel_card == 'RTS Pro' else ''}💳 RTS Pro (~50¢)", "callback_data": "setcard_rts"}
            ],
            [
                {"text": f"{'✅ ' if fuel_card == 'TCS Fuel' else ''}💳 TCS (~40¢)", "callback_data": "setcard_tcs"},
                {"text": f"{'✅ ' if fuel_card == 'NASTC' else ''}💳 NASTC (~60¢)", "callback_data": "setcard_nastc"},
                {"text": f"{'✅ ' if 'Без карты' in fuel_card else ''}💵 Без скидок", "callback_data": "setcard_none"}
            ]
        ]
    }
    return text, reply_markup

def set_manual_rig(telegram_id: int, rig_choice: str) -> dict:
    if rig_choice == "stinger":
        rig_name = "Стингер 9-кар (Class 8)"
    elif rig_choice == "wedge":
        rig_name = "Пикап + Виджик 3-4 авто"
    elif rig_choice == "highmount":
        rig_name = "Хай-маунт 7-8 авто"
    else:
        rig_name = "Стингер 9-кар (Class 8)"

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE user_profiles 
            SET truck_type = %s, truck_confidence = 1.00, has_equipment_info = TRUE, last_active_at = NOW()
            WHERE telegram_id = %s;
        """, (rig_name, telegram_id))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[WARN] Error updating manual rig: {e}")
        if conn:
            conn.close()
    return get_or_create_user_profile(telegram_id)

def set_manual_fuel_card(telegram_id: int, card_choice: str) -> dict:
    card_map = {
        "mudflap": ("Mudflap", 0.45),
        "rts": ("RTS Pro", 0.50),
        "tcs": ("TCS Fuel", 0.40),
        "nastc": ("NASTC", 0.60),
        "none": ("Без карты (Retail)", 0.00)
    }
    card_name, disc = card_map.get(card_choice, ("Mudflap", 0.45))
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE user_profiles 
            SET fuel_card = %s, fuel_discount = %s, last_active_at = NOW()
            WHERE telegram_id = %s;
        """, (card_name, disc, telegram_id))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[WARN] Error updating manual fuel card: {e}")
        if conn:
            conn.close()
    return get_or_create_user_profile(telegram_id)

def set_manual_role(telegram_id: int, role_choice: str) -> dict:
    role_name = "Оунер-Оператор" if role_choice == "owner" else "Водитель-наймит"
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE user_profiles 
            SET user_role = %s, role_confidence = 1.00, has_owner_status = TRUE, last_active_at = NOW()
            WHERE telegram_id = %s;
        """, (role_name, telegram_id))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[WARN] Error updating manual role: {e}")
        if conn:
            conn.close()
    return get_or_create_user_profile(telegram_id)

def reset_user_profile_data(telegram_id: int) -> dict:
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE user_profiles 
            SET user_role = 'Не определена', role_confidence = 0.20,
                truck_type = 'Неизвестно', truck_confidence = 0.00,
                typical_cargo = 'Не указан', primary_corridor = 'Вся территория США',
                fuel_card = 'Mudflap', fuel_discount = 0.45,
                has_owner_status = FALSE, has_equipment_info = FALSE,
                last_active_at = NOW()
            WHERE telegram_id = %s;
        """, (telegram_id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[WARN] Error resetting profile: {e}")
        if conn:
            conn.close()
    return get_or_create_user_profile(telegram_id)

# Convenience alias
get_user_profile = get_or_create_user_profile
