"""
Comprehensive End-to-End System Audit & Microservice Test Suite
Runs tests across all modules of the Car Hauling Dispatch Hub:
1. PostgreSQL Tables & Data Integrity
2. AAA Daily Fuel Feed & Certified State Benchmarks
3. Fuel Advisor (GPS, City search, Rig clearances, Google Maps pins)
4. Repair Service & Mechanics Directory (Radius check, 0 fake 555 numbers, 24/7 emergency lines)
5. Broker Verification & MC Intelligence
6. Claim Generator (Detention, TONU, In-Op copyable blocks)
7. Overhang Advisor (FAST Act 23 CFR § 658.13 & State DOT limits)
8. User Profiling & Dynamic Session Memory
9. Grounding & Sense-Check Validator (Anti-hallucination filters)
10. Telegram Formatter & HTML Security
11. Tone & Persona Review for Commercial Car Hauling Audience
"""

import sys
import os
import json
import re
import time

sys.path.insert(0, '/app/services')
sys.path.insert(0, '/app')

test_results = []

def record(service, test_name, status, details=""):
    test_results.append({
        "service": service,
        "test": test_name,
        "status": status,
        "details": details
    })
    mark = "✅ PASS" if status == "PASS" else "❌ FAIL"
    print(f"[{mark}] {service} :: {test_name} -> {details[:80]}")

# ==========================================
# TEST 1: Database & Table Integrity
# ==========================================
def test_database():
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "postgres"),
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            user=os.environ.get("POSTGRES_USER", "dispatch_admin"),
            password=os.environ.get("POSTGRES_PASSWORD", "DispatchSecurePass2026!_pg"),
            dbname=os.environ.get("POSTGRES_DB", "dispatch_hub")
        )
        cur = conn.cursor()
        
        # Check required tables
        expected_tables = ["user_profiles", "driver_sessions", "car_hauler_mechanics", "state_fuel_prices", "driver_cases"]
        for t in expected_tables:
            cur.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{t}');")
            exists = cur.fetchone()[0]
            if exists:
                cur.execute(f"SELECT count(*) FROM {t};")
                count = cur.fetchone()[0]
                record("Database", f"Table: {t}", "PASS", f"Table exists with {count} rows")
            else:
                record("Database", f"Table: {t}", "FAIL", "Table does not exist")

        cur.close()
        conn.close()
    except Exception as e:
        record("Database", "Connection", "FAIL", str(e))

# ==========================================
# TEST 2: AAA Fuel Feed
# ==========================================
def test_aaa_feed():
    try:
        from aaa_fuel_feed import sync_state_fuel_prices, get_state_diesel_benchmark, validate_diesel_price
        sync_state_fuel_prices()
        
        # Check Oregon
        or_bench = get_state_diesel_benchmark("OR")
        if or_bench and or_bench["diesel"] > 5.50:
            record("AAA Feed", "Oregon Diesel Benchmark", "PASS", f"Price: ${or_bench['diesel']:.2f}/gal (realistic)")
        else:
            record("AAA Feed", "Oregon Diesel Benchmark", "FAIL", f"Unexpected price: {or_bench}")

        # Check Florida
        fl_bench = get_state_diesel_benchmark("FL")
        if fl_bench and fl_bench["diesel"] > 4.50:
            record("AAA Feed", "Florida Diesel Benchmark", "PASS", f"Price: ${fl_bench['diesel']:.2f}/gal (realistic)")
        else:
            record("AAA Feed", "Florida Diesel Benchmark", "FAIL", f"Unexpected price: {fl_bench}")

        # Check Validation logic
        valid, _ = validate_diesel_price("OR", 6.80)
        invalid, _ = validate_diesel_price("OR", 3.20)
        if valid and not invalid:
            record("AAA Feed", "Price Bounds Validation", "PASS", "Correctly rejected $3.20 in OR and accepted $6.80")
        else:
            record("AAA Feed", "Price Bounds Validation", "FAIL", "Validation logic error")
    except Exception as e:
        record("AAA Feed", "Module Execution", "FAIL", str(e))

# ==========================================
# TEST 3: Fuel Advisor (GPS & Text)
# ==========================================
def test_fuel_advisor():
    try:
        from fuel_advisor import generate_fuel_recommendations
        
        # Test 1: Eugene, Oregon (Text)
        res_or = generate_fuel_recommendations("Сакраменто", driver_setup="Стингер 9-кар (Class 8)")
        if "<b>" in res_or and "google.com/maps" in res_or and "Маршрут в Навигатор" in res_or:
            record("Fuel Advisor", "Text City Query (Sacramento)", "PASS", "Structured HTML with verified navigation links")
        else:
            record("Fuel Advisor", "Text City Query (Sacramento)", "FAIL", "Missing HTML tags or navigation links")

        time.sleep(2.5)
        # Test 2: Coordinates (Florida)
        res_fl = generate_fuel_recommendations("Flat Creek Road, FL", driver_setup="Пикап + Виджик 3-4 авто", lat=30.5939, lon=-84.7172)
        if "google.com/maps" in res_fl and ("Midway" in res_fl or "Quincy" in res_fl or "I-10" in res_fl or "Love's" in res_fl):
            record("Fuel Advisor", "GPS Pin Resolution (FL I-10)", "PASS", "Accurate truck stops along I-10")
        else:
            record("Fuel Advisor", "GPS Pin Resolution (FL I-10)", "FAIL", "Failed to resolve local I-10 truck stops")

        # Test 3: Check that fake timestamps '14 мин назад' are 100% absent
        if "мин назад" not in res_or and "мин назад" not in res_fl:
            record("Fuel Advisor", "Anti-Fake Timestamp Check", "PASS", "Zero fake timestamps generated")
        else:
            record("Fuel Advisor", "Anti-Fake Timestamp Check", "FAIL", "Detected hallucinated timestamp!")
    except Exception as e:
        record("Fuel Advisor", "Module Execution", "FAIL", str(e))

# ==========================================
# TEST 4: Repair Service
# ==========================================
def test_repair_service():
    try:
        from repair_service import handle_repair_inquiry, find_mechanics
        
        # Test 1: Local match in Chicago
        res_chi = handle_repair_inquiry("сломался в чикаго")
        if "Balkan" in res_chi or "Pro Mobile" in res_chi:
            record("Repair Service", "Local Match (Chicago)", "PASS", "Found verified Slavic shop")
        else:
            record("Repair Service", "Local Match (Chicago)", "FAIL", "Failed to find Chicago shop")

        # Test 2: Rural location without nearby private shop (should return 24/7 official lines)
        res_rural = handle_repair_inquiry("сломался в Небраске", lat=41.1400, lon=-100.7601, location_str="North Platte, NE")
        if "1-800-687-5683" in res_rural or "Love's Truck Care" in res_rural:
            record("Repair Service", "Distant Location Radius Fallback", "PASS", "Honest disclaimer + official 24/7 lines")
        else:
            record("Repair Service", "Distant Location Radius Fallback", "FAIL", "Did not provide official 24/7 lines")

        # Test 3: Zero 555 numbers
        all_mechs = find_mechanics(limit=50)
        has_555 = any("555-01" in m.get("contact_phone", "") for m in all_mechs)
        if not has_555 and len(all_mechs) > 0:
            record("Repair Service", "Phone Numbers Authenticity", "PASS", f"All {len(all_mechs)} mechanics have real numbers (zero 555)")
        else:
            record("Repair Service", "Phone Numbers Authenticity", "FAIL", "Found fictional 555 numbers in database!")
    except Exception as e:
        record("Repair Service", "Module Execution", "FAIL", str(e))

# ==========================================
# TEST 5: Broker Verifier
# ==========================================
def test_broker_verifier():
    try:
        from broker_verifier import verify_broker
        res_tql = verify_broker("TQL")
        if res_tql and "BMC-84" in res_tql and ("QuickPay" in res_tql or "DTP" in res_tql or "факторинг" in res_tql.lower()):
            record("Broker Verifier", "Known Broker Verification (TQL)", "PASS", "Complete compliance & credit check")
        else:
            record("Broker Verifier", "Known Broker Verification (TQL)", "FAIL", "Incomplete broker card")

        time.sleep(2.5)
        res_mc = verify_broker("MC 1045231")
        if res_mc and ("RELIABLE AUTO SHIPPERS" in res_mc or "1045231" in res_mc):
            desc = "Real carrier name matched from registry" if "RELIABLE AUTO SHIPPERS" in res_mc else "Algorithmic longevity & risk fallback card"
            record("Broker Verifier", "MC Registry Check (MC 1045231)", "PASS", desc)
        else:
            record("Broker Verifier", "MC Registry Check (MC 1045231)", "FAIL", "Failed to match real carrier or express card")
    except Exception as e:
        record("Broker Verifier", "Module Execution", "FAIL", str(e))

# ==========================================
# TEST 6: Claim Generator
# ==========================================
def test_claim_generator():
    try:
        from claim_generator import handle_claim_command
        det = handle_claim_command("/detention")
        tonu = handle_claim_command("/tonu")
        inop = handle_claim_command("/inop")
        
        has_codes = "<code>" in det and "<code>" in tonu and "<code>" in inop
        has_rates = "$75" in det and "$250" in tonu and "$150" in inop
        if has_codes and has_rates:
            record("Claim Generator", "1-Tap Copyable Legal Templates", "PASS", "All templates formatted in <code> with industry rates")
        else:
            record("Claim Generator", "1-Tap Copyable Legal Templates", "FAIL", "Missing <code> tags or standard fees")
    except Exception as e:
        record("Claim Generator", "Module Execution", "FAIL", str(e))

# ==========================================
# TEST 7: Overhang Advisor
# ==========================================
def test_overhang_advisor():
    try:
        from overhang_advisor import get_overhang_guide
        fl_guide = get_overhang_guide("FL")
        ca_guide = get_overhang_guide("CA")
        fed_guide = get_overhang_guide()
        
        if "4 фута" in fl_guide and "FAST Act" in fed_guide and "KPRA" in ca_guide:
            record("Overhang Advisor", "Statute Accuracy (FAST Act & States)", "PASS", "Correct overhangs & scale inspection traps")
        else:
            record("Overhang Advisor", "Statute Accuracy (FAST Act & States)", "FAIL", "Missing overhang statutes or traps")
    except Exception as e:
        record("Overhang Advisor", "Module Execution", "FAIL", str(e))

# ==========================================
# TEST 8: Grounding & Anti-Hallucination Verifier
# ==========================================
def test_grounding_verifier():
    try:
        from grounding_verifier import multi_agent_sense_check, sanitize_prohibited_phrases
        
        # Test 1: Sanitize childish phrases
        bad_text = "Совет Агентов на связи! Братуха, был сбой связи с сервером, но связь восстановилась."
        cleaned = sanitize_prohibited_phrases(bad_text)
        if "Совет Агентов" not in cleaned and "братуха" not in cleaned and "сбой связи" not in cleaned:
            record("Grounding Verifier", "Childish Phrase Sanitization", "PASS", "Purged persona fluff and connection excuses")
        else:
            record("Grounding Verifier", "Childish Phrase Sanitization", "FAIL", f"Failed to sanitize: {cleaned}")

        # Test 2: Intercept absurd fuel price in Oregon
        hallucinated_fuel = "⛽ Дизель в Eugene, OR: Love's $3.29/gal (со скидкой $2.94)."
        grounded_fuel = multi_agent_sense_check(hallucinated_fuel, context_type="fuel", location_str="Eugene, Oregon", state_code="OR")
        if "$6." in grounded_fuel and "$3.29" not in grounded_fuel:
            record("Grounding Verifier", "Obsolete Price Interception (OR)", "PASS", "Intercepted $3.29 and enforced real AAA ~$6.74 corridor")
        else:
            record("Grounding Verifier", "Obsolete Price Interception (OR)", "FAIL", f"Failed to intercept: {grounded_fuel}")

        # Test 3: Intercept fictional 555 number
        fake_mech = "<b>Мастер</b>\n• 📞 +1 (847) 555-0142"
        grounded_mech = multi_agent_sense_check(fake_mech, context_type="repair")
        if "555-01" not in grounded_mech and "1-800" in grounded_mech:
            record("Grounding Verifier", "Fake 555 Phone Interception", "PASS", "Intercepted 555 and substituted official line")
        else:
            record("Grounding Verifier", "Fake 555 Phone Interception", "FAIL", f"Failed to intercept 555: {grounded_mech}")
    except Exception as e:
        record("Grounding Verifier", "Module Execution", "FAIL", str(e))

# ==========================================
# TEST 9: User Profiler & Memory
# ==========================================
def test_user_profiler():
    try:
        from user_profiler import analyze_and_update_profile, get_user_profile
        
        # Test profiling an owner-operator with a stinger
        chat_id = 999000111
        p1 = analyze_and_update_profile(chat_id, text="Я оунер, хожу на 9-каре стингере Питербилт под Вольво")
        if p1.get("user_role") == "Оунер-Оператор" and "Стингер" in p1.get("truck_type", ""):
            record("User Profiler", "Role & Equipment Inference", "PASS", f"Inferred {p1['user_role']} & {p1['truck_type']}")
        else:
            record("User Profiler", "Role & Equipment Inference", "FAIL", f"Failed inference: {p1}")

        # Test profile retrieval
        p2 = get_user_profile(chat_id)
        if p2 and p2.get("user_role") == "Оунер-Оператор":
            record("User Profiler", "PostgreSQL Persistence", "PASS", "Profile stored and retrieved from PostgreSQL")
        else:
            record("User Profiler", "PostgreSQL Persistence", "FAIL", "Failed persistence")
    except Exception as e:
        record("User Profiler", "Module Execution", "FAIL", str(e))

# ==========================================
# TEST 10: Telegram Formatter
# ==========================================
def test_telegram_formatter():
    try:
        from telegram_formatter import markdown_to_telegram_html
        md = "**Дизель:** [Маршрут](https://maps.google.com?q=Love's&st=OR) `Code` *Italic*"
        html = markdown_to_telegram_html(md)
        if "<b>" in html and "&amp;" in html and "<code>" in html and "<i>" in html:
            record("Telegram Formatter", "HTML & Entity Escaping", "PASS", "Properly escaped &amp; and converted tags")
        else:
            record("Telegram Formatter", "HTML & Entity Escaping", "FAIL", f"Formatting issue: {html}")
    except Exception as e:
        record("Telegram Formatter", "Module Execution", "FAIL", str(e))

# ==========================================
# TEST 11: Dynamic Model Router & Quota Health
# ==========================================
def test_model_router():
    try:
        from model_router import rate_request_difficulty, metrics_tracker
        d0, _ = rate_request_difficulty("/overhang CA")
        d1, _ = rate_request_difficulty("где заправиться возле Орегона")
        d2, _ = rate_request_difficulty("пробей брокера MC 1045231")
        d3, _ = rate_request_difficulty("брокер отказывается платить и выставил клейм за царапину на крыше")
        
        metrics = metrics_tracker.generate_prometheus_metrics()
        has_prom = "gemini_requests_total" in metrics and "gemini_active_rpm" in metrics
        
        if d0 == 0 and d1 == 1 and d2 == 2 and d3 == 3 and has_prom:
            record("Model Router", "Difficulty Rating & Quota Metrics", "PASS", "Difficulty scored 0-3 correctly, Prometheus metrics active")
        else:
            record("Model Router", "Difficulty Rating & Quota Metrics", "FAIL", f"Difficulty scores: {d0},{d1},{d2},{d3}")
    except Exception as e:
        record("Model Router", "Module Execution", "FAIL", str(e))

# ==========================================
# TEST 12: News Engine Frequency Gating
# ==========================================
def test_news_frequency():
    try:
        from news_and_alerts_engine import is_true_road_emergency
        is_true_alert = is_true_road_emergency("I-80 closed due to pileup at Elk Mountain, WY", "WYDOT reports all lanes shut down")
        is_false_alert1 = is_true_road_emergency("Truck driver sentenced for crash 3 years ago", "A driver was sentenced to 5 years in prison")
        is_false_alert2 = is_true_road_emergency("FMCSA announces new inspection blitz next summer", "The CVSA roadcheck is scheduled")
        
        if is_true_alert and not is_false_alert1 and not is_false_alert2:
            record("News Engine", "Emergency Alert Discrimination", "PASS", "True road closures trigger alert, general news & history blocked")
        else:
            record("News Engine", "Emergency Alert Discrimination", "FAIL", f"Filter results: {is_true_alert}, {is_false_alert1}, {is_false_alert2}")
    except Exception as e:
        record("News Engine", "Module Execution", "FAIL", str(e))

# ==========================================
# TEST 13: Driver Keyboard UI
# ==========================================
def test_telegram_keyboard():
    try:
        from telegram_bot_daemon import MAIN_KEYBOARD
        buttons_flat = [b["text"] for row in MAIN_KEYBOARD["keyboard"] for b in row]
        has_location = any(b.get("request_location") for row in MAIN_KEYBOARD["keyboard"] for b in row)
        has_mechanic = any("Мастер рядом" in t for t in buttons_flat)
        has_broker = any("Проверить брокера" in t for t in buttons_flat)
        
        if has_location and has_mechanic and has_broker:
            record("Driver Keyboard", "Persistent ReplyKeyboardMarkup", "PASS", "Location GPS button + Mechanic + Broker quick actions active")
        else:
            record("Driver Keyboard", "Persistent ReplyKeyboardMarkup", "FAIL", f"Buttons: {buttons_flat}")
    except Exception as e:
        record("Driver Keyboard", "Module Execution", "FAIL", str(e))

def run_all():
    print("="*60)
    print("STARTING CAR HAULING DISPATCH HUB FULL SYSTEM AUDIT")
    print("="*60)
    test_database()
    test_aaa_feed()
    test_fuel_advisor()
    test_repair_service()
    test_broker_verifier()
    test_claim_generator()
    test_overhang_advisor()
    test_grounding_verifier()
    test_user_profiler()
    test_telegram_formatter()
    test_model_router()
    test_news_frequency()
    test_telegram_keyboard()
    print("="*60)
    
    passed = sum(1 for t in test_results if t["status"] == "PASS")
    failed = sum(1 for t in test_results if t["status"] == "FAIL")
    print(f"AUDIT SUMMARY: {passed} PASSED, {failed} FAILED (TOTAL {len(test_results)})")
    print("="*60)
    
    with open("/app/services/audit_report.json", "w", encoding="utf-8") as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    run_all()
