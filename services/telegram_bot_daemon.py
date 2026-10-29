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

# Config & Credentials loaded securely from Environment Variables
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "-1004420587350")

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

def send_telegram_message(chat_id, text, reply_to_message_id=None):
    try:
        url = f"{API_URL}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError:
        try:
            payload.pop("parse_mode", None)
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as ex:
            print(f"[ERROR] Failed to send fallback message: {ex}")
    except Exception as e:
        print(f"[ERROR] Failed to send message: {e}")

def ask_gemini(user_message):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"SYSTEM INSTRUCTIONS:\n{SYSTEM_PROMPT}\n\nUSER MESSAGE:\n{user_message}"}]
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
    from_user = msg.get("from", {})
    username = from_user.get("username", from_user.get("first_name", "оунер"))

    if not text or not chat_id:
        return

    print(f"[MSG] From @{username} (chat {chat_id}): {text}")

    # Start command
    if text.startswith("/start"):
        welcome_text = (
            "🚛 *Здорово, оунер! На связи Совет Агентов автовозного диспатча («Грузовики на базу»).*\n\n"
            "Мы прикрываем твою спину на дороге 24/7. Наш принцип — **водитель всегда прав**.\n\n"
            "🔥 *Чем помогаем прямо сейчас:*\n"
            "• ⚖️ **Отжать деньги у брокера:** Простой (Detention $75/ч после 2ч), срыв (Dry Run / TONU $200–$250)\n"
            "• 🛠️ **Ин-опы и развесовка:** Доплата за лебеду ($150), высоты и Bridge Formula B\n"
            "• 🔍 **Проверка брокера:** Бонд $75,000 BMC-84, возраст MC и защита от дабл-брокеринга\n"
            "• ⛽ **Солярка и трак-стопы:** Оптимальные цены под твой сетап (стингер vs виджик) и IFTA\n\n"
            "👉 *Просто напиши сюда свою проблему, номер MC брокера или вопрос — Совет сразу ответит!*"
        )
        send_telegram_message(chat_id, welcome_text, reply_to_message_id=msg_id)
        return

    # Indicate typing to user
    send_chat_action(chat_id, "typing")

    # Generate answer via Council of Agents
    answer = ask_gemini(text)

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

def run_bot():
    print(f"[START] Starting Telegram Bot Daemon for @CarHaulerSOS_bot...")
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
        except urllib.error.URLError as e:
            print(f"[RETRY] Network connection: {e}")
            time.sleep(3)
        except Exception as e:
            print(f"[ERROR] Polling loop error: {e}")
            time.sleep(3)

if __name__ == "__main__":
    run_bot()
