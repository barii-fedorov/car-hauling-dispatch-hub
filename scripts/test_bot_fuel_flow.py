import sys
import json

sys.path.insert(0, '/app/services')
import telegram_bot_daemon

def mock_send(chat_id, text, reply_to_message_id=None, message_thread_id=None, reply_markup=None):
    print(f"\n[BOT OUTGOING TO CHAT {chat_id}]:")
    print(text)
    print("-" * 50)
    return {"ok": True, "result": {"message_id": 9999}}

def mock_edit(chat_id, message_id, text, reply_markup=None):
    print(f"\n[BOT EDITED MESSAGE {message_id} IN CHAT {chat_id}]:")
    print(text)
    print("-" * 50)
    return {"ok": True, "result": {"message_id": message_id}}

telegram_bot_daemon.send_telegram_message = mock_send
telegram_bot_daemon.edit_telegram_message = mock_edit

test_chat_id = 999888777

print("=== STEP 1: Driver asks about fuel ===")
msg1 = {
    "chat": {"id": test_chat_id},
    "message_id": 101,
    "text": "Братуха, где солярки залить подешевле?",
    "from": {"username": "test_driver", "first_name": "Даниэль"}
}
telegram_bot_daemon.process_message(msg1)

print("\n=== STEP 2: Driver sends GPS location pin from Florida (Gadsden County) ===")
msg2 = {
    "chat": {"id": test_chat_id},
    "message_id": 102,
    "text": "Стингер 9-кар (Class 8), груженый 7-8 авто",
    "location": {"latitude": 30.5844, "longitude": -84.7213},
    "from": {"username": "test_driver", "first_name": "Даниэль"}
}
telegram_bot_daemon.process_message(msg2)
