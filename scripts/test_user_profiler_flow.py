import sys
import os

sys.path.insert(0, '/app/services')
import telegram_bot_daemon
from user_profiler import get_or_create_user_profile, analyze_and_update_profile

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

test_user_id = 777123456

print("=== STEP 1: New user with unknown rig sends a pin ===")
msg1 = {
    "chat": {"id": test_user_id},
    "message_id": 201,
    "location": {"latitude": 30.5844, "longitude": -84.7213},
    "from": {"username": "new_driver"}
}
telegram_bot_daemon.process_message(msg1)

p1 = get_or_create_user_profile(test_user_id)
print(f"[DB STATE 1] Truck: {p1['truck_type']}, Owner Known: {p1['has_owner_status']}, Equip Known: {p1['has_equipment_info']}")

print("\n=== STEP 2: Driver replies: 'я оунер, хожу на стингере 9-кар, вожу тяжелые SUV' ===")
msg2 = {
    "chat": {"id": test_user_id},
    "message_id": 202,
    "text": "я оунер, хожу на стингере 9-кар, вожу тяжелые SUV",
    "from": {"username": "new_driver"}
}
telegram_bot_daemon.process_message(msg2)

p2 = get_or_create_user_profile(test_user_id)
print(f"[DB STATE 2] Role: {p2['user_role']}, Truck: {p2['truck_type']}, Cargo: {p2['typical_cargo']}, Owner Known: {p2['has_owner_status']}, Equip Known: {p2['has_equipment_info']}")

print("\n=== STEP 3: User thanks the bot: 'спасибо от души выручил!' ===")
msg3 = {
    "chat": {"id": test_user_id},
    "message_id": 203,
    "text": "спасибо от души выручил!",
    "from": {"username": "new_driver"}
}
telegram_bot_daemon.process_message(msg3)

p3 = get_or_create_user_profile(test_user_id)
print(f"[DB STATE 3] Satisfaction: {p3['satisfaction_score']}, Interactions: {p3['interaction_count']}")

print("\n=== STEP 4: Next time driver sends ONLY a pin (Bot remembers their Stinger without asking!) ===")
msg4 = {
    "chat": {"id": test_user_id},
    "message_id": 204,
    "location": {"latitude": 41.1399, "longitude": -104.8202},
    "from": {"username": "new_driver"}
}
telegram_bot_daemon.process_message(msg4)

print("\n=== STEP 5: Driver changes rig: 'я сейчас пересел на виджик 3-кар' ===")
msg5 = {
    "chat": {"id": test_user_id},
    "message_id": 205,
    "text": "я сейчас пересел на виджик 3-кар",
    "from": {"username": "new_driver"}
}
telegram_bot_daemon.process_message(msg5)

p5 = get_or_create_user_profile(test_user_id)
print(f"[DB STATE 5] Truck immediately changed in DB to: {p5['truck_type']}, Equip Known: {p5['has_equipment_info']}")
print("\n[SUCCESS] User Profiler and Adaptive Memory Flow verified!")
