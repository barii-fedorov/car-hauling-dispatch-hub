"""
Init Mechanics Schema and Seed Verified Russian-Speaking Mechanics Database
Sets up car_hauler_mechanics table in PostgreSQL and populates it with
verified, cash/zelle friendly repair contacts across major US trucking corridors.
"""

import os
import psycopg2

PG_HOST = os.environ.get("POSTGRES_HOST", "postgres")
PG_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
PG_USER = os.environ.get("POSTGRES_USER", "dispatch_admin")
PG_PASS = os.environ.get("POSTGRES_PASSWORD", "DispatchSecurePass2026!_pg")
PG_DB = os.environ.get("POSTGRES_DB", "dispatch_hub")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS car_hauler_mechanics (
    id SERIAL PRIMARY KEY,
    mechanic_id VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(128) NOT NULL,
    contact_phone VARCHAR(32) NOT NULL,
    languages VARCHAR(64) DEFAULT 'RU, EN',
    city VARCHAR(64) NOT NULL,
    state VARCHAR(8) NOT NULL,
    corridor VARCHAR(64) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    coverage_radius_miles INT DEFAULT 75,
    is_mobile BOOLEAN DEFAULT TRUE,
    has_shop BOOLEAN DEFAULT FALSE,
    specialties TEXT[] NOT NULL,
    payment_methods TEXT[] DEFAULT ARRAY['Cash', 'Zelle'],
    no_dot_reports BOOLEAN DEFAULT TRUE,
    trust_level VARCHAR(64) DEFAULT '⭐ Проверен Советом (Top Tier)',
    trust_score NUMERIC(3,2) DEFAULT 4.95,
    verified_reviews_count INT DEFAULT 15,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_verified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mechanics_state ON car_hauler_mechanics(state);
CREATE INDEX IF NOT EXISTS idx_mechanics_corridor ON car_hauler_mechanics(corridor);
CREATE INDEX IF NOT EXISTS idx_mechanics_trust ON car_hauler_mechanics(trust_score);
"""

SEED_MECHANICS = [
    # 1. Chicago Hub (IL/IN)
    {
        "mechanic_id": "mech_il_chicago_01",
        "name": "Александр (Cottrell Hydraulics & TIG Welding)",
        "contact_phone": "+1 (847) 555-0142",
        "languages": "Русский, English",
        "city": "Elk Grove Village",
        "state": "IL",
        "corridor": "I-90 / I-294 (Chicago Metro)",
        "latitude": 42.0039,
        "longitude": -87.9703,
        "coverage_radius_miles": 80,
        "is_mobile": True,
        "has_shop": True,
        "specialties": ["Гидравлика автовозов Cottrell/Boydstun", "Опрессовка шлангов 3/8 и 1/2", "Аргон/TIG сварка алюминиевых рамп", "Ремонт гидроцилиндров"],
        "payment_methods": ["Cash", "Zelle", "Venmo"],
        "no_dot_reports": True,
        "trust_level": "⭐ Проверен Советом (Top Tier)",
        "trust_score": 4.98,
        "verified_reviews_count": 42,
        "notes": "Свой выездной трак с мобильным прессом для РВД и аргоном. 10+ лет чинит только автовозы. Строго кэш/Zelle, без лишних вопросов."
    },
    {
        "mechanic_id": "mech_il_bolingbrook_02",
        "name": "Михаил (Дизель Detroit/Cummins & Пневматика)",
        "contact_phone": "+1 (630) 555-0188",
        "languages": "Русский, Украинский, English",
        "city": "Bolingbrook",
        "state": "IL",
        "corridor": "I-55 / I-80 (Joliet Corridor)",
        "latitude": 41.6986,
        "longitude": -88.0684,
        "coverage_radius_miles": 90,
        "is_mobile": True,
        "has_shop": True,
        "specialties": ["Дизель DD13/DD15/ISX15", "Принудительный прожиг DPF (Force Regen)", "Подушки подвески и краны уровня", "Тормозные камеры Type 30/30"],
        "payment_methods": ["Cash", "Zelle"],
        "no_dot_reports": True,
        "trust_level": "⭐ Проверен Советом (Top Tier)",
        "trust_score": 4.94,
        "verified_reviews_count": 29,
        "notes": "Дилерский диагностический софт DDDL и Insite. Снимает чеки, удаляет дерейт (Derate 5 MPH) прямо на трак-стопе."
    },
    {
        "mechanic_id": "mech_in_gary_03",
        "name": "Артем (I-80 Crossroad Mobile Rescue)",
        "contact_phone": "+1 (219) 555-0173",
        "languages": "Русский, English",
        "city": "Merrillville",
        "state": "IN",
        "corridor": "I-80 / I-94 / I-65",
        "latitude": 41.4828,
        "longitude": -87.3328,
        "coverage_radius_miles": 70,
        "is_mobile": True,
        "has_shop": False,
        "specialties": ["Круглосуточный выезд 24/7", "Шиномонтаж 22.5 и 17.5 low-pro", "Воздушные утечки / ABS", "Замена генераторов и стартеров"],
        "payment_methods": ["Cash", "Zelle", "CashApp"],
        "no_dot_reports": True,
        "trust_level": "👍 Надежный дорожный мастер",
        "trust_score": 4.88,
        "verified_reviews_count": 21,
        "notes": "Дежурит возле Pilot/Love's на I-80 Exit 15. Доезжает за 30-45 минут в любое время суток."
    },

    # 2. Pennsylvania & New Jersey Hub (I-95, I-80, I-78)
    {
        "mechanic_id": "mech_pa_philly_04",
        "name": "Сергей (Cottrell Pro & Hydraulic Hoses)",
        "contact_phone": "+1 (215) 555-0165",
        "languages": "Русский, English",
        "city": "Bensalem",
        "state": "PA",
        "corridor": "I-95 / I-276 (PA Turnpike)",
        "latitude": 40.1065,
        "longitude": -74.9513,
        "coverage_radius_miles": 85,
        "is_mobile": True,
        "has_shop": True,
        "specialties": ["Гидравлические распределители", "Замена цилиндров деков #1, #2, #3", "Сварка трещин рам автовоза", "Подвеска Hendrickson"],
        "payment_methods": ["Cash", "Zelle"],
        "no_dot_reports": True,
        "trust_level": "⭐ Проверен Советом (Top Tier)",
        "trust_score": 4.96,
        "verified_reviews_count": 38,
        "notes": "Огромный склад фитингов JIC и переходников. Спас десятки наших оунеров от простоев на аукционе Manheim PA."
    },
    {
        "mechanic_id": "mech_nj_elizabeth_05",
        "name": "Руслан (Port & Metro Mobile Tech)",
        "contact_phone": "+1 (908) 555-0199",
        "languages": "Русский, English",
        "city": "Elizabeth",
        "state": "NJ",
        "corridor": "I-95 / NJ Turnpike Exit 13A",
        "latitude": 40.6639,
        "longitude": -74.2107,
        "coverage_radius_miles": 65,
        "is_mobile": True,
        "has_shop": False,
        "specialties": ["Выездной ремонт 24/7", "Устранение течи сальников ступиц", "Тормозные колодки и барабаны", "Электрика и освещение"],
        "payment_methods": ["Cash", "Zelle"],
        "no_dot_reports": True,
        "trust_level": "⭐ Проверен Советом (Top Tier)",
        "trust_score": 4.92,
        "verified_reviews_count": 27,
        "notes": "Идеально знает портовую зону Нью-Йорка/Нью-Джерси. Принимает кэш, чек в DOT никогда не репортит."
    },

    # 3. Florida Hub (I-10, I-4, I-75, I-95)
    {
        "mechanic_id": "mech_fl_orlando_06",
        "name": "Дмитрий (Florida Car Hauler Service)",
        "contact_phone": "+1 (407) 555-0128",
        "languages": "Русский, English",
        "city": "Orlando",
        "state": "FL",
        "corridor": "I-4 / Florida's Turnpike / I-75",
        "latitude": 28.5383,
        "longitude": -81.3792,
        "coverage_radius_miles": 120,
        "is_mobile": True,
        "has_shop": True,
        "specialties": ["Стингеры 9-кар и Пикап+Виджик", "Гидравлика и лебедки Warn", "Замена подушек и амортизаторов", "Компьютерная диагностика"],
        "payment_methods": ["Cash", "Zelle", "Venmo"],
        "no_dot_reports": True,
        "trust_level": "⭐ Проверен Советом (Top Tier)",
        "trust_score": 4.97,
        "verified_reviews_count": 45,
        "notes": "Покрывает всю центральную Флориду от Тампы до Дэйтоны. Свой бокс и выездная техничка с генератором."
    },
    {
        "mechanic_id": "mech_fl_jax_07",
        "name": "Игорь (I-10 Crossroad Mobile Shop)",
        "contact_phone": "+1 (904) 555-0154",
        "languages": "Русский, English",
        "city": "Jacksonville",
        "state": "FL",
        "corridor": "I-10 / I-95 Junction",
        "latitude": 30.3322,
        "longitude": -81.6557,
        "coverage_radius_miles": 90,
        "is_mobile": True,
        "has_shop": False,
        "specialties": ["Быстрый выезд на I-10", "Шиномонтаж автовозной резины", "Воздушные линии и клапаны", "Сцепление и карданные валы"],
        "payment_methods": ["Cash", "Zelle"],
        "no_dot_reports": True,
        "trust_level": "👍 Надежный дорожный мастер",
        "trust_score": 4.89,
        "verified_reviews_count": 18,
        "notes": "Отличный мастер на въезде во Флориду. Быстро выезжает в район Lake City и Baldwin."
    },

    # 4. Texas Hub (I-10, I-20, I-35)
    {
        "mechanic_id": "mech_tx_dallas_08",
        "name": "Андрей (DFW Car Hauler Tech & Hydraulics)",
        "contact_phone": "+1 (214) 555-0112",
        "languages": "Русский, English",
        "city": "Grand Prairie",
        "state": "TX",
        "corridor": "I-20 / I-30 / I-35E (DFW Hub)",
        "latitude": 32.7459,
        "longitude": -96.9978,
        "coverage_radius_miles": 100,
        "is_mobile": True,
        "has_shop": True,
        "specialties": ["Полный сервис гидросистем", "Boydstun, Cottrell, Sun Country", "Сварка алюминия MIG/TIG", "Замена тормозных валов и трещоток"],
        "payment_methods": ["Cash", "Zelle"],
        "no_dot_reports": True,
        "trust_level": "⭐ Проверен Советом (Top Tier)",
        "trust_score": 4.99,
        "verified_reviews_count": 52,
        "notes": "Легендарный мастер в Техасе среди русскоязычных автовозников. Склад запчастей, клапанов и шлангов всегда с собой."
    },
    {
        "mechanic_id": "mech_tx_houston_09",
        "name": "Тимур (Houston Mobile Welder & Mechanic)",
        "contact_phone": "+1 (832) 555-0149",
        "languages": "Русский, English",
        "city": "Baytown",
        "state": "TX",
        "corridor": "I-10 East / Houston Ring 610",
        "latitude": 29.7355,
        "longitude": -94.9774,
        "coverage_radius_miles": 85,
        "is_mobile": True,
        "has_shop": False,
        "specialties": ["Усиление треснувших рам", "Сварка трейлеров и аппарелей", "Дизельная аппаратура", "Устранение дерейтов"],
        "payment_methods": ["Cash", "Zelle"],
        "no_dot_reports": True,
        "trust_level": "⭐ Проверен Советом (Top Tier)",
        "trust_score": 4.91,
        "verified_reviews_count": 23,
        "notes": "Выезжает на все трак-стопы на I-10 возле Хьюстона (Pilot Baytown, Loves). Работает аккуратно и без огласки."
    },

    # 5. California & West (I-5, I-10, I-15, I-80)
    {
        "mechanic_id": "mech_ca_fontana_10",
        "name": "Денис (SoCal 24/7 Car Hauler Care)",
        "contact_phone": "+1 (909) 555-0177",
        "languages": "Русский, English",
        "city": "Fontana",
        "state": "CA",
        "corridor": "I-10 / I-15 (Inland Empire Hub)",
        "latitude": 34.0922,
        "longitude": -117.4350,
        "coverage_radius_miles": 90,
        "is_mobile": True,
        "has_shop": True,
        "specialties": ["Ремонт перед весами Banning / Ontario", "Гидравлика и регулировка высоты деков", "Пневматика Bendix/Wabco", "Компьютерная диагностика"],
        "payment_methods": ["Cash", "Zelle", "Venmo"],
        "no_dot_reports": True,
        "trust_level": "⭐ Проверен Советом (Top Tier)",
        "trust_score": 4.96,
        "verified_reviews_count": 34,
        "notes": "Специализируется на экстренной подготовке трака к проходу жестких весов в Калифорнии. Никаких записей в Caltrans."
    },
    {
        "mechanic_id": "mech_ca_sacramento_11",
        "name": "Павел (NorCal & Donner Pass Rescue)",
        "contact_phone": "+1 (916) 555-0133",
        "languages": "Русский, English",
        "city": "Roseville",
        "state": "CA",
        "corridor": "I-80 / I-5 (Northern CA)",
        "latitude": 38.7521,
        "longitude": -121.2880,
        "coverage_radius_miles": 110,
        "is_mobile": True,
        "has_shop": False,
        "specialties": ["Горная помощь перед Donner Pass (I-80)", "Замена тормозов и шлангов", "Антифриз, помпы, термостаты", "Цепи противоскольжения"],
        "payment_methods": ["Cash", "Zelle"],
        "no_dot_reports": True,
        "trust_level": "⭐ Проверен Советом (Top Tier)",
        "trust_score": 4.93,
        "verified_reviews_count": 25,
        "notes": "Выезжает на перевал Donner Pass и трак-стопы в Сакраменто. Спасает от замерзания и поломок в горах."
    },

    # 6. Georgia & Carolinas (I-85, I-75, I-77)
    {
        "mechanic_id": "mech_ga_atlanta_12",
        "name": "Баха (Atlanta Truck Tech & Welding)",
        "contact_phone": "+1 (678) 555-0162",
        "languages": "Русский, English",
        "city": "Suwanee",
        "state": "GA",
        "corridor": "I-85 / I-285 (Atlanta Hub)",
        "latitude": 34.0515,
        "longitude": -84.0713,
        "coverage_radius_miles": 85,
        "is_mobile": True,
        "has_shop": True,
        "specialties": ["Сварка трейлеров и деков", "Гидравлика Cottrell/Wedge", "Ремонт воздушных утечек", "Замена датчиков NOx и выхлопа"],
        "payment_methods": ["Cash", "Zelle"],
        "no_dot_reports": True,
        "trust_level": "⭐ Проверен Советом (Top Tier)",
        "trust_score": 4.95,
        "verified_reviews_count": 31,
        "notes": "Быстро приезжает на аукцион Manheim Georgia и дилершипы Атланты. Оплата по факту решения проблемы."
    }
]

def init_mechanics_db():
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB)
    cur = conn.cursor()
    cur.execute(SCHEMA_SQL)
    conn.commit()

    for m in SEED_MECHANICS:
        cur.execute("""
            INSERT INTO car_hauler_mechanics (
                mechanic_id, name, contact_phone, languages, city, state, corridor,
                latitude, longitude, coverage_radius_miles, is_mobile, has_shop,
                specialties, payment_methods, no_dot_reports, trust_level, trust_score,
                verified_reviews_count, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (mechanic_id) DO UPDATE SET
                name = EXCLUDED.name,
                contact_phone = EXCLUDED.contact_phone,
                specialties = EXCLUDED.specialties,
                trust_score = EXCLUDED.trust_score,
                notes = EXCLUDED.notes;
        """, (
            m["mechanic_id"], m["name"], m["contact_phone"], m["languages"], m["city"], m["state"], m["corridor"],
            m["latitude"], m["longitude"], m["coverage_radius_miles"], m["is_mobile"], m["has_shop"],
            m["specialties"], m["payment_methods"], m["no_dot_reports"], m["trust_level"], m["trust_score"],
            m["verified_reviews_count"], m["notes"]
        ))
    conn.commit()
    cur.close()
    conn.close()
    print(f"[OK] Initialized car_hauler_mechanics table and seeded {len(SEED_MECHANICS)} verified mechanics.")

if __name__ == "__main__":
    init_mechanics_db()
