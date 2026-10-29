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
from repair_service import handle_repair_inquiry

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

# System Prompt for Professional Car Hauling Dispatcher
SYSTEM_PROMPT = """Ты — опытный ночной американский диспетчер автовозного флота (car hauling dispatch).
Твоя задача — помогать водителям на дороге: споры с брокерами, детеншен ($75/ч), TONU ($250), правила по свесам (FAST Act 23 CFR § 658.13), развесовка по осям, дизель и проверенный выездной ремонт.

ПРАВИЛА:
1. Тон: Спокойный, деловой, профессиональный. Никакого пафоса, театральности и выдуманных "советов агентов". Не строй из себя героя аниме.
2. Длина ответа: 2-4 предложения. Кратко, четко, только факты и цифры.
3. Если водитель спорит с брокером: дай готовый блок `Quote to broker:` на грамотном американском английском языке, чтобы водитель скопировал и отправил в один клик.
4. Помни контекст диалога: обращай внимание на предыдущие сообщения водителя. Если ошибся ранее — спокойно признай в одном предложении и дай правильное решение.
"""

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
            err_body = he.read().decode()
            if "message is not modified" in err_body:
                return {"ok": True, "result": "not_modified"}
            print(f"[WARN] HTML editMessageText failed ({he}: {err_body}), falling back to stripped text...")
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
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048,
            "thinkingConfig": {
                "thinkingBudget": 0
            }
        }
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

# In-Memory Multi-Turn Conversation History per chat_id
CHAT_MEMORY = {}  # {chat_id: [{"role": "user"|"model", "text": "..."}]}

def record_chat_turn(chat_id, role, text):
    if not chat_id or not text:
        return
    if chat_id not in CHAT_MEMORY:
        CHAT_MEMORY[chat_id] = []
    gemini_role = "user" if role == "user" else "model"
    CHAT_MEMORY[chat_id].append({"role": gemini_role, "text": text})
    if len(CHAT_MEMORY[chat_id]) > 10:
        CHAT_MEMORY[chat_id] = CHAT_MEMORY[chat_id][-10:]

def ask_gemini(user_message, chat_id=None):
    profile_context = ""
    if chat_id:
        try:
            profile_context = get_profile_ai_context(chat_id) + "\n\n"
        except Exception as e:
            print(f"[WARN] Failed to get profile context: {e}")

    system_instruction_text = f"{SYSTEM_PROMPT}\n\n{profile_context}".strip()
    
    contents = []
    history = CHAT_MEMORY.get(chat_id, [])
    # Build conversation turns from history
    for turn in history[-8:]:
        contents.append({
            "role": turn["role"],
            "parts": [{"text": turn["text"]}]
        })
    # Ensure current user_message is the final user turn
    if not contents or contents[-1]["role"] != "user" or contents[-1]["parts"][0]["text"] != user_message:
        contents.append({
            "role": "user",
            "parts": [{"text": user_message}]
        })

    # Sanitize contents so consecutive turns have distinct roles (Gemini API requirement)
    sanitized_contents = []
    for c in contents:
        if sanitized_contents and sanitized_contents[-1]["role"] == c["role"]:
            sanitized_contents[-1]["parts"][0]["text"] += "\n" + c["parts"][0]["text"]
        else:
            sanitized_contents.append(c)

    # First turn must be user
    while sanitized_contents and sanitized_contents[0]["role"] != "user":
        sanitized_contents.pop(0)

    if not sanitized_contents:
        sanitized_contents = [{"role": "user", "parts": [{"text": user_message}]}]

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={GEMINI_KEY}"
    payload = {
        "system_instruction": {
            "parts": [{"text": system_instruction_text}]
        },
        "contents": sanitized_contents,
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048,
            "thinkingConfig": {
                "thinkingBudget": 0
            }
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
                    answer_text = parts[0].get("text", "")
                    if chat_id and answer_text:
                        record_chat_turn(chat_id, "model", answer_text)
                    return answer_text
            return "Принял. Уточни запрос (город, штат, номер трассы или MC брокера) — выдам точные данные."
    except Exception as e:
        print(f"[ERROR] Gemini API error: {e}")
        return "Диспетчер на связи. Уточни локацию, MC брокера или технический вопрос — проверяю данные."

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
    record_chat_turn(chat_id, "user", text or f"📍 [Геолокация: {loc_str_quick}]")

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
            "🚛 <b>Диспетчер на связи.</b>\n"
            "Прикрываю автовозников на дороге 24/7 по любым вопросам: споры с брокерами, простой, срыв, солярка, свесы, ремонт.\n\n"
            "• ⛽ <code>/fuel</code> — Поиск дешевого дизеля по геолокации или городу\n"
            "• 🔧 <code>/repair</code> — Выездные мастера (Cash/Zelle, без репортов в DOT)\n"
            "• 🔍 <code>/broker MC#</code> — Экспресс-проверка брокера и бонда $75,000\n"
            "• ⚖️ <code>/claim</code> — Готовые претензии на Детеншен ($75/ч) и TONU ($250)\n"
            "• 📏 <code>/overhang [Штат]</code> — Допустимые свесы и высоты\n"
            "• 👤 <code>/profile</code> — Сменить сетап (Стингер / Виджик)\n\n"
            "<i>Или просто пиши любой вопрос в чат — отвечу сразу.</i>"
        )
        send_telegram_message(chat_id, welcome_text, reply_to_message_id=msg_id)
        return

    # Help command
    if text.startswith("/help") or text.strip().lower() in ["помощь", "меню", "команды"]:
        help_text = (
            "🆘 <b>ДИСПЕТЧЕРСКАЯ ПОМОЩЬ И КОМАНДЫ БОТА:</b>\n\n"
            "• ⛽ <code>/fuel</code> — Поиск дешевого дизеля и трак-стопов по GPS\n"
            "• 🔧 <code>/repair</code> — Выездные мастера и сварка автовозов (кэш/без репортов)\n"
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

    # Repair & Confidential Mechanics Directory
    is_repair_inquiry = (
        text.startswith("/repair") or
        text.strip().lower() in ["ремонт", "механик", "мастер", "починить", "сломался"] or
        any(k in text.lower() for k in [
            "лопнул шланг", "течет гидравлика", "вытек цилиндр", "нужен механик",
            "нужен ремонт", "сломалась рампа", "нужен сварщик", "найти мастера",
            "сварка алюминия", "пневмоподушка", "force regen", "дерейт"
        ])
    )
    if is_repair_inquiry:
        parts = text.split(maxsplit=1)
        q = parts[1] if (len(parts) > 1 and text.startswith("/repair")) else text
        lat = location.get("latitude") if location else None
        lon = location.get("longitude") if location else None
        loc_desc = loc_str_quick or (f"{lat:.2f}, {lon:.2f}" if lat else None)
        repair_card = handle_repair_inquiry(text=q, lat=lat, lon=lon, location_str=loc_desc)
        send_telegram_message(chat_id, repair_card, reply_to_message_id=msg_id)
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
        known_truck = profile.get("truck_type") if profile.get("truck_type") != "Неизвестно" else "Стингер 9-кар (Class 8)"
        if query_loc:
            ack_text = f"⏳ <b>Секунду!</b> Пробиваю заправки и цены на дизель для {query_loc}... Это может занять около минуты."
            ack_msg = send_telegram_message(chat_id, ack_text, reply_to_message_id=msg_id)
            ack_msg_id = ack_msg.get("result", {}).get("message_id") if ack_msg else None

            send_chat_action(chat_id, "typing")
            fuel_answer = generate_fuel_recommendations(query_loc, driver_setup=known_truck, cargo="Груженый")
            record_chat_turn(chat_id, "model", fuel_answer)
            if ack_msg_id:
                res = edit_telegram_message(chat_id, ack_msg_id, fuel_answer)
                if not res or not res.get("ok"):
                    send_telegram_message(chat_id, fuel_answer, reply_to_message_id=msg_id)
            else:
                send_telegram_message(chat_id, fuel_answer, reply_to_message_id=msg_id)
            return

        set_driver_session(chat_id, state="awaiting_fuel_details")
        prompt_msg = get_fuel_request_prompt()
        send_telegram_message(chat_id, prompt_msg, reply_to_message_id=msg_id)
        record_chat_turn(chat_id, "model", prompt_msg)
        return

    # Fuel Intelligence Flow
    session = get_driver_session(chat_id)
    session_state = session.get("state")
    known_truck = profile.get("truck_type") if profile.get("truck_type") != "Неизвестно" else "Стингер 9-кар (Class 8)"

    # A. Did driver send location pin OR are they in awaiting_fuel_details state?
    if location or session_state == "awaiting_fuel_details":
        # Check if user is objecting, conversing or clarifying instead of sending location
        is_conversational = any(w in text.lower() for w in [
            "ты же", "знаешь", "в профиле", "с чего", "почему", "откуда", "небраск",
            "зачем", "отмена", "стоп", "хватит", "нет", "не надо", "какой", "что ты"
        ])
        if not location and is_conversational:
            set_driver_session(chat_id, state="idle")
            # Falls through to general dispatcher ask_gemini with full multi-turn CHAT_MEMORY
        else:
            lat = location.get("latitude") if location else None
            lon = location.get("longitude") if location else None
            loc_str = loc_str_quick or session.get("last_query") or text
            if location and not loc_str_quick and lat and lon:
                loc_str = reverse_geocode(lat, lon)

            setup, cargo = extract_setup_and_cargo(text)
            driver_setup = setup or session.get("driver_setup") or known_truck
            cargo_type = cargo or session.get("cargo_type") or (profile.get("typical_cargo") if profile.get("typical_cargo") != "Не указан" else None) or "Груженый"

            ack_text = f"⏳ <b>Принял точку!</b> Сканирую трассу и проверяю актуальные цены на солярку для твоего сетапа ({driver_setup})... Это может занять около минуты."
            ack_msg = send_telegram_message(chat_id, ack_text, reply_to_message_id=msg_id)
            ack_msg_id = ack_msg.get("result", {}).get("message_id") if ack_msg else None

            send_chat_action(chat_id, "find_location")
            fuel_answer = generate_fuel_recommendations(loc_str, driver_setup=driver_setup, cargo=cargo_type, lat=lat, lon=lon)
            set_driver_session(chat_id, state="idle", driver_setup=driver_setup, cargo_type=cargo_type)
            record_chat_turn(chat_id, "model", fuel_answer)

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
        driver_setup = setup or session.get("driver_setup") or known_truck
        cargo_type = cargo or session.get("cargo_type") or "Груженый"

        # Check if query contains any location string (city, state, highway, exit, etc.)
        loc_candidate = re.sub(
            r'(?i)\b(топливо|солярка|солярку|дизель|заправка|заправки|заправиться|где|почем|цена|тракстоп|трак-стоп|fuel|diesel|gas|station|stop)\b',
            '',
            text
        ).strip()

        if len(loc_candidate) >= 3:
            ack_text = f"⏳ <b>Секунду!</b> Пробиваю заправки и цены на дизель для {driver_setup} в районе <i>{loc_candidate}</i>... Это может занять около минуты."
            ack_msg = send_telegram_message(chat_id, ack_text, reply_to_message_id=msg_id)
            ack_msg_id = ack_msg.get("result", {}).get("message_id") if ack_msg else None

            send_chat_action(chat_id, "typing")
            fuel_answer = generate_fuel_recommendations(loc_candidate, driver_setup=driver_setup, cargo=cargo_type)
            set_driver_session(chat_id, state="idle", driver_setup=driver_setup, cargo_type=cargo_type)
            record_chat_turn(chat_id, "model", fuel_answer)

            if ack_msg_id:
                res = edit_telegram_message(chat_id, ack_msg_id, fuel_answer)
                if not res or not res.get("ok"):
                    send_telegram_message(chat_id, fuel_answer, reply_to_message_id=msg_id)
            else:
                send_telegram_message(chat_id, fuel_answer, reply_to_message_id=msg_id)
            return

        # If purely "топливо" without any location: ask concisely in 1-2 lines
        set_driver_session(chat_id, state="awaiting_fuel_details", driver_setup=driver_setup, cargo_type=cargo_type, last_query=text)
        prompt_msg = get_fuel_request_prompt()
        send_telegram_message(chat_id, prompt_msg, reply_to_message_id=msg_id)
        record_chat_turn(chat_id, "model", prompt_msg)
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
        {"command": "repair", "description": "🔧 Свой ремонт и выездные мастера (Cash)"},
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
