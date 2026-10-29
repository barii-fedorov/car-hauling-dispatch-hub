#!/usr/bin/env python3
"""
Initialize user_profiles table and views in PostgreSQL for user intelligence and Grafana dashboard.
Stores anonymized profile attributes: roles, rig types, confidence levels, satisfaction scores,
checkmarks for known attributes (owner, phone, mc, equipment), corridor preferences, and notes.
"""

import os
import psycopg2
import random
from datetime import datetime, timezone, timedelta

PG_HOST = os.environ.get("POSTGRES_HOST", "postgres")
PG_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
PG_USER = os.environ.get("POSTGRES_USER", "dispatch_admin")
PG_PASS = os.environ.get("POSTGRES_PASSWORD", "DispatchSecurePass2026!_pg")
PG_DB = os.environ.get("POSTGRES_DB", "dispatch_hub")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS user_profiles (
    telegram_id BIGINT PRIMARY KEY,
    user_hash VARCHAR(16) GENERATED ALWAYS AS (SUBSTRING(MD5(telegram_id::text) FROM 1 FOR 8)) STORED,
    user_role VARCHAR(64) DEFAULT 'Не определена', -- 'Оунер-Оператор', 'Водитель-наймит', 'Диспетчер', 'Владелец флота'
    role_confidence NUMERIC(4,2) DEFAULT 0.00,
    truck_type VARCHAR(64) DEFAULT 'Неизвестно', -- 'Стингер 9-кар', 'Пикап + Виджик 3-4 авто', 'Хай-маунт 7-8 авто'
    truck_confidence NUMERIC(4,2) DEFAULT 0.00,
    typical_cargo VARCHAR(128) DEFAULT 'Не указан',
    primary_corridor VARCHAR(64) DEFAULT 'Вся территория США',
    primary_state VARCHAR(8) DEFAULT 'US',
    satisfaction_score NUMERIC(4,2) DEFAULT 0.90, -- 0.00 to 1.00
    has_owner_status BOOLEAN DEFAULT FALSE,
    has_phone_info BOOLEAN DEFAULT FALSE,
    has_mc_info BOOLEAN DEFAULT FALSE,
    has_equipment_info BOOLEAN DEFAULT FALSE,
    interaction_count INT DEFAULT 1,
    notes_summary TEXT DEFAULT '',
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_active_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_role ON user_profiles(user_role);
CREATE INDEX IF NOT EXISTS idx_user_profiles_truck ON user_profiles(truck_type);
CREATE INDEX IF NOT EXISTS idx_user_profiles_active ON user_profiles(last_active_at);

-- View for Grafana: 100% Anonymized, NO PII (No names, usernames or phone numbers)
CREATE OR REPLACE VIEW v_user_profiles_overview AS
SELECT 
    '#User-' || user_hash AS user_ref,
    user_role AS "Роль",
    ROUND(role_confidence * 100) || '%' AS "Уверенность роли",
    truck_type AS "Сетап автовоза",
    CASE WHEN has_owner_status THEN '✅ Да' ELSE '❌ Нет' END AS "Статус оунера",
    CASE WHEN has_equipment_info THEN '✅ Да' ELSE '❌ Нет' END AS "Сетап известен",
    CASE WHEN has_phone_info THEN '✅ Есть' ELSE '❌ Нет' END AS "Телефон",
    CASE WHEN has_mc_info THEN '✅ Есть' ELSE '❌ Нет' END AS "MC номер",
    CASE 
        WHEN satisfaction_score >= 0.85 THEN '🟢 ' || ROUND(satisfaction_score * 100) || '%'
        WHEN satisfaction_score >= 0.60 THEN '🟡 ' || ROUND(satisfaction_score * 100) || '%'
        ELSE '🔴 ' || ROUND(satisfaction_score * 100) || '%'
    END AS "Уровень довольства",
    interaction_count AS "Обращений",
    primary_corridor AS "Коридор / Регион",
    primary_state AS "Штат",
    last_active_at AS "Активность"
FROM user_profiles
ORDER BY last_active_at DESC;
"""

SAMPLE_PROFILES = [
    {
        "telegram_id": 10001001,
        "user_role": "Оунер-Оператор",
        "role_confidence": 0.95,
        "truck_type": "Стингер 9-кар (Class 8)",
        "truck_confidence": 0.95,
        "typical_cargo": "Новые авто и дилерские перевозки",
        "primary_corridor": "I-80 (Midwest - Mountain)",
        "primary_state": "WY",
        "satisfaction_score": 0.96,
        "has_owner_status": True,
        "has_phone_info": True,
        "has_mc_info": True,
        "has_equipment_info": True,
        "interaction_count": 18,
        "notes_summary": "Опытный оунер со стингером Peterbilt. Регулярно запрашивает дизель на I-80 и ставки."
    },
    {
        "telegram_id": 10001002,
        "user_role": "Оунер-Оператор",
        "role_confidence": 0.90,
        "truck_type": "Пикап RAM 3500 + Виджик 3-кар",
        "truck_confidence": 0.92,
        "typical_cargo": "Аукционы Copart / Manheim",
        "primary_corridor": "I-10 (South / Texas)",
        "primary_state": "TX",
        "satisfaction_score": 0.88,
        "has_owner_status": True,
        "has_phone_info": False,
        "has_mc_info": True,
        "has_equipment_info": True,
        "interaction_count": 9,
        "notes_summary": "Оунер на виджике. Специализируется на ин-опах с аукционов Техаса."
    },
    {
        "telegram_id": 10001003,
        "user_role": "Водитель-наймит",
        "role_confidence": 0.85,
        "truck_type": "Хай-маунт 7-8 авто",
        "truck_confidence": 0.88,
        "typical_cargo": "Смешанный (седаны + SUV)",
        "primary_corridor": "I-95 (East Coast)",
        "primary_state": "PA",
        "satisfaction_score": 0.75,
        "has_owner_status": True,
        "has_phone_info": False,
        "has_mc_info": False,
        "has_equipment_info": True,
        "interaction_count": 5,
        "notes_summary": "Водитель на проценте в небольшой компании. Часто консультируется по DOT и весам."
    },
    {
        "telegram_id": 10001004,
        "user_role": "Диспетчер",
        "role_confidence": 0.92,
        "truck_type": "Флот (стингеры + виджики)",
        "truck_confidence": 0.70,
        "typical_cargo": "Груженые сетапы на дальние рейсы",
        "primary_corridor": "I-70 / I-40",
        "primary_state": "IL",
        "satisfaction_score": 0.94,
        "has_owner_status": True,
        "has_phone_info": True,
        "has_mc_info": True,
        "has_equipment_info": True,
        "interaction_count": 24,
        "notes_summary": "Диспетчер автовозного парка (6 траков). Проверяет брокеров на BMC-84 и срывы погрузок."
    },
    {
        "telegram_id": 10001005,
        "user_role": "Оунер-Оператор",
        "role_confidence": 0.88,
        "truck_type": "Стингер 9-кар (Class 8)",
        "truck_confidence": 0.90,
        "typical_cargo": "Тяжелые SUV",
        "primary_corridor": "I-10 (Florida - Alabama)",
        "primary_state": "FL",
        "satisfaction_score": 0.92,
        "has_owner_status": True,
        "has_phone_info": False,
        "has_mc_info": True,
        "has_equipment_info": True,
        "interaction_count": 12,
        "notes_summary": "Оунер на I-10 во Флориде. Сверяет цены дизеля перед выходом на Джорджию."
    },
    {
        "telegram_id": 10001006,
        "user_role": "Не определена",
        "role_confidence": 0.20,
        "truck_type": "Неизвестно",
        "truck_confidence": 0.00,
        "typical_cargo": "Не указан",
        "primary_corridor": "I-15",
        "primary_state": "UT",
        "satisfaction_score": 0.85,
        "has_owner_status": False,
        "has_phone_info": False,
        "has_mc_info": False,
        "has_equipment_info": False,
        "interaction_count": 2,
        "notes_summary": "Новый пользователь, пока задавал общие вопросы про погоду."
    }
]

def main():
    print(f"Connecting to PostgreSQL at {PG_HOST}:{PG_PORT}/{PG_DB}...")
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB)
    cur = conn.cursor()
    
    print("Executing user_profiles schema DDL...")
    cur.execute(SCHEMA_SQL)
    conn.commit()

    print("Checking existing user profiles...")
    cur.execute("SELECT COUNT(*) FROM user_profiles;")
    count = cur.fetchone()[0]
    
    if count == 0:
        print("Populating initial representative sample profiles...")
        for p in SAMPLE_PROFILES:
            cur.execute("""
                INSERT INTO user_profiles (
                    telegram_id, user_role, role_confidence, truck_type, truck_confidence,
                    typical_cargo, primary_corridor, primary_state, satisfaction_score,
                    has_owner_status, has_phone_info, has_mc_info, has_equipment_info,
                    interaction_count, notes_summary, first_seen_at, last_active_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW() - interval '3 days', NOW() - interval '20 minutes'
                ) ON CONFLICT (telegram_id) DO NOTHING;
            """, (
                p["telegram_id"], p["user_role"], p["role_confidence"], p["truck_type"], p["truck_confidence"],
                p["typical_cargo"], p["primary_corridor"], p["primary_state"], p["satisfaction_score"],
                p["has_owner_status"], p["has_phone_info"], p["has_mc_info"], p["has_equipment_info"],
                p["interaction_count"], p["notes_summary"]
            ))
        conn.commit()
        print(f"[OK] Added {len(SAMPLE_PROFILES)} sample profiles.")
    else:
        print(f"[INFO] Table user_profiles already has {count} entries.")

    cur.close()
    conn.close()
    print("[SUCCESS] user_profiles schema and view initialized!")

if __name__ == "__main__":
    main()
