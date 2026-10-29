import os
import sys
import re
import logging
from telethon import TelegramClient, events
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
N8N_WEBHOOK_URL = os.getenv("N8N_TELEGRAM_WEBHOOK", "http://n8n:5678/webhook/telegram-ingest")

MECHANIC_KEYWORDS = re.compile(
    r'(?i)\b(ремонт|сварка|сварщик|гидравлик|автовоз|выезд\s+на\s+трассу|'
    r'road\s*service|mobile\s*mechanic|трак[- ]?шоп|дерейт|force\s*regen|'
    r'пневмоподушк|boydstun|cottrell|kaufman)\b'
)
PHONE_REGEX = re.compile(r'(\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?[2-9]\d{2}[-.\s]?\d{4}')

if not API_ID or not API_HASH:
    logging.warning("TELEGRAM_API_ID или TELEGRAM_API_HASH не заданы в .env. Бот ожидает настройки.")
    import time
    while True:
        time.sleep(3600)

client = TelegramClient("/app/sessions/dispatcher_session", int(API_ID), API_HASH)

@client.on(events.NewMessage)
async def handle_new_message(event):
    if event.is_channel or event.is_group:
        raw_text = event.raw_text or ""
        payload = {
            "chat_id": event.chat_id,
            "message_id": event.id,
            "text": raw_text,
            "date": event.date.isoformat() if event.date else None
        }

        # Check if message contains a mechanic/repair lead
        if MECHANIC_KEYWORDS.search(raw_text) and PHONE_REGEX.search(raw_text):
            payload["lead_type"] = "mechanic_candidate"
            logging.info(f"[MECHANIC LEAD INTERCEPTED] Chat {event.chat_id}: {raw_text[:80]}")

        try:
            requests.post(N8N_WEBHOOK_URL, json=payload, timeout=5)
        except Exception as e:
            logging.error(f"Ошибка отправки вебхука в n8n: {e}")

async def main():
    await client.start()
    logging.info("Telethon Userbot успешно запущен и слушает события...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
