import os
import sys
import logging
from telethon import TelegramClient, events
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
N8N_WEBHOOK_URL = os.getenv("N8N_TELEGRAM_WEBHOOK", "http://n8n:5678/webhook/telegram-ingest")

if not API_ID or not API_HASH:
    logging.warning("TELEGRAM_API_ID или TELEGRAM_API_HASH не заданы в .env. Бот ожидает настройки.")
    # Не падаем в рестарт-луп, даем контейнеру жить
    import time
    while True:
        time.sleep(3600)

client = TelegramClient("/app/sessions/dispatcher_session", int(API_ID), API_HASH)

@client.on(events.NewMessage)
async def handle_new_message(event):
    if event.is_channel or event.is_group:
        payload = {
            "chat_id": event.chat_id,
            "message_id": event.id,
            "text": event.raw_text,
            "date": event.date.isoformat() if event.date else None
        }
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
EOFcat << 'EOF' > telethon_bot/main.py
import os
import sys
import logging
from telethon import TelegramClient, events
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
N8N_WEBHOOK_URL = os.getenv("N8N_TELEGRAM_WEBHOOK", "http://n8n:5678/webhook/telegram-ingest")

if not API_ID or not API_HASH:
    logging.warning("TELEGRAM_API_ID или TELEGRAM_API_HASH не заданы в .env. Бот ожидает настройки.")
    # Не падаем в рестарт-луп, даем контейнеру жить
    import time
    while True:
        time.sleep(3600)

client = TelegramClient("/app/sessions/dispatcher_session", int(API_ID), API_HASH)

@client.on(events.NewMessage)
async def handle_new_message(event):
    if event.is_channel or event.is_group:
        payload = {
            "chat_id": event.chat_id,
            "message_id": event.id,
            "text": event.raw_text,
            "date": event.date.isoformat() if event.date else None
        }
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
