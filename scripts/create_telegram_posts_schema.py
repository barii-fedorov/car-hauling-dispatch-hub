#!/usr/bin/env python3
"""
Create telegram_posts table and populate rich sample analytics for Grafana dashboard.
"""
import psycopg2
import os
import random
from datetime import datetime, timedelta

PG_HOST = os.environ.get("POSTGRES_HOST", "127.0.0.1")
PG_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
PG_USER = os.environ.get("POSTGRES_USER", "dispatch_admin")
PG_PASS = os.environ.get("POSTGRES_PASSWORD", "DispatchSecurePass2026!_pg")
PG_DB = os.environ.get("POSTGRES_DB", "dispatch_hub")

DDL = """
CREATE TABLE IF NOT EXISTS telegram_posts (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(64) UNIQUE NOT NULL,
    post_type VARCHAR(32) NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    content TEXT,
    image_url TEXT,
    hashtags TEXT[],
    primary_category VARCHAR(64) NOT NULL,
    primary_corridor VARCHAR(32),
    primary_state VARCHAR(8),
    target_setup VARCHAR(32) DEFAULT 'All',
    status VARCHAR(32) NOT NULL DEFAULT 'published',
    approved_by VARCHAR(64),
    cabinet_message_id BIGINT,
    channel_message_id BIGINT,
    published_at TIMESTAMPTZ DEFAULT NOW(),
    views_count INT DEFAULT 0,
    forwards_count INT DEFAULT 0,
    reactions_count INT DEFAULT 0,
    comments_count INT DEFAULT 0,
    engagement_rate NUMERIC(5,2) GENERATED ALWAYS AS (
        CASE WHEN views_count > 0 THEN ROUND(((reactions_count + forwards_count * 2 + comments_count * 3)::numeric / views_count::numeric) * 100, 2) ELSE 0 END
    ) STORED
);

CREATE INDEX IF NOT EXISTS idx_telegram_posts_published_at ON telegram_posts(published_at);
CREATE INDEX IF NOT EXISTS idx_telegram_posts_category ON telegram_posts(primary_category);
CREATE INDEX IF NOT EXISTS idx_telegram_posts_corridor ON telegram_posts(primary_corridor);
CREATE INDEX IF NOT EXISTS idx_telegram_posts_status ON telegram_posts(status);
"""

SAMPLE_POSTS = [
    ("Штормовой ветер 65 mph на I-80: 3 автовоза сдуло возле Elk Mountain", "Accidents", "I-80", "WY", "Stinger", "alert", ["#Алерт", "#I80", "#WY", "#Стингер", "#Погода"], 4500, 180, 230, 45),
    ("DOT объявил внеплановый рейд на весах I-70 Ohio: взвешивают стингеры", "DOT Blitz", "I-70", "OH", "Stinger", "alert", ["#Весы", "#I70", "#OH", "#Стингер", "#DOT_Рейд"], 3800, 140, 195, 32),
    ("Закрытие перевала Donner Pass на I-80: снежная буря и Chain Law", "Winter Weather", "I-80", "CA", "All", "alert", ["#Алерт", "#I80", "#CA", "#Погода", "#Цепи"], 4100, 210, 185, 29),
    ("Ставки на Copart Orlando выросли до $2.45/миля на Midwest", "Rates & Market", "I-75", "FL", "All", "news", ["#Ставки", "#Рынок", "#Копарт", "#FL"], 2900, 95, 120, 18),
    ("Как оспорить клейм за царапину на крыше по Carmack Amendment", "Legal & TONU", "National", "US", "All", "advice", ["#SOS_Совет", "#Юрист", "#Клеймы"], 3200, 175, 260, 52),
    ("Срыв погрузки на Manheim Pennsylvania: выбиваем $250 TONU за 1 час", "Legal & TONU", "I-76", "PA", "All", "advice", ["#SOS_Совет", "#Тонну", "#Детеншен", "#PA"], 3600, 190, 240, 41),
    ("Развесовка 9-кар стингера: как не попасть на штраф $1200 в Индиане", "Equipment", "I-65", "IN", "Stinger", "advice", ["#SOS_Совет", "#Стингер", "#Габариты", "#Вес"], 4200, 230, 310, 68),
    ("Loves на I-40 Техас запустил выделенные колонки без очередей", "Equipment", "I-40", "TX", "All", "news", ["#Новости", "#ТракСтоп", "#I40", "#TX"], 2400, 60, 85, 12),
    ("FMCSA ужесточает проверки фальсификации ELD: кого проверят первыми", "DOT Blitz", "National", "US", "All", "news", ["#Новости", "#DOT", "#ELD", "#FMCSA"], 3500, 160, 175, 38),
    ("Брокер TQL пытается урезать detention: разбираем свежий кейс", "Legal & TONU", "I-71", "OH", "All", "advice", ["#SOS_Совет", "#Детеншен", "#Брокеры"], 4800, 290, 390, 84),
    ("Черный список: Брокер-банкрот с аннулированным бондом BMC-84", "Legal & TONU", "National", "IL", "All", "alert", ["#Алерт", "#ЧерныйСписок", "#Брокеры"], 5100, 340, 410, 95),
    ("Виджик на 4 авто: оптимальная развесовка на пикап RAM 3500", "Equipment", "I-35", "TX", "Wedge", "advice", ["#SOS_Совет", "#Виджик", "#Габариты"], 3100, 130, 160, 25),
    ("Обвал цен на дизель на Flying J в Вайоминге: скидка 45 центов", "Equipment", "I-80", "WY", "All", "news", ["#Новости", "#Солярка", "#I80", "#WY"], 2700, 80, 110, 14),
    ("Проезд под мостом 13'6 на East Coast: актуальная карта лоу-клиренс", "Equipment", "I-95", "NY", "Stinger", "alert", ["#Алерт", "#I95", "#Габариты", "#Стингер"], 4600, 270, 320, 58),
    ("Задержки на аукционе IAAI Atlanta: простой более 4 часов", "Rates & Market", "I-85", "GA", "All", "news", ["#Новости", "#Детеншен", "#GA"], 2600, 75, 90, 15)
]

def seed_database():
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASS,
        dbname=PG_DB
    )
    cur = conn.cursor()
    cur.execute(DDL)
    print("[OK] Schema created/verified.")

    # Check if table already populated
    cur.execute("SELECT COUNT(*) FROM telegram_posts;")
    cnt = cur.fetchone()[0]
    if cnt > 10:
        print(f"[INFO] Table telegram_posts already has {cnt} rows.")
        conn.close()
        return

    print("[SEED] Generating 45 historical analytical posts...")
    now = datetime.now()
    inserted = 0

    for i in range(45):
        base = SAMPLE_POSTS[i % len(SAMPLE_POSTS)]
        title, cat, corridor, state, setup, ptype, tags, views, fwd, react, comm = base
        # Add slight variation
        time_offset = timedelta(days=random.randint(0, 28), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        pub_time = now - time_offset
        
        post_id = f"post_{pub_time.strftime('%Y%m%d')}_{i+1:03d}"
        var_views = int(views * random.uniform(0.75, 1.35))
        var_fwd = int(fwd * random.uniform(0.7, 1.4))
        var_react = int(react * random.uniform(0.8, 1.3))
        var_comm = int(comm * random.uniform(0.6, 1.5))
        
        status = "published" if random.random() > 0.1 else ("rejected" if random.random() > 0.5 else "pending_approval")
        approved_by = "admin_drommel" if status == "published" else None

        cur.execute("""
            INSERT INTO telegram_posts (
                post_id, post_type, title, summary, content, image_url, hashtags,
                primary_category, primary_corridor, primary_state, target_setup,
                status, approved_by, published_at, views_count, forwards_count,
                reactions_count, comments_count
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (post_id) DO NOTHING;
        """, (
            post_id, ptype, title, f"Аналитическая сводка по теме {title}", title,
            "https://cdllife.com/wp-content/uploads/sample.jpg", tags,
            cat, corridor, state, setup, status, approved_by, pub_time,
            var_views, var_fwd, var_react, var_comm
        ))
        inserted += 1

    conn.commit()
    conn.close()
    print(f"[OK] Seeded {inserted} posts successfully into telegram_posts table!")

if __name__ == "__main__":
    seed_database()
