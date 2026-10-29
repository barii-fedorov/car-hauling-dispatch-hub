#!/usr/bin/env python3
"""
Post and pin README navigator in Telegram Channel "Грузовики на базу" (-1004424371115)
"""
import os
import json
import urllib.request

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    print("[ERROR] TELEGRAM_BOT_TOKEN environment variable is missing!")
    exit(1)
CHAT_ID = os.environ.get("CHANNEL_CHAT_ID", "-1004424371115")

PIN_TEXT = (
    "🚛 *НАВИГАТОР ПО КАНАЛУ «ГРУЗОВИКИ НА БАЗУ» И ИИ-ДИСПЕТЧЕРУ @CarHaulerSOS_bot*\n\n"
    "Добро пожаловать в сообщество автовозного диспатча *«Грузовики на базу»*!\n"
    "Наше железное правило: **ВОДИТЕЛЬ ВСЕГДА ПРАВ**.\n"
    "Мы работаем по фиксированной ставке 7% и защищаем оунер-оператора от произвола брокеров, задержек и штрафов.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "🤖 *КТО ТАКОЙ @CarHaulerSOS_bot?*\n"
    "Это ваш личный **Совет Агентов** 24/7 в одном кармане:\n"
    "• ⚖️ *Агент-Юрист:* Заберет деньги за простой (Detention $75/ч после 2ч), срыв (Dry Run / TONU $200–$250) и зажмет брокера через бонд BMC-84 ($75k).\n"
    "• 🛠️ *Агент-Техник:* Развесовка Bridge Formula B, высоты (Восток 13'6\", Запад 14'0\"), углы рамп и доплата за ин-опы с лебедой ($150).\n"
    "• 🧭 *Главный Диспетчер:* Понимает автовозный сленг с полуслова, помогает с прокладкой маршрута и соляркой.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "🔥 *В КАКИХ СИТУАЦИЯХ ПИСАТЬ БОТУ:*\n"
    "1. ⏳ *Детеншен:* Стоишь на дилершипе/аукционе >2 часов — бот составит клейм брокеру.\n"
    "2. 🚫 *Срыв (TONU):* Приехал, а тачки нет/отмена — забираем $200–$250.\n"
    "3. 🪝 *Нежданный Ин-оп:* Колеса заклинило, пневма легла — чарджим $150 за лебедку до погрузки.\n"
    "4. 🔍 *Проверка брокера:* Присылай MC — проверим бонд, возраст и дабл-брокеров.\n"
    "5. ⛽ *Солярка:* Назови сетап (стингер vs виджик) — покажем заправки без риска снести козырек.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "💬 *КАК ОБРАЩАТЬСЯ:*\n"
    "👉 Открой диалог: @CarHaulerSOS_bot\n"
    "Пиши текстом или голосом в свободной форме (как говоришь в кабине трака)!\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "🏷️ *НАВИГАЦИЯ ПО КАНАЛУ (ХЕШТЕГИ):*\n"
    "#Новости · #Алерт · #Весы · #Ставки · #SOS_Совет\n"
    "#I80 · #I70 · #I10 · #I40 · #I95 · #I75 · #I15 · #I5\n"
    "#Midwest · #WestCoast · #TX · #PA · #OH · #WY · #CO\n"
    "#Стингер · #Виджик · #ХайМаунт · #ИнОп · #Детеншен\n\n"
    "🛡️ *Диспетчерская «Грузовики на базу» — надежный тыл на дороге!*"
)

def main():
    print(f"Sending PIN README to channel {CHAT_ID}...")
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": PIN_TEXT,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode())
        msg_id = res["result"]["message_id"]
        print(f"Message published successfully! Message ID: {msg_id}")

    # Pin the message
    pin_url = f"https://api.telegram.org/bot{TOKEN}/pinChatMessage"
    pin_payload = {
        "chat_id": CHAT_ID,
        "message_id": msg_id,
        "disable_notification": False
    }
    pin_req = urllib.request.Request(
        pin_url,
        data=json.dumps(pin_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(pin_req, timeout=15) as resp:
        print("Pin response:", resp.read().decode())

if __name__ == "__main__":
    main()
