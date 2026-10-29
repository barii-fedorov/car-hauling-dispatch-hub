"""
User Profiler Module
Tracks and dynamically updates car hauler driver profiles in PostgreSQL.
Maintains role, confidence levels, rig equipment, corridor preferences,
GDPR-safe indicator flags (is_owner, has_phone, has_mc, has_equipment),
and provides memory context to AI so users feel the bot remembers them.
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
                   interaction_count, notes_summary
            FROM user_profiles WHERE telegram_id = %s;
        """, (telegram_id,))
        row = cur.fetchone()
        if row:
            cur.close()
            conn.close()
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
                "notes_summary": row[14] or ""
            }

        # Create new default profile
        cur.execute("""
            INSERT INTO user_profiles (telegram_id, user_role, role_confidence, truck_type, truck_confidence,
                                      typical_cargo, primary_corridor, primary_state, satisfaction_score,
                                      has_owner_status, has_phone_info, has_mc_info, has_equipment_info,
                                      interaction_count, notes_summary, first_seen_at, last_active_at)
            VALUES (%s, 'Не определена', 0.20, 'Неизвестно', 0.00, 'Не указан', 'Вся территория США', 'US', 0.90,
                    FALSE, FALSE, FALSE, FALSE, 1, 'Новый пользователь', NOW(), NOW())
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
            "notes_summary": "Новый пользователь"
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
            "notes_summary": ""
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

    if role != "Не определена":
        notes_parts.append(f"Роль: {role}")
    if truck != "Неизвестно":
        notes_parts.append(f"Сетап: {truck}")
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
    summary = profile.get("notes_summary", "")

    context = (
        "ПАМЯТЬ СОВЕТА О ДАННОМ ВОДИТЕЛЕ (Используй для персонализации, чтобы он чувствовал, что бот его помнит):\n"
    )
    if role != "Не определена":
        context += f"• Статус/Роль: {role} (уверенность {int(profile.get('role_confidence', 0)*100)}%)\n"
    if truck != "Неизвестно":
        context += f"• Оборудование/Сетап: {truck}\n"
    else:
        context += "• Оборудование/Сетап: НЕИЗВЕСТНО (НЕ ПРИДУМЫВАЙ машину сам, обязательно спроси стингер или виджик!)\n"
    if cargo != "Не указан":
        context += f"• Типичный груз: {cargo}\n"
    if corridor != "Вся территория США":
        context += f"• Основной регион/коридор: {corridor}\n"
    if summary:
        context += f"• Краткое резюме: {summary}\n"

    context += (
        "ВАЖНОЕ ПРАВИЛО: Если сетап известен, дружески ссылайся на него (например: «Помню, ты на стингере...» или «Как твой виджик?»). "
        "Если сетап НЕИЗВЕСТЕН — НИКОГДА не додумывай его сам, а прямо спроси водителя!"
    )
    return context
