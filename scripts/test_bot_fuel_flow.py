import sys
import json

sys.path.insert(0, '/app/services')
import telegram_bot_daemon

# Mock send_telegram_message to print outgoing messages to console
def mock_send(chat_id, text, reply_to_message_id=None, message_thread_id=None, reply_markup=None):
    print(f"\n[BOT OUTGOING TO CHAT {chat_id}]:")
    print(text)
    print("-" * 50)
    return {"ok": True, "result": {"message_id": 9999}}

telegram_bot_daemon.send_telegram_message = mock_send

test_chat_id = 999888777

print("=== STEP 1: Driver asks about fuel ===")
msg1 = {
    "chat": {"id": test_chat_id},
    "message_id": 101,
    "text": "Братуха, где солярки залить подешевле?",
    "from": {"username": "test_driver", "first_name": "Иван"}
}
telegram_bot_daemon.process_message(msg1)

print("\n=== STEP 2: Driver sends GPS location pin and specifies setup ===")
msg2 = {
    "chat": {"id": test_chat_id},
    "message_id": 102,
    "text": "Стингер 9-кар, везу 8 тяжелых SUV на Денвер",
    "location": {"latitude": 41.1399, "longitude": -104.8202},
    "from": {"username": "test_driver", "first_name": "Иван"}
}
telegram_bot_daemon.process_message(msg2)
