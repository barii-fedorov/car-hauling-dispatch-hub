"""
Autonomous Telegram Dispatcher Bot Daemon ("Совет Агентов")
Listens to Telegram messages via long polling, invokes Gemini 3.5 Flash + Qdrant RAG,
replies to drivers with road slang & broker quotes, logs GDPR-sanitized cases to PostgreSQL,
and notifies admin cabinet.
"""

import os
import sys
import time
import json
import re
import urllib.request
import urllib.parse
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telegram_formatter import markdown_to_telegram_html, strip_html_tags
from fuel_advisor import (
    init_fuel_session_db,
    get_driver_session,
    set_driver_session,
    is_fuel_inquiry,
    get_fuel_request_prompt,
    reverse_geocode,
    extract_setup_and_cargo,
    generate_fuel_recommendations
)
from user_profiler import (
    analyze_and_update_profile,
    get_or_create_user_profile,
    get_profile_ai_context,
    format_user_profile_card,
    set_manual_rig,
    set_manual_role,
    reset_user_profile_data
)
from broker_verifier import verify_broker
from claim_generator import handle_claim_command
from overhang_advisor import get_overhang_guide

# Config & Credentials loaded securely from Environment Variables
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "-1004420587350")
CHANNEL_ID = os.environ.get("CHANNEL_CHAT_ID", "-1004424371115")

PG_HOST = os.environ.get("POSTGRES_HOST", "postgres")
PG_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
PG_USER = os.environ.get("POSTGRES_USER", "dispatch_admin")
PG_PASS = os.environ.get("POSTGRES_PASSWORD", "DispatchSecurePass2026!_pg")
PG_DB = os.environ.get("POSTGRES_DB", "dispatch_hub")

if not BOT_TOKEN:
    print("[CRITICAL] TELEGRAM_BOT_TOKEN environment variable is missing!")
if not GEMINI_KEY:
    print("[CRITICAL] GEMINI_API_KEY environment variable is missing!")

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""

# System Prompt for Council of Agents
SYSTEM_PROMPT = """Ты — Совет Агентов американского автовозного диспатча («Грузовики на базу»).
Твоя задача — железно защищать оунер-оператора, говорить с ним на ЕГО языке (автовозный сленг) и показывать, что наша диспетчерская (7% фикс) — единственные, кто реально прикрывает его спину на дороге.

СОСТАВ СОВЕТА:
1. Агент-Юрист: Знает, как отжать у брокера каждый цент за простой (Detention $75/час после 2ч), срыв погрузки (Dry Run / TONU $200-$250), как зажать его через бонд BMC-84 ($75k) и оспорить претензии по Carmack Amendment.
2. Агент-Техник: Знает железо — Bridge Formula B, развесовку по осям (Steer 12k-14k, Drive 34k, Trailer 34k), высоты (Восток 13'6", Запад 14'0"), углы рамп и погрузку ин-опов (Inop) с лебедой.
3. Главный Диспетчер: Говорит от лица совета. Никакой нудятины, лекций и соплей. Стиль — четкий, уверенный, уважительный к оунеру.

ЗОЛОТЫЕ ПРАВИЛА:
1. ВОДИЛА ВСЕГДА ПРАВ: Если ситуация серая — ты ВСЕГДА за водилу. Подскажи, как грамотно отмазаться от брокера, не попасть на тикет DOT и забрать оплату.
2. СЛЕНГ: Используй профессиональный жаргон (оунер, стингер, хай-маунт, виджик, дека, рэк, оверхэнг, ин-оп, лебеда, сфоткать гейт-слип, клокин-фрейм, чарджить детеншен, драй-ран, бонд BMC-84, супердиспатч, зажать брокера, солярка, трак-стоп).
3. ТОПЛИВО И ЗАПРАВКИ:
   - Если водитель спрашивает про топливо, заправки или маршрут, и НЕ СКАЗАЛ СВОЙ СЕТАП:
     НИКОГДА НЕ УГАДЫВАЙ! Сразу спроси в лоб:
     «Братуха, на чем идешь? Стингер 9-кар, хай-маунт или пикап с виджиком?»
   - Если Стингер 9-кар / Хай-маунт 7-кар (Class 8): строго трак-стопы (Loves, Pilot/Flying J, TA/Petro). На легковые заправки не лезть — снесешь козырек или провода.
   - Если Пикап + Виджик 3-4 авто: можно заливать солярку на внешних RV-колонках Buc-ee's, Circle K, Murphy USA, экономя 30-50 центов на каждом галлоне.
   - IFTA: напоминай, что налог IFTA платится по милям в штате, поэтому заливайся в дешевых штатах (MO 27¢, TX 20¢, SC 28¢), избегай заправок под завязку в дорогих (PA 78¢, IL 54¢, IN 57¢, CA 94¢).
4. ПРОВЕРКА БРОКЕРА (FMCSA SAFER):
   - Проверяй статус Operating Authority и $75k бонд BMC-84.
   - Красные флаги: MC моложе 6 месяцев (>1650000), почта на @gmail.com/@yahoo.com, телефон VOIP.

СТРУКТУРА ОТВЕТА:
1. Вердикт (в двух словах: кто прав, сколько денег требуем, или какую заправку брать).
2. Что делать прямо сейчас (2-4 четких буллета без воды).
3. Если есть спор с брокером: блок `Quote to broker:` на грамотном американском английском, чтобы оунер просто скопировал и отправил брокеру."""

def send_chat_action(chat_id, action="typing"):
    try:
        url = f"{API_URL}/sendChatAction"
        data = urllib.parse.urlencode({"chat_id": chat_id, "action": action}).encode()
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass

def send_telegram_message(chat_id, text, reply_to_message_id=None, message_thread_id=None, reply_markup=None):
    html_text = markdown_to_telegram_html(text)
    payload = {
        "chat_id": chat_id,
        "text": html_text,
        "parse_mode": "HTML"
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    if message_thread_id:
        payload["message_thread_id"] = message_thread_id
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    
    url = f"{API_URL}/sendMessage"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as he:
        try:
            print(f"[WARN] HTML sendMessage failed ({he}), retrying with stripped plain text...")
            payload["text"] = strip_html_tags(html_text)
            payload.pop("parse_mode", None)
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception as ex:
            print(f"[ERROR] Failed to send fallback message: {ex}")
    except Exception as e:
        print(f"[ERROR] Failed to send message: {e}")
    return None

def edit_telegram_message(chat_id, message_id, text, reply_markup=None):
    html_text = markdown_to_telegram_html(text)
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": html_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    url = f"{API_URL}/editMessageText"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as he:
        try:
            print(f"[WARN] HTML editMessageText failed ({he}), falling back to stripped text...")
            payload["text"] = strip_html_tags(html_text)
            payload.pop("parse_mode", None)
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception as ex:
            print(f"[ERROR] Failed to edit fallback message: {ex}")
    except Exception as e:
        print(f"[ERROR] Failed to edit message: {e}")
    return None

def ask_gemini_direct(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 800}
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
    except Exception as e:
        print(f"[ERROR] Gemini direct call failed: {e}")
    return None

def ask_gemini(user_message, chat_id=None):
    profile_context = ""
    if chat_id:
        try:
            profile_context = get_profile_ai_context(chat_id) + "\n\n"
        except Exception as e:
            print(f"[WARN] Failed to get profile context: {e}")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"SYSTEM INSTRUCTIONS:\n{SYSTEM_PROMPT}\n\n{profile_context}USER MESSAGE:\n{user_message}"}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1000
        }
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            return "Братуха, сигнал просел. Повтори вопрос, сейчас Совет подключится!"
    except Exception as e:
        print(f"[ERROR] Gemini API error: {e}")
        return "Братуха, временный сбой связи с базой. Повтори вопрос еще разок!"

def process_message(msg):
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    msg_id = msg.get("message_id")
    text = msg.get("text", "").strip()
    location = msg.get("location")
    from_user = msg.get("from", {})
    username = from_user.get("username", from_user.get("first_name", "оунер"))
    thread_id = msg.get("message_thread_id")

    if not chat_id or (not text and not location):
        return

    # 1. Dynamic User Profiling in PostgreSQL
    loc_str_quick = None
    if location:
        lat = location.get("latitude")
        lon = location.get("longitude")
        loc_str_quick = reverse_geocode(lat, lon)
    profile = analyze_and_update_profile(chat_id, text=text, location_str=loc_str_quick)

    if not chat_id or (not text and not location):
        return

    print(f"[MSG] From @{username} (chat {chat_id}, thread {thread_id}): {text or location}")

    # Check if this is an admin revision comment in Cabinet
    reply_to = msg.get("reply_to_message")
    if str(chat_id) == str(ADMIN_CHAT_ID) and reply_to:
        reply_msg_id = reply_to.get("message_id")
        post = None
        try:
            import psycopg2
            conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB)
            cur = conn.cursor()
            # 1. Match exact cabinet_message_id
            cur.execute("""
                SELECT post_id, title, content, image_url, post_type 
                FROM telegram_posts 
                WHERE cabinet_message_id = %s
                LIMIT 1;
            """, (reply_msg_id,))
            post = cur.fetchone()

            # 2. If not found by exact message id, match most recent pending post
            if not post:
                cur.execute("""
                    SELECT post_id, title, content, image_url, post_type 
                    FROM telegram_posts 
                    WHERE status IN ('revision_pending', 'pending_approval')
                    ORDER BY id DESC LIMIT 1;
                """)
                post = cur.fetchone()
            conn.close()
        except Exception as ex:
            print(f"[WARN] Error finding post for revision: {ex}")

        if post:
            post_id, p_title, p_content, p_image, p_type = post
            send_chat_action(chat_id, "typing")
            
            if p_type == "alert":
                revision_prompt = f"""
Ты — Дорожный Дозор американского автовозного диспатча («Грузовики на базу»).
Администратор дал комментарий к дорожному алерту:
"{text}"

ИСХОДНЫЙ ЧЕРНОВИК:
{p_content}

ЗАДАЧА:
Перепиши алерт с учетом замечаний администратора.
СТРОГО СОБЛЮДАЙ ПРАВИЛА:
1. ДЛИНА: РОВНО ДВЕ СТРОКИ! Ни строчки больше, никаких пустых строк между ними.
2. СТРОКА 1: 🚨 [Трасса] ([Штат]): что перекрыто/происходит прямо сейчас.
3. СТРОКА 2: ⚠️ Совет водителям автовозов + хештеги #Алерт #[Трасса] #[Штат]
"""
            else:
                revision_prompt = f"""
Ты — Совет Агентов американского автовозного диспатча («Грузовики на базу»).
Администратор дал комментарий к черновику поста:
"{text}"

ИСХОДНЫЙ ЧЕРНОВИК:
{p_content}

ЗАДАЧА:
Перепиши пост строго с учетом пожеланий администратора.
Сохраняй сочный язык американских автовозников, ключевые факты и блок хештегов в конце.
"""
            revised_text = ask_gemini_direct(revision_prompt)
            if revised_text:
                reply_markup = {
                    "inline_keyboard": [
                        [
                            {"text": "✅ Опубликовать в канал", "callback_data": f"publish_{post_id}"},
                            {"text": "🔄 На доработку", "callback_data": f"revise_{post_id}"}
                        ],
                        [
                            {"text": "❌ Отклонить", "callback_data": f"reject_{post_id}"}
                        ]
                    ]
                }
                rev_caption = f"✨ **[ОБНОВЛЕННЫЙ ЧЕРНОВИК С УЧЕТОМ ЗАМЕЧАНИЙ]**\n\n" + revised_text
                sent_res = send_telegram_message(
                    chat_id, 
                    rev_caption, 
                    reply_to_message_id=msg_id, 
                    message_thread_id=thread_id, 
                    reply_markup=reply_markup
                )
                new_msg_id = sent_res["result"]["message_id"] if sent_res and "result" in sent_res else None

                try:
                    import psycopg2
                    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB)
                    cur = conn.cursor()
                    if new_msg_id:
                        cur.execute("""
                            UPDATE telegram_posts 
                            SET content = %s, status = 'pending_approval', cabinet_message_id = %s
                            WHERE post_id = %s;
                        """, (revised_text, new_msg_id, post_id))
                    else:
                        cur.execute("""
                            UPDATE telegram_posts 
                            SET content = %s, status = 'pending_approval'
                            WHERE post_id = %s;
                        """, (revised_text, post_id))
                    conn.commit()
                    conn.close()
                except Exception as ex:
                    print(f"[WARN] DB update failed: {ex}")
                return

    # Start command
    if text.startswith("/start"):
        set_driver_session(chat_id, state="idle")
        welcome_text = (
            "🚛 <b>Здорово, оунер! На связи Совет Агентов автовозного диспатча («Грузовики на базу»).</b>\n\n"
            "Мы прикрываем твою спину на дороге 24/7. Наш принцип — <b>водитель всегда прав</b>.\n\n"
            "🔥 <b>Быстрые команды в меню:</b>\n"
            "• ⛽ <code>/fuel</code> — Найти дешевый дизель по геолокации\n"
            "• 🔍 <code>/broker MC#</code> — Проверка брокера, бонда $75k и срока оплаты\n"
            "• ⚖️ <code>/claim</code> — Претензии на Детеншен ($75/ч) и срыв TONU ($250)\n"
            "• 📏 <code>/overhang [Штат]</code> — Свесы, габариты и правила весовых\n"
            "• 👤 <code>/profile</code> — Твой сетап и статус (стингер vs виджик)\n"
            "• 🆘 <code>/help</code> — Связь с дежурным диспетчером\n\n"
            "👉 <i>Просто выбери команду из синего Меню или напиши сюда свой вопрос/скинь гео-пику!</i>"
        )
        send_telegram_message(chat_id, welcome_text, reply_to_message_id=msg_id)
        return

    # Help command
    if text.startswith("/help") or text.strip().lower() in ["помощь", "меню", "команды"]:
        help_text = (
            "🆘 <b>ДИСПЕТЧЕРСКАЯ ПОМОЩЬ И КОМАНДЫ БОТА:</b>\n\n"
            "• ⛽ <code>/fuel</code> — Поиск дешевого дизеля и трак-стопов по GPS\n"
            "• 🔍 <code>/broker MC#</code> — Проверка брокера, бонда $75,000 и срока оплаты\n"
            "• ⚖️ <code>/claim</code> — Официальные претензии на Детеншен ($75/ч) и TONU ($250)\n"
            "• 📏 <code>/overhang [Штат]</code> — Допустимые свесы, высота и веса\n"
            "• 👤 <code>/profile</code> — Твой сохраненный профиль и оборудование\n"
            "• 🚛 <code>/start</code> — Главное приветствие\n\n"
            "💬 <b>Или просто пиши любой вопрос в чат:</b>\n"
            "<i>'Сколько взять за неходовую Теслу?', 'Какая солярка дешевле в Вайоминге?', 'Коп выписал тикет за свес в Пенсильвании — что делать?'</i> — Совет ответит сразу!"
        )
        send_telegram_message(chat_id, help_text, reply_to_message_id=msg_id)
        return

    # Profile command
    if text.startswith("/profile") or text.strip().lower() in ["профиль", "мой профиль", "мой сетап", "сетап"]:
        card_text, card_markup = format_user_profile_card(chat_id)
        send_telegram_message(chat_id, card_text, reply_to_message_id=msg_id, reply_markup=card_markup)
        return

    # Claim & Legal Generator
    if text.startswith("/claim") or text.startswith("/detention") or text.startswith("/tonu"):
        claim_card = handle_claim_command(text)
        send_telegram_message(chat_id, claim_card, reply_to_message_id=msg_id)
        return

    # Overhang & Limits Advisor
    if text.startswith("/overhang") or text.lower().startswith("свес") or text.lower().startswith("свесы"):
        parts = text.split()
        st = parts[1] if len(parts) > 1 else None
        if not st:
            st_match = re.search(r'\b(PA|FL|TX|CA|GA|OH|IN|NY|NC|SC|IL)\b', text, re.IGNORECASE)
            if st_match:
                st = st_match.group(1)
        overhang_card = get_overhang_guide(st)
        send_telegram_message(chat_id, overhang_card, reply_to_message_id=msg_id)
        return

    # Broker & MC Verification
    if text.startswith("/broker") or text.lower().startswith("проверь брокера") or text.lower().startswith("проверка брокера"):
        parts = text.split(maxsplit=1)
        query = parts[1] if len(parts) > 1 else ""
        if not query:
            m = re.search(r'(?:проверь|проверка)\s+брокера\s*(.*)', text, re.IGNORECASE)
            if m:
                query = m.group(1).strip()
        send_chat_action(chat_id, "typing")
        broker_card = verify_broker(query)
        send_telegram_message(chat_id, broker_card, reply_to_message_id=msg_id)
        return

    # Explicit /fuel command
    if text.startswith("/fuel"):
        parts = text.split(maxsplit=1)
        query_loc = parts[1] if len(parts) > 1 else ""
        if query_loc:
            known_truck = profile.get("truck_type") if profile.get("truck_type") != "Неизвестно" else "Стингер 9-кар (Class 8)"
            ack_text = f"⏳ <b>Секунду!</b> Пробиваю заправки и цены на дизель для {query_loc}... Это может занять около минуты."
            ack_msg = send_telegram_message(chat_id, ack_text, reply_to_message_id=msg_id)
            ack_msg_id = ack_msg.get("result", {}).get("message_id") if ack_msg else None

            send_chat_action(chat_id, "typing")
            fuel_answer = generate_fuel_recommendations(query_loc, driver_setup=known_truck, cargo="Груженый")
            if ack_msg_id:
                res = edit_telegram_message(chat_id, ack_msg_id, fuel_answer)
                if not res or not res.get("ok"):
                    send_telegram_message(chat_id, fuel_answer, reply_to_message_id=msg_id)
            else:
                send_telegram_message(chat_id, fuel_answer, reply_to_message_id=msg_id)
            return

        set_driver_session(chat_id, state="awaiting_fuel_details")
        prompt_msg = (
            "⛽ <b>ПОИСК ТОПЛИВА И ТРАК-СТОПОВ ДЛЯ АВТОВОЗА:</b>\n\n"
            "1. Нажми 📎 <b>Скрепку</b> в поле ввода -> выбери <b>«Геолокация»</b> (📍 Location).\n"
            "2. Отправь свою точку на трассе.\n"
            "3. Я мгновенно найду:\n"
            "• 📍 Самую близкую заправку\n"
            "• 💰 Самую дешевую (со скидками Mudflap/RTS)\n"
            "• 🛣️ Оптимальный трак-стоп под твой сетап с прямыми выездами и высокими навесами!\n\n"
            "<i>Или просто напиши трассу и выход, например: 'I-80 exit 359 WY'</i>"
        )
        send_telegram_message(chat_id, prompt_msg, reply_to_message_id=msg_id)
        return

    # Fuel Intelligence Flow
    session = get_driver_session(chat_id)
    session_state = session.get("state")

    # A. Did driver send location pin OR are they responding to fuel request?
    if location or session_state == "awaiting_fuel_details":
        loc_str = loc_str_quick or session.get("last_query") or text
        if location and not loc_str_quick:
            lat = location.get("latitude")
            lon = location.get("longitude")
            loc_str = reverse_geocode(lat, lon)

        setup, cargo = extract_setup_and_cargo(text)
        known_truck = profile.get("truck_type") if profile.get("truck_type") != "Неизвестно" else None
        driver_setup = setup or session.get("driver_setup") or known_truck
        cargo_type = cargo or session.get("cargo_type") or (profile.get("typical_cargo") if profile.get("typical_cargo") != "Не указан" else None) or "Груженый"

        # If driver rig is completely unknown: DO NOT GUESS! Politely ask the driver once.
        if not driver_setup:
            set_driver_session(chat_id, state="awaiting_fuel_details", last_query=loc_str)
            ask_rig_text = (
                f"⛽ <b>Заправка автовоза:</b> Локацию принял (📍 <i>{loc_str}</i>)!\n"
                "Подскажи, на каком траке идешь — <b>стингер 9-кар</b> или <b>пикап с виджиком</b>? "
                "Я сразу запомню твой сетап в базе, чтобы подбирать подходящие колонки (Truck Lanes vs RV) и высоту навеса!"
            )
            send_telegram_message(chat_id, ask_rig_text, reply_to_message_id=msg_id)
            return

        # Immediate fast status message as requested by user
        ack_text = f"⏳ <b>Принял точку!</b> Сканирую трассу и проверяю актуальные цены на солярку для твоего сетапа ({driver_setup})... Это может занять около минуты."
        ack_msg = send_telegram_message(chat_id, ack_text, reply_to_message_id=msg_id)
        ack_msg_id = ack_msg.get("result", {}).get("message_id") if ack_msg else None

        send_chat_action(chat_id, "find_location")
        fuel_answer = generate_fuel_recommendations(loc_str, driver_setup=driver_setup, cargo=cargo_type)
        set_driver_session(chat_id, state="idle", driver_setup=driver_setup, cargo_type=cargo_type)

        if ack_msg_id:
            res = edit_telegram_message(chat_id, ack_msg_id, fuel_answer)
            if not res or not res.get("ok"):
                send_telegram_message(chat_id, fuel_answer, reply_to_message_id=msg_id)
        else:
            send_telegram_message(chat_id, fuel_answer, reply_to_message_id=msg_id)
        return

    # B. Did driver ask about fuel / diesel / gas station?
    if is_fuel_inquiry(text):
        setup, cargo = extract_setup_and_cargo(text)
        has_specific_location = any(k in text.lower() for k in [
            "i-80", "i-70", "i-95", "i-10", "i-40", "i-35", "i-15", "i-20", "i-65", "i-75",
            "exit", "выход", "шайенн", "cheyenne", "даллас", "dallas", "чикаго", "chicago",
            "денвер", "denver", "техас", "texas", "вайоминг", "wyoming", "колорадо", "colorado",
            "флорида", "florida", "майами", "miami", "орландо", "orlando", "атланта", "atlanta",
            "возле", "рядом", "в районе", "state"
        ])
        
        if setup and has_specific_location:
            ack_text = f"⏳ <b>Секунду!</b> Пробиваю заправки и цены на дизель для {setup}... Это может занять около минуты."
            ack_msg = send_telegram_message(chat_id, ack_text, reply_to_message_id=msg_id)
            ack_msg_id = ack_msg.get("result", {}).get("message_id") if ack_msg else None

            send_chat_action(chat_id, "typing")
            fuel_answer = generate_fuel_recommendations(text, driver_setup=setup, cargo=cargo)
            set_driver_session(chat_id, state="idle", driver_setup=setup, cargo_type=cargo)

            if ack_msg_id:
                res = edit_telegram_message(chat_id, ack_msg_id, fuel_answer)
                if not res or not res.get("ok"):
                    send_telegram_message(chat_id, fuel_answer, reply_to_message_id=msg_id)
            else:
                send_telegram_message(chat_id, fuel_answer, reply_to_message_id=msg_id)
            return

        # Ask in 1-3 lines for setup, cargo, and location pin
        set_driver_session(chat_id, state="awaiting_fuel_details", driver_setup=setup, cargo_type=cargo, last_query=text)
        prompt_msg = get_fuel_request_prompt()
        send_telegram_message(chat_id, prompt_msg, reply_to_message_id=msg_id)
        return

    # Indicate typing to user
    send_chat_action(chat_id, "typing")

    # Generate answer via Council of Agents (personalized with user profile memory)
    answer = ask_gemini(text, chat_id=chat_id)

    # Reply to user
    send_telegram_message(chat_id, answer, reply_to_message_id=msg_id)

    # Log to PostgreSQL (GDPR-sanitized) in background
    try:
        from case_logger_gdpr import log_driver_case
        case_payload = {
            "driver_id": str(chat_id),
            "driver_setup": "Unknown",
            "category": "Consultation",
            "facility": "On Road",
            "facility_location": "USA",
            "state": "US",
            "broker_name": "Inquiry",
            "broker_mc": "N/A",
            "claimed_amount": 0.0,
            "recovered_amount": 0.0,
            "status": "Resolved",
            "time_to_resolve_minutes": 1,
            "raw_summary": text,
            "resolution_strategy": answer[:300]
        }
        log_driver_case(case_payload)
    except Exception as e:
        print(f"[WARN] Failed to log case: {e}")

def answer_callback_query(callback_query_id, text=None):
    try:
        url = f"{API_URL}/answerCallbackQuery"
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
            payload["show_alert"] = False
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"[WARN] Failed to answer callback query: {e}")

def edit_message_reply_markup(chat_id, message_id, reply_markup=None):
    try:
        url = f"{API_URL}/editMessageReplyMarkup"
        payload = {"chat_id": chat_id, "message_id": message_id}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        else:
            payload["reply_markup"] = {"inline_keyboard": []}
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"[WARN] Failed to edit markup: {e}")

def process_callback_query(cb):
    cb_id = cb.get("id")
    data = cb.get("data", "")
    from_user = cb.get("from", {})
    username = from_user.get("username", from_user.get("first_name", "Admin"))
    msg = cb.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    msg_id = msg.get("message_id")

    print(f"[CALLBACK] Button clicked by @{username}: data='{data}' (msg {msg_id})")

    thread_id = msg.get("message_thread_id")

    # Profile Interactive Callbacks
    if data.startswith("setrig_"):
        rig_choice = data.replace("setrig_", "")
        from_id = from_user.get("id") or chat_id
        prof = set_manual_rig(from_id, rig_choice)
        rig_title = prof.get("truck_type")
        answer_callback_query(cb_id, text=f"Сетап обновлен: {rig_title}")
        new_text, new_markup = format_user_profile_card(from_id)
        edit_telegram_message(chat_id, msg_id, new_text, reply_markup=new_markup)
        return

    if data.startswith("setrole_"):
        role_choice = data.replace("setrole_", "")
        from_id = from_user.get("id") or chat_id
        prof = set_manual_role(from_id, role_choice)
        role_title = prof.get("user_role")
        answer_callback_query(cb_id, text=f"Статус обновлен: {role_title}")
        new_text, new_markup = format_user_profile_card(from_id)
        edit_telegram_message(chat_id, msg_id, new_text, reply_markup=new_markup)
        return

    if data == "reset_profile":
        from_id = from_user.get("id") or chat_id
        reset_user_profile_data(from_id)
        answer_callback_query(cb_id, text="Профиль сброшен к начальным настройкам")
        new_text, new_markup = format_user_profile_card(from_id)
        edit_telegram_message(chat_id, msg_id, new_text, reply_markup=new_markup)
        return

    if data.startswith("publish_"):
        post_id = data.replace("publish_", "")
        # 1. Fetch post from PostgreSQL
        try:
            import psycopg2
            conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB)
            cur = conn.cursor()
            cur.execute("SELECT title, content, image_url, post_type FROM telegram_posts WHERE post_id = %s;", (post_id,))
            post = cur.fetchone()
            if post:
                title, content, image_url, post_type = post
                # 2. Publish to Channel
                channel_msg_id = None
                if image_url and post_type != "alert":
                    photo_url = f"{API_URL}/sendPhoto"
                    html_caption = markdown_to_telegram_html(content, max_length=1020)
                    p_load = {"chat_id": CHANNEL_ID, "photo": image_url, "caption": html_caption, "parse_mode": "HTML"}
                    try:
                        req = urllib.request.Request(photo_url, data=json.dumps(p_load).encode(), headers={"Content-Type": "application/json"})
                        with urllib.request.urlopen(req, timeout=15) as resp:
                            res = json.loads(resp.read().decode())
                            channel_msg_id = res["result"]["message_id"]
                    except Exception as ex:
                        print(f"[WARN] sendPhoto HTML failed ({ex}), falling back to stripped text")
                        p_load["caption"] = strip_html_tags(html_caption)
                        p_load.pop("parse_mode", None)
                        req = urllib.request.Request(photo_url, data=json.dumps(p_load).encode(), headers={"Content-Type": "application/json"})
                        with urllib.request.urlopen(req, timeout=15) as resp:
                            res = json.loads(resp.read().decode())
                            channel_msg_id = res["result"]["message_id"]
                else:
                    m_url = f"{API_URL}/sendMessage"
                    html_text = markdown_to_telegram_html(content)
                    p_load = {"chat_id": CHANNEL_ID, "text": html_text, "parse_mode": "HTML"}
                    try:
                        req = urllib.request.Request(m_url, data=json.dumps(p_load).encode(), headers={"Content-Type": "application/json"})
                        with urllib.request.urlopen(req, timeout=15) as resp:
                            res = json.loads(resp.read().decode())
                            channel_msg_id = res["result"]["message_id"]
                    except Exception as ex:
                        print(f"[WARN] sendMessage HTML failed ({ex}), falling back to stripped text")
                        p_load["text"] = strip_html_tags(html_text)
                        p_load.pop("parse_mode", None)
                        req = urllib.request.Request(m_url, data=json.dumps(p_load).encode(), headers={"Content-Type": "application/json"})
                        with urllib.request.urlopen(req, timeout=15) as resp:
                            res = json.loads(resp.read().decode())
                            channel_msg_id = res["result"]["message_id"]

                # 3. Update PostgreSQL status
                cur.execute("""
                    UPDATE telegram_posts 
                    SET status = 'published', approved_by = %s, published_at = NOW(), channel_message_id = %s
                    WHERE post_id = %s;
                """, (username, channel_msg_id, post_id))
                conn.commit()
            conn.close()
        except Exception as e:
            print(f"[ERROR] DB update failed: {e}")

        # 4. Remove buttons and update Cabinet message
        edit_message_reply_markup(chat_id, msg_id, None)
        send_telegram_message(chat_id, f"✅ **ОДОБРЕНО И ОПУБЛИКОВАНО в канал @{username}**", reply_to_message_id=msg_id, message_thread_id=thread_id)
        answer_callback_query(cb_id, text="🚀 Пост успешно опубликован в канал «Грузовики на базу»!")

    elif data.startswith("revise_"):
        post_id = data.replace("revise_", "")
        try:
            import psycopg2
            conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB)
            cur = conn.cursor()
            cur.execute("""
                UPDATE telegram_posts 
                SET status = 'revision_pending'
                WHERE post_id = %s;
            """, (post_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[ERROR] DB update failed: {e}")

        send_telegram_message(
            chat_id,
            "🔄 **Черновик отправлен на доработку!**\n\nОтветьте *(Reply)* на сообщение с черновиком выше и напишите, что изменить или добавить — AI автоматически создаст новую версию.",
            reply_to_message_id=msg_id,
            message_thread_id=thread_id
        )
        answer_callback_query(cb_id, text="Черновик отправлен на доработку. Напишите комментарий в ответ!")

    elif data.startswith("reject_"):
        post_id = data.replace("reject_", "")
        try:
            import psycopg2
            conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB)
            cur = conn.cursor()
            cur.execute("""
                UPDATE telegram_posts 
                SET status = 'rejected', approved_by = %s 
                WHERE post_id = %s;
            """, (username, post_id))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[ERROR] DB update failed: {e}")

        # Remove buttons and update Cabinet message
        edit_message_reply_markup(chat_id, msg_id, None)
        send_telegram_message(chat_id, f"❌ **ОТКЛОНЕНО @{username}**", reply_to_message_id=msg_id, message_thread_id=thread_id)
        answer_callback_query(cb_id, text="Пост отклонен.")

def setup_telegram_commands():
    """
    Registers native Telegram bot commands for the menu button.
    """
    if not API_URL:
        return
    commands = [
        {"command": "fuel", "description": "⛽ Дешевый дизель по геолокации"},
        {"command": "broker", "description": "🔍 Проверка брокера по MC (бонд $75k)"},
        {"command": "claim", "description": "⚖️ Претензия: Детеншен ($75/ч) / TONU"},
        {"command": "overhang", "description": "📏 Свесы, габариты и правила по штатам"},
        {"command": "profile", "description": "👤 Мой профиль (трак, статус, коридор)"},
        {"command": "start", "description": "🚛 Главное меню диспетчера"},
        {"command": "help", "description": "🆘 Помощь и дежурный диспетчер"}
    ]
    url = f"{API_URL}/setMyCommands"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps({"commands": commands}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode())
            if res.get("ok"):
                print("[OK] Native Telegram bot commands registered successfully!")
            else:
                print(f"[WARN] setMyCommands returned: {res}")
    except Exception as e:
        print(f"[WARN] Failed to set native bot commands: {e}")

def run_bot():
    print(f"[START] Starting Telegram Bot Daemon for @CarHaulerSOS_bot...")
    setup_telegram_commands()
    init_fuel_session_db()
    offset = 0
    while True:
        try:
            url = f"{API_URL}/getUpdates?offset={offset}&timeout=20"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode())
                updates = data.get("result", [])
                for u in updates:
                    offset = max(offset, u["update_id"] + 1)
                    if "message" in u:
                        process_message(u["message"])
                    elif "callback_query" in u:
                        process_callback_query(u["callback_query"])
        except urllib.error.URLError as e:
            print(f"[RETRY] Network connection: {e}")
            time.sleep(3)
        except Exception as e:
            print(f"[ERROR] Polling loop error: {e}")
            time.sleep(3)

if __name__ == "__main__":
    run_bot()
