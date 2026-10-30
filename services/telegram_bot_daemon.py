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
    set_driver_session
)
from user_profiler import (
    analyze_and_update_profile,
    get_or_create_user_profile,
    get_profile_ai_context,
    format_user_profile_card,
    set_manual_rig,
    set_manual_role,
    set_manual_fuel_card,
    reset_user_profile_data
)
from route_advisor import analyze_car_hauler_route, reverse_geocode_osm
from broker_verifier import verify_broker
from claim_generator import handle_claim_command, CLAIMS_INLINE_KEYBOARD
from overhang_advisor import get_overhang_guide
from repair_service import handle_repair_inquiry
from model_router import start_metrics_server, query_model_with_failover

# Persistent Quick Action Keyboard for Car Haulers
MAIN_KEYBOARD = {
    "keyboard": [
        [
            {"text": "🛣️ Анализ маршрута и топлива"},
            {"text": "🔧 Мастер рядом"}
        ],
        [
            {"text": "🏢 Проверить брокера"},
            {"text": "⚖️ Свесы и весы (FAST Act)"}
        ],
        [
            {"text": "📋 Шаблоны клеймов"},
            {"text": "👤 Мой профиль"}
        ]
    ],
    "resize_keyboard": True,
    "is_persistent": True
}

ROUTE_KEYBOARD = {
    "keyboard": [
        [{"text": "📍 Отправить мою гео-точку", "request_location": True}],
        [{"text": "⬅️ В главное меню"}]
    ],
    "resize_keyboard": True,
    "one_time_keyboard": True
}

REPAIR_KEYBOARD = {
    "keyboard": [
        [{"text": "📍 Отправить мою гео-точку", "request_location": True}],
        [{"text": "⬅️ В главное меню"}]
    ],
    "resize_keyboard": True,
    "one_time_keyboard": True
}

OVERHANG_KEYBOARD = {
    "keyboard": [
        [{"text": "📍 Проверить свесы по моей гео-точке", "request_location": True}],
        [{"text": "⬅️ В главное меню"}]
    ],
    "resize_keyboard": True,
    "one_time_keyboard": True
}

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
    elif str(chat_id) != str(ADMIN_CHAT_ID) and str(chat_id) != str(CHANNEL_ID):
        payload["reply_markup"] = MAIN_KEYBOARD
    
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
    # NOTE: Telegram editMessageText only accepts inline_keyboard. Never pass ReplyKeyboardMarkup!
    if reply_markup is not None and "inline_keyboard" in reply_markup:
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
    try:
        from model_router import query_model_with_failover
    except ImportError:
        from services.model_router import query_model_with_failover
    res, _ = query_model_with_failover(prompt, context_type="general")
    return res

# Multi-Turn Conversation History (Memory + PostgreSQL Persistence)
CHAT_MEMORY = {}  # {chat_id: [{"role": "user"|"model", "text": "..."}]}

def init_chat_history_db():
    try:
        import psycopg2
        conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS driver_chat_history (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                role VARCHAR(16) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_driver_chat_hist_cid ON driver_chat_history(chat_id, id DESC);
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[WARN] init_chat_history_db failed: {e}")

def record_chat_turn(chat_id, role, text):
    if not chat_id or not text:
        return
    gemini_role = "user" if role == "user" else "model"
    if chat_id not in CHAT_MEMORY:
        CHAT_MEMORY[chat_id] = []
    CHAT_MEMORY[chat_id].append({"role": gemini_role, "text": text})
    if len(CHAT_MEMORY[chat_id]) > 14:
        CHAT_MEMORY[chat_id] = CHAT_MEMORY[chat_id][-14:]

    # Persist to PostgreSQL asynchronously
    def _save():
        try:
            import psycopg2
            conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO driver_chat_history (chat_id, role, content)
                VALUES (%s, %s, %s);
            """, (chat_id, gemini_role, text))
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            pass
    import threading
    threading.Thread(target=_save, daemon=True).start()

def load_chat_history(chat_id, limit=10):
    if chat_id in CHAT_MEMORY and len(CHAT_MEMORY[chat_id]) >= 2:
        return CHAT_MEMORY[chat_id][-limit:]
    # Fetch from PostgreSQL if memory is empty
    history = []
    try:
        import psycopg2
        conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB)
        cur = conn.cursor()
        cur.execute("""
            SELECT role, content FROM (
                SELECT role, content, id FROM driver_chat_history
                WHERE chat_id = %s
                ORDER BY id DESC LIMIT %s
            ) sub ORDER BY id ASC;
        """, (chat_id, limit))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        for r in rows:
            history.append({"role": r[0], "text": r[1]})
        if history:
            CHAT_MEMORY[chat_id] = history
    except Exception as e:
        print(f"[WARN] Failed to load chat history from DB: {e}")
    return history

def get_live_fuel_market_summary() -> str:
    """Provides certified AAA state diesel prices for grounding dispatcher answers."""
    try:
        from aaa_fuel_feed import get_state_diesel_benchmark
        states = [("OR", "Oregon"), ("CA", "California"), ("WA", "Washington"), ("TX", "Texas"), ("FL", "Florida"), ("WY", "Wyoming"), ("IL", "Illinois")]
        lines = ["[СЕРТИФИЦИРОВАННЫЕ ДАННЫЕ AAA ПО СОЛЯРКЕ (ДИЗЕЛЬ, НЕ БЕНЗИН!)]:"]
        for code, name in states:
            b = get_state_diesel_benchmark(code)
            if b:
                lines.append(f"• {name} ({code}): средняя розничная ${b['diesel']:.2f}/gal (коридор: ${b['range_low']:.2f}–${b['range_high']:.2f})")
        lines.append("[ДИСПЕТЧЕРСКИЕ ПРАВИЛА И ОРИЕНТИРЫ ПО РЕГИОНАМ]:")
        lines.append("- Вест Коаст (West Coast): В Калифорнии ($8.40) самый высокий налог и дизель в стране. Заправляться нужно ДО въезда в CA — на юге Орегона (Медфорд, Кламат-Фолс: средняя $6.74, по картам RTS/Mudflap $5.10–$5.35) или в Неваде. В самой Калифорнии брать только аварийный минимум.")
        lines.append("- Орегон: нет налога на галлон на колонке (поэтому цена на колонке кажется ниже), но действует весовой налог Weight-Mile Tax, который компания платит в конце квартала.")
        lines.append("- КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО называть цены на бензин $3.xx вместо реального коммерческого дизеля $5.xx-$8.xx!")
        return "\n".join(lines)
    except Exception:
        return ""

def is_conversational_fuel_query(text: str) -> bool:
    """
    Identifies high-level conversational or regional questions about diesel/fuel
    that should be answered by Gemini dispatcher with full chat memory and AAA grounding,
    rather than hijacked by a 3-truckstop geocoding template.
    """
    if not text:
        return False
    t = text.lower()
    broad_indicators = [
        "вест коаст", "west coast", "ист коаст", "east coast", "мидвест", "midwest",
        "по штатам", "по коридору", "вдоль трассы", "в калифорнии или", "в орегоне или",
        "вообще", "посоветуй", "что думаешь", "почему", "стоит ли", "где выгоднее",
        "где дешевле солярка", "где сейчас дешевый дизель", "где лучше заправиться",
        "налог", "ifta", "вес-майл", "дорогой", "дешевый", "а почему", "а где"
    ]
    if any(b in t for b in broad_indicators):
        return True
    if "?" in text and any(w in t for w in ["почему", "где", "как", "откуда", "зачем", "а что", "какой"]):
        has_specific_pin = bool(re.search(r'\b(exit\s*\d+|экзит\s*\d+|loves|pilot|flying j|ta|petro|заправка в [а-яa-z]+)\b', t))
        if not has_specific_pin:
            return True
    return False

def ask_gemini(user_message, chat_id=None):
    profile_context = ""
    if chat_id:
        try:
            profile_context = get_profile_ai_context(chat_id) + "\n\n"
        except Exception as e:
            print(f"[WARN] Failed to get profile context: {e}")

    fuel_summary = get_live_fuel_market_summary()
    system_instruction_text = f"{SYSTEM_PROMPT}\n\n{profile_context}\n\n{fuel_summary}".strip()
    
    # Load persistent multi-turn conversation history
    history = load_chat_history(chat_id, limit=8) if chat_id else []
    contents = []
    for turn in history:
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

    # Use Dynamic Model Router with 429 Circuit Breaker & Failover, passing full sanitized_contents
    try:
        raw_text, model_used = query_model_with_failover(
            user_message, 
            system_prompt=system_instruction_text, 
            context_type="general",
            contents=sanitized_contents
        )
        if raw_text:
            try:
                try:
                    from services.grounding_verifier import multi_agent_sense_check
                except ImportError:
                    from grounding_verifier import multi_agent_sense_check
                answer_text = multi_agent_sense_check(raw_text, context_type="general")
            except Exception:
                answer_text = raw_text

            if chat_id and answer_text:
                record_chat_turn(chat_id, "model", answer_text)
            return answer_text
    except Exception as e:
        print(f"[ERROR] Dynamic Model Router execution error: {e}")

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

    # Start command & Main Menu
    if text.startswith("/start") or text.strip() in ["⬅️ В главное меню", "главное меню", "меню"]:
        set_driver_session(chat_id, state="idle")
        welcome_text = (
            "🚛 <b>Диспетчер на связи.</b>\n"
            "Прикрываю автовозников на дороге 24/7 по любым вопросам: анализ маршрута, расход солярки, ремонт автовозов и клиентских авто, споры с брокерами, свесы и весовые.\n\n"
            "• 🛣️ <code>/route</code> — Анализ маршрута: километраж, солярка, скидки по картам, IFTA и весы\n"
            "• 🔧 <code>/repair</code> — Мастер рядом: ремонт автовоза (гидравлика/сварка) и скрытый ремонт авто клиента (PDR/царапины)\n"
            "• 🏢 <code>/broker MC#</code> — Проверка брокера, бонда $75,000, дней оплаты и факторинга\n"
            "• ⚖️ <code>/overhang [Штат]</code> — Допустимые свесы по FAST Act (4ft/6ft), высота 13'6\"/14'0\" и весы POE\n"
            "• 📋 <code>/claim</code> — Претензии в 1 клик: Детеншен ($75/ч), TONU ($250), In-Op ($150)\n"
            "• 👤 <code>/profile</code> — Сетап (Стингер/Виджик) и топливная карта (Mudflap, RTS, TCS)\n\n"
            "<i>Используй кнопки внизу или просто пиши любой вопрос или гео-точку 📍 в чат — отвечу сразу.</i>"
        )
        send_telegram_message(chat_id, welcome_text, reply_to_message_id=msg_id, reply_markup=MAIN_KEYBOARD)
        return

    # Help command
    if text.startswith("/help") or text.strip().lower() in ["помощь", "команды"]:
        help_text = (
            "🆘 <b>ДИСПЕТЧЕРСКАЯ ПОМОЩЬ И КОМАНДЫ БОТА:</b>\n\n"
            "• 🛣️ <code>/route</code> — Анализ маршрута: километраж, солярка, скидка по карте, IFTA и весы\n"
            "• 🔧 <code>/repair</code> — Выездные мастера для трака (Cash/без DOT) и скрытый ремонт авто клиента (PDR/царапины)\n"
            "• 🏢 <code>/broker MC#</code> — Проверка брокера, бонда $75,000 и срока оплаты\n"
            "• ⚖️ <code>/overhang [Штат]</code> — Свесы FAST Act, высоты мостов и активные весовые станции\n"
            "• 📋 <code>/claim</code> — Претензии: Детеншен ($75/ч), TONU ($250), неходовые авто ($150)\n"
            "• 👤 <code>/profile</code> — Твой сетап и топливная карта со скидкой\n"
            "• 🚛 <code>/start</code> — Главное меню\n\n"
            "💬 <b>Или просто пиши любой вопрос или скинь гео-точку 📍 в чат:</b>\n"
            "<i>'Посчитай маршрут из Сиэтла в ЛА', 'Поцарапали дверь на клиентской Тесле в Далласе', 'Брокер TQL не платит детеншен'</i> — помогу сразу!"
        )
        send_telegram_message(chat_id, help_text, reply_to_message_id=msg_id, reply_markup=MAIN_KEYBOARD)
        return

    # Repair & Mechanic Service (Rig breakdown vs Stealth client cargo damage)
    is_repair_inquiry = (
        text.startswith("/repair") or
        text.strip().lower() in ["ремонт", "механик", "мастер", "починить", "сломался", "мастер рядом", "🔧 мастер рядом"] or
        any(k in text.lower() for k in [
            "лопнул шланг", "течет гидравлика", "вытек цилиндр", "нужен механик",
            "нужен ремонт", "сломалась рампа", "нужен сварщик", "найти мастера",
            "сварка алюминия", "пневмоподушка", "force regen", "дерейт",
            "поцарапали", "вмятина", "бордюрка", "клиентское авто", "починить авто клиента"
        ])
    )
    if is_repair_inquiry:
        parts = text.split(maxsplit=1)
        q = parts[1] if (len(parts) > 1 and text.startswith("/repair")) else ("" if text.strip().lower() in ["ремонт", "механик", "мастер", "починить", "сломался", "мастер рядом", "🔧 мастер рядом", "/repair"] else text)
        if q and len(q) > 6 and not any(q.strip().lower() == w for w in ["мастер рядом", "ремонт", "механик"]):
            send_chat_action(chat_id, "find_location")
            repair_card = handle_repair_inquiry(text=q)
            send_telegram_message(chat_id, repair_card, reply_to_message_id=msg_id, reply_markup=MAIN_KEYBOARD)
            record_chat_turn(chat_id, "model", repair_card)
            return

        set_driver_session(chat_id, state="awaiting_repair_inquiry")
        prompt_text = (
            "🔧 <b>Поиск мастера рядом:</b>\n\n"
            "📍 Нажми <b>«📍 Отправить мою гео-точку»</b> внизу, либо напиши, где находишься и что случилось\n"
            "(например: <code>1033 Green Acres Rd, Eugene OR, лопнул шланг подъема рампы</code> или <code>вмятина на двери клиентского авто в Далласе</code>):\n\n"
            "• <i>Помощь с автовозом:</i> гидравлика, выездной пресс шлангов, сварка рампы, регенерация (Cash/Zelle без отметок в DOT)\n"
            "• <i>Помощь с клиентским авто:</i> беспокрасочный PDR, локальная полировка сколов/царапин, восстановление дисков от бордюрки (без внесения в Carfax)"
        )
        send_telegram_message(chat_id, prompt_text, reply_to_message_id=msg_id, reply_markup=REPAIR_KEYBOARD)
        record_chat_turn(chat_id, "model", prompt_text)
        return

    # Profile command
    if text.startswith("/profile") or text.strip().lower() in ["профиль", "мой профиль", "мой сетап", "сетап"]:
        card_text, card_markup = format_user_profile_card(chat_id)
        send_telegram_message(chat_id, card_text, reply_to_message_id=msg_id, reply_markup=card_markup)
        return

    # Claim & Legal Generator
    if text.startswith("/claim") or text.startswith("/detention") or text.startswith("/tonu") or text.strip() in ["📋 Шаблоны клеймов", "шаблоны клеймов", "клеймы"]:
        claim_card, claim_markup = handle_claim_command(text)
        send_telegram_message(chat_id, claim_card, reply_to_message_id=msg_id, reply_markup=claim_markup or MAIN_KEYBOARD)
        record_chat_turn(chat_id, "model", claim_card)
        return

    # Overhang & Limits Advisor (Dynamic FAST Act & Weigh Stations)
    if text.startswith("/overhang") or text.lower().startswith("свес") or "свесы" in text.lower() or text.strip() in ["⚖️ Свесы и весы (FAST Act)", "свесы и весы"]:
        parts = text.split(maxsplit=1)
        st_query = parts[1] if (len(parts) > 1 and text.startswith("/overhang")) else ("" if text.strip() in ["⚖️ Свесы и весы (FAST Act)", "свесы и весы", "/overhang"] else text)
        if st_query and len(st_query) >= 2 and st_query.strip().lower() not in ["свесы и весы (fast act)", "свесы и весы", "свесы"]:
            send_chat_action(chat_id, "typing")
            overhang_card = get_overhang_guide(text=st_query)
            send_telegram_message(chat_id, overhang_card, reply_to_message_id=msg_id, reply_markup=MAIN_KEYBOARD)
            record_chat_turn(chat_id, "model", overhang_card)
            return

        set_driver_session(chat_id, state="awaiting_overhang_location")
        prompt_text = (
            "⚖️ <b>Свесы и весы (FAST Act 23 CFR § 658.13):</b>\n\n"
            "📍 Нажми <b>«📍 Проверить свесы по моей гео-точке»</b> внизу, чтобы автоматически определить штат и весы POE по твоему местоположению,\n"
            "либо напиши штат или город (например: <code>Орегон</code>, <code>PA</code>, <code>Eugene OR</code> или <code>Dallas TX</code>):"
        )
        send_telegram_message(chat_id, prompt_text, reply_to_message_id=msg_id, reply_markup=OVERHANG_KEYBOARD)
        record_chat_turn(chat_id, "model", prompt_text)
        return

    # Broker & MC Verification
    if text.startswith("/broker") or text.lower().startswith("проверь брокера") or text.lower().startswith("проверка брокера") or text.strip() == "🏢 Проверить брокера":
        parts = text.split(maxsplit=1)
        query = parts[1] if (len(parts) > 1 and text.startswith("/broker")) else ""
        if not query and not text.strip().startswith("/broker") and text.strip() != "🏢 Проверить брокера":
            m = re.search(r'(?:проверь|проверка)\s+брокера\s*(.*)', text, re.IGNORECASE)
            if m:
                query = m.group(1).strip()
        if not query:
            set_driver_session(chat_id, state="awaiting_broker_query")
            prompt_text = (
                "🏢 <b>Проверка брокера и MC:</b>\n\n"
                "Напиши номер MC (например: <code>MC 1045231</code>), название компании (например: <code>TQL</code>) "
                "или скопируй шапку из Rate Confirmation —\n"
                "проверю статус бонда BMC-84 ($75k), дни оплаты (DTP), одобрение факторингом и риски дабл-брокеринга."
            )
            send_telegram_message(chat_id, prompt_text, reply_to_message_id=msg_id, reply_markup=MAIN_KEYBOARD)
            return
        send_chat_action(chat_id, "typing")
        broker_card = verify_broker(query)
        send_telegram_message(chat_id, broker_card, reply_to_message_id=msg_id, reply_markup=MAIN_KEYBOARD)
        record_chat_turn(chat_id, "model", broker_card)
        return

    # Route & Fuel Strategic Analysis command
    is_route_command = (
        text.startswith("/route") or
        text.startswith("/fuel") or
        text.strip().lower() in ["🛣️ анализ маршрута и топлива", "анализ маршрута и топлива", "анализ маршрута", "маршрут"]
    )
    if is_route_command:
        parts = text.split(maxsplit=1)
        query_route = parts[1] if (len(parts) > 1 and (text.startswith("/route") or text.startswith("/fuel"))) else ""
        known_truck = profile.get("truck_type") if profile.get("truck_type") != "Неизвестно" else "Стингер 9-кар (Class 8)"
        fuel_card = profile.get("fuel_card", "Mudflap")
        fuel_discount = float(profile.get("fuel_discount", 0.45))
        cargo_type = profile.get("typical_cargo", "Груженый")

        if query_route:
            send_chat_action(chat_id, "typing")
            route_answer = analyze_car_hauler_route(
                route_text=query_route,
                driver_setup=known_truck,
                fuel_card=fuel_card,
                fuel_discount=fuel_discount,
                cargo=cargo_type
            )
            record_chat_turn(chat_id, "model", route_answer)
            send_telegram_message(chat_id, route_answer, reply_to_message_id=msg_id, reply_markup=MAIN_KEYBOARD)
            return

        set_driver_session(chat_id, state="awaiting_route_details")
        disc_text = f"-${fuel_discount:.2f}/gal" if fuel_discount > 0 else "0¢"
        prompt_msg = (
            f"🛣️ <b>Анализ маршрута и топлива:</b> <b>{known_truck}</b>\n"
            f"💳 Топливная программа: <b>{fuel_card}</b> ({disc_text})\n\n"
            f"📍 Нажми <b>«📍 Отправить мою гео-точку»</b> внизу, чтобы автоматически взять текущую локацию за старт,\n"
            f"либо напиши маршрут сообщением (например: <code>1033 Green Acres Rd, Eugene OR в Dallas TX</code> или <code>Копарт Атланта ➔ Майами</code>):"
        )
        send_telegram_message(chat_id, prompt_msg, reply_to_message_id=msg_id, reply_markup=ROUTE_KEYBOARD)
        record_chat_turn(chat_id, "model", prompt_msg)
        return

    # Route & Repair Location Handling Flow
    session = get_driver_session(chat_id)
    session_state = session.get("state")
    known_truck = profile.get("truck_type") if profile.get("truck_type") != "Неизвестно" else "Стингер 9-кар (Class 8)"
    fuel_card = profile.get("fuel_card", "Mudflap")
    fuel_discount = float(profile.get("fuel_discount", 0.45))
    cargo_type = profile.get("typical_cargo", "Груженый")

    # A. Did driver send location pin?
    if location:
        lat = location.get("latitude")
        lon = location.get("longitude")
        try:
            from route_advisor import reverse_geocode_osm
            loc_info = reverse_geocode_osm(lat, lon)
        except Exception:
            loc_info = {"display": f"{lat:.4f}, {lon:.4f}", "lat": lat, "lon": lon, "state": "US"}
        loc_str = loc_info.get("display")

        # 1. Route to repair if driver requested mechanic
        if session_state in ["awaiting_repair_inquiry", "awaiting_repair_location"]:
            last_q = session.get("last_query") or ""
            if last_q and len(last_q) > 6 and last_q.lower() not in ["ремонт", "механик", "мастер"]:
                set_driver_session(chat_id, state="idle")
                send_chat_action(chat_id, "find_location")
                repair_card = handle_repair_inquiry(text=last_q, lat=lat, lon=lon, location_str=loc_str)
                send_telegram_message(chat_id, repair_card, reply_to_message_id=msg_id, reply_markup=MAIN_KEYBOARD)
                record_chat_turn(chat_id, "model", repair_card)
                return
            else:
                set_driver_session(chat_id, state="awaiting_repair_problem", last_query=json.dumps(loc_info))
                loc_msg = (
                    f"📍 <b>Локация принята:</b> <b>{loc_str}</b>\n\n"
                    f"🛠️ <b>Какая помощь требуется? Напиши проблему:</b>\n"
                    f"• <b>Для твоего автовоза</b> (лопнул гидрошланг, вытек цилиндр, треснула рампа, сварка алюминия, DPF регенерация, воздух/тормоза)?\n"
                    f"• <b>Или повреждение клиентского авто</b> (вмятина, царапина, бордюрка на диске, скол — нужно сделать скрытно до сдачи на ярде)?"
                )
                send_telegram_message(chat_id, loc_msg, reply_to_message_id=msg_id, reply_markup=MAIN_KEYBOARD)
                record_chat_turn(chat_id, "model", loc_msg)
                return

        # 2. Overhang check by location pin
        if session_state == "awaiting_overhang_location":
            set_driver_session(chat_id, state="idle")
            send_chat_action(chat_id, "typing")
            overhang_card = get_overhang_guide(lat=lat, lon=lon)
            send_telegram_message(chat_id, overhang_card, reply_to_message_id=msg_id, reply_markup=MAIN_KEYBOARD)
            record_chat_turn(chat_id, "model", overhang_card)
            return

        # 3. Default Location pin sets origin for route planning
        set_driver_session(chat_id, state="awaiting_route_destination", last_query=json.dumps(loc_info))
        loc_msg = (
            f"📍 <b>Точка старта принята:</b> <b>{loc_str}</b>\n"
            f"🚛 Сетап: <b>{known_truck}</b> | 💳 Карта: <b>{fuel_card}</b>\n\n"
            f"🏁 <b>Куда едем?</b> Напиши пункт назначения:\n"
            f"(город, точный адрес разгрузки или аукцион Copart / Manheim)"
        )
        send_telegram_message(chat_id, loc_msg, reply_to_message_id=msg_id, reply_markup=MAIN_KEYBOARD)
        record_chat_turn(chat_id, "model", loc_msg)
        return

    # B. Was driver in awaiting session state?
    if session_state in [
        "awaiting_route_details", "awaiting_route_destination", "awaiting_fuel_details",
        "awaiting_repair_inquiry", "awaiting_repair_location", "awaiting_repair_problem",
        "awaiting_overhang_location", "awaiting_broker_query"
    ]:
        is_conversational = any(w in text.lower() for w in [
            "ты же", "знаешь", "в профиле", "с чего", "почему", "откуда",
            "зачем", "отмена", "стоп", "хватит", "нет", "не надо", "какой", "что ты", "главное меню", "меню"
        ])
        if is_conversational or text.strip() in ["⬅️ В главное меню", "Отмена"]:
            set_driver_session(chat_id, state="idle")
            if text.strip() in ["⬅️ В главное меню", "Отмена"]:
                send_telegram_message(chat_id, "Главное меню:", reply_to_message_id=msg_id, reply_markup=MAIN_KEYBOARD)
                return
            # Falls through to general dispatcher
        else:
            # 1. Repair problem follow-up
            if session_state == "awaiting_repair_problem":
                loc_info = {}
                try:
                    loc_info = json.loads(session.get("last_query") or "{}")
                except Exception:
                    loc_info = {}
                set_driver_session(chat_id, state="idle")
                send_chat_action(chat_id, "find_location")
                repair_card = handle_repair_inquiry(
                    text=text,
                    lat=loc_info.get("lat"),
                    lon=loc_info.get("lon"),
                    location_str=loc_info.get("display")
                )
                record_chat_turn(chat_id, "model", repair_card)
                send_telegram_message(chat_id, repair_card, reply_to_message_id=msg_id, reply_markup=MAIN_KEYBOARD)
                return

            # 2. Repair text inquiry with location in text
            if session_state in ["awaiting_repair_inquiry", "awaiting_repair_location"]:
                set_driver_session(chat_id, state="idle")
                send_chat_action(chat_id, "find_location")
                repair_card = handle_repair_inquiry(text=text)
                record_chat_turn(chat_id, "model", repair_card)
                send_telegram_message(chat_id, repair_card, reply_to_message_id=msg_id, reply_markup=MAIN_KEYBOARD)
                return

            # 3. Overhang location follow-up
            if session_state == "awaiting_overhang_location":
                set_driver_session(chat_id, state="idle")
                send_chat_action(chat_id, "typing")
                overhang_card = get_overhang_guide(text=text)
                record_chat_turn(chat_id, "model", overhang_card)
                send_telegram_message(chat_id, overhang_card, reply_to_message_id=msg_id, reply_markup=MAIN_KEYBOARD)
                return

            # 4. Broker query follow-up
            if session_state == "awaiting_broker_query":
                set_driver_session(chat_id, state="idle")
                send_chat_action(chat_id, "typing")
                broker_card = verify_broker(text)
                record_chat_turn(chat_id, "model", broker_card)
                send_telegram_message(chat_id, broker_card, reply_to_message_id=msg_id, reply_markup=MAIN_KEYBOARD)
                return

            # 5. Route Destination follow-up
            set_driver_session(chat_id, state="idle")
            origin_geo = None
            if session_state == "awaiting_route_destination":
                try:
                    origin_geo = json.loads(session.get("last_query") or "{}")
                except Exception:
                    origin_geo = None

            send_chat_action(chat_id, "typing")
            route_answer = analyze_car_hauler_route(
                route_text=text,
                origin_geo=origin_geo,
                driver_setup=known_truck,
                fuel_card=fuel_card,
                fuel_discount=fuel_discount,
                cargo=cargo_type
            )
            record_chat_turn(chat_id, "model", route_answer)
            send_telegram_message(chat_id, route_answer, reply_to_message_id=msg_id, reply_markup=MAIN_KEYBOARD)
            return

    # C. Route or Fuel inquiry in free-form text
    has_route_pattern = (
        bool(re.search(r'(?i)\b([а-яa-z0-9\s,\.\-]{3,}\s*(?:-|–|—|->|до|в|to)\s*[а-яa-z0-9\s,\.\-]{3,})\b', text)) and
        any(k in text.lower() for k in ["маршрут", "расход", "солярк", "дизел", "миль", "доехать", "route", "fuel", "miles", "копарт", "copart", "manheim", "манхейм", "аукцион", "-", "to", "до"])
    )
    if has_route_pattern and not is_conversational_fuel_query(text):
        send_chat_action(chat_id, "typing")
        route_answer = analyze_car_hauler_route(
            route_text=text,
            driver_setup=known_truck,
            fuel_card=fuel_card,
            fuel_discount=fuel_discount,
            cargo=cargo_type
        )
        record_chat_turn(chat_id, "model", route_answer)
        send_telegram_message(chat_id, route_answer, reply_to_message_id=msg_id, reply_markup=MAIN_KEYBOARD)
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

    # Claim interactive templates
    if data.startswith("claim_"):
        claim_type = data.replace("claim_", "")
        answer_callback_query(cb_id, text="Шаблон сформирован")
        claim_card, _ = handle_claim_command(claim_type)
        send_telegram_message(chat_id, claim_card, reply_markup=MAIN_KEYBOARD)
        return

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

    if data.startswith("setcard_"):
        card_choice = data.replace("setcard_", "")
        from_id = from_user.get("id") or chat_id
        prof = set_manual_fuel_card(from_id, card_choice)
        card_title = prof.get("fuel_card")
        answer_callback_query(cb_id, text=f"Топливная карта: {card_title}")
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
        {"command": "route", "description": "🛣️ Анализ маршрута и солярки"},
        {"command": "repair", "description": "🔧 Мастер рядом (трак или авто клиента)"},
        {"command": "broker", "description": "🏢 Проверка брокера по MC ($75k бонд)"},
        {"command": "overhang", "description": "⚖️ Свесы и весы (FAST Act)"},
        {"command": "claim", "description": "📋 Претензии: Детеншен, TONU, In-Op"},
        {"command": "profile", "description": "👤 Мой сетап и топливная карта"},
        {"command": "start", "description": "🚛 Главное меню диспетчера"},
        {"command": "help", "description": "🆘 Помощь дежурного диспетчера"}
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
    try:
        start_metrics_server(port=8000)
    except Exception as me:
        print(f"[WARN] Failed to start Prometheus metrics server: {me}")
    setup_telegram_commands()
    init_chat_history_db()
    init_fuel_session_db()
    try:
        try:
            from services.aaa_fuel_feed import init_state_fuel_table, sync_state_fuel_prices
        except ImportError:
            from aaa_fuel_feed import init_state_fuel_table, sync_state_fuel_prices
        init_state_fuel_table()
        sync_state_fuel_prices()
    except Exception as ex:
        print(f"[WARN] Initial AAA fuel sync error: {ex}")
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
