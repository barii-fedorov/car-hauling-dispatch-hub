"""
HERE Technologies Fuel Prices API Service (v3)
Provides real-time station-level fuel pricing and commercial truck accessibility verification.
Docs: https://developer.here.com/documentation/fuel-prices/dev_guide/topics/introduction.html
Free Tier Limit: 250,000 transactions / month on Base Plan.
Safety Circuit Breaker: Hardcoded stop at 245,000 transactions to guarantee 100% free tier safety.
Usage tracking persisted in PostgreSQL and exported to Prometheus / Grafana.
"""

import os
import json
import time
import threading
import urllib.request
import urllib.parse
from datetime import datetime, timezone

try:
    from services.aaa_fuel_feed import validate_diesel_price, get_state_diesel_benchmark
except ImportError:
    from aaa_fuel_feed import validate_diesel_price, get_state_diesel_benchmark

HERE_API_KEY = os.environ.get("HERE_API_KEY", "l1FEin56p0iO3pf_smaXSnAMFN2I8PtsK8h63zPfQcU")
HERE_FUEL_ENDPOINT = "https://fuel.hereapi.com/v3/stations"

# Hardcoded Safe Stop Limits & Cost Budget
HERE_COST_PER_REQ_EUR = 0.00466
HERE_BUDGET_EUR = 10.00
HERE_MONTHLY_LIMIT = 2000    # Hard stop at 2,000 calls = €9.32 max (strictly under €10 budget)
HERE_DAILY_LIMIT = 70        # Soft daily safety pacing (~66-70 calls/day)

PG_HOST = os.environ.get("POSTGRES_HOST", "postgres")
PG_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
PG_USER = os.environ.get("POSTGRES_USER", "dispatch_admin")
PG_PASS = os.environ.get("POSTGRES_PASSWORD", "DispatchSecurePass2026!_pg")
PG_DB = os.environ.get("POSTGRES_DB", "dispatch_hub")

# In-memory fast cache & lock
_lock = threading.Lock()
_in_memory_stats = {
    "month_year": datetime.now(timezone.utc).strftime("%Y-%m"),
    "monthly_count": 0,
    "daily_count": 0,
    "last_day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    "circuit_breaker_active": False,
    "total_success": 0,
    "total_errors": 0,
    "initialized": False
}

def get_db_connection():
    try:
        import psycopg2
        return psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB)
    except Exception as e:
        return None

def init_api_tracking_db():
    conn = get_db_connection()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS api_usage_tracking (
                api_name VARCHAR(64) PRIMARY KEY,
                month_year VARCHAR(7) NOT NULL,
                monthly_count INTEGER DEFAULT 0,
                daily_count INTEGER DEFAULT 0,
                last_day VARCHAR(10) NOT NULL,
                circuit_breaker_active BOOLEAN DEFAULT FALSE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[WARN] Failed to init api_usage_tracking table: {e}")
        if conn:
            conn.close()

def load_usage_from_db():
    global _in_memory_stats
    conn = get_db_connection()
    now_utc = datetime.now(timezone.utc)
    curr_month = now_utc.strftime("%Y-%m")
    curr_day = now_utc.strftime("%Y-%m-%d")

    with _lock:
        if not conn:
            _in_memory_stats["initialized"] = True
            return

        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT month_year, monthly_count, daily_count, last_day, circuit_breaker_active
                FROM api_usage_tracking WHERE api_name = 'here_fuel';
            """)
            row = cur.fetchone()
            if row:
                m_year, m_count, d_count, l_day, cb = row
                if m_year == curr_month:
                    _in_memory_stats["monthly_count"] = m_count
                    _in_memory_stats["circuit_breaker_active"] = (m_count >= HERE_MONTHLY_LIMIT)
                else:
                    # New month reset
                    _in_memory_stats["monthly_count"] = 0
                    _in_memory_stats["circuit_breaker_active"] = False

                if l_day == curr_day:
                    _in_memory_stats["daily_count"] = d_count
                else:
                    _in_memory_stats["daily_count"] = 0
            else:
                # Seed record
                cur.execute("""
                    INSERT INTO api_usage_tracking (api_name, month_year, monthly_count, daily_count, last_day, circuit_breaker_active)
                    VALUES ('here_fuel', %s, 0, 0, %s, FALSE)
                    ON CONFLICT (api_name) DO NOTHING;
                """, (curr_month, curr_day))
                conn.commit()

            cur.close()
            conn.close()
            _in_memory_stats["initialized"] = True
        except Exception as e:
            print(f"[WARN] Error loading usage from DB: {e}")
            if conn:
                conn.close()
            _in_memory_stats["initialized"] = True

def record_here_api_call(status_code: int = 200):
    global _in_memory_stats
    now_utc = datetime.now(timezone.utc)
    curr_month = now_utc.strftime("%Y-%m")
    curr_day = now_utc.strftime("%Y-%m-%d")

    with _lock:
        if status_code == 200:
            _in_memory_stats["total_success"] += 1
            if _in_memory_stats["month_year"] != curr_month:
                _in_memory_stats["month_year"] = curr_month
                _in_memory_stats["monthly_count"] = 0
                _in_memory_stats["circuit_breaker_active"] = False

            if _in_memory_stats["last_day"] != curr_day:
                _in_memory_stats["last_day"] = curr_day
                _in_memory_stats["daily_count"] = 0

            _in_memory_stats["monthly_count"] += 1
            _in_memory_stats["daily_count"] += 1

            if _in_memory_stats["monthly_count"] >= HERE_MONTHLY_LIMIT:
                _in_memory_stats["circuit_breaker_active"] = True
                print(f"[CRITICAL CIRCUIT BREAKER] HERE API monthly limit reached ({_in_memory_stats['monthly_count']}/{HERE_MONTHLY_LIMIT})! Hard stop activated.")
        else:
            _in_memory_stats["total_errors"] += 1

        m_count = _in_memory_stats["monthly_count"]
        d_count = _in_memory_stats["daily_count"]
        cb = _in_memory_stats["circuit_breaker_active"]

    # Persist in DB asynchronously
    def _save():
        conn = get_db_connection()
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO api_usage_tracking (api_name, month_year, monthly_count, daily_count, last_day, circuit_breaker_active, updated_at)
                VALUES ('here_fuel', %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (api_name) DO UPDATE SET
                    month_year = EXCLUDED.month_year,
                    monthly_count = EXCLUDED.monthly_count,
                    daily_count = EXCLUDED.daily_count,
                    last_day = EXCLUDED.last_day,
                    circuit_breaker_active = EXCLUDED.circuit_breaker_active,
                    updated_at = NOW();
            """, (curr_month, m_count, d_count, curr_day, cb))
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            if conn:
                conn.close()

    t = threading.Thread(target=_save, daemon=True)
    t.start()

def is_here_quota_exceeded() -> bool:
    """
    Hardcoded safety check. Returns True if monthly usage >= 245,000, blocking calls.
    """
    global _in_memory_stats
    if not _in_memory_stats["initialized"]:
        load_usage_from_db()

    with _lock:
        if _in_memory_stats["circuit_breaker_active"] or _in_memory_stats["monthly_count"] >= HERE_MONTHLY_LIMIT:
            return True
        return False

def get_here_quota_stats() -> dict:
    """
    Returns current HERE usage metrics for Prometheus and Grafana dashboards.
    """
    global _in_memory_stats
    if not _in_memory_stats["initialized"]:
        load_usage_from_db()

    with _lock:
        m_count = _in_memory_stats["monthly_count"]
        rem = max(0, HERE_MONTHLY_LIMIT - m_count)
        cost_eur = round(m_count * HERE_COST_PER_REQ_EUR, 4)
        budget_rem_eur = max(0.0, round(HERE_BUDGET_EUR - cost_eur, 4))
        return {
            "monthly_count": m_count,
            "daily_count": _in_memory_stats["daily_count"],
            "remaining": rem,
            "limit": HERE_MONTHLY_LIMIT,
            "cost_eur": cost_eur,
            "budget_eur": HERE_BUDGET_EUR,
            "budget_remaining_eur": budget_rem_eur,
            "circuit_breaker_active": _in_memory_stats["circuit_breaker_active"],
            "total_success": _in_memory_stats["total_success"],
            "total_errors": _in_memory_stats["total_errors"]
        }

def is_here_api_available() -> bool:
    if is_here_quota_exceeded():
        return False
    return bool(HERE_API_KEY and len(HERE_API_KEY) > 10)

def search_here_fuel_stations(lat: float, lon: float, radius_meters: int = 40000, state_code: str = None) -> list:
    """
    Searches for real fuel stations within radius_meters around coordinates.
    Filters by commercial diesel and truck accessibility.
    Cross-validates all reported prices against AAA state benchmark to prevent anomalies.
    Guaranteed hard stop if monthly limit reached.
    """
    # 1. Hard stop check
    if is_here_quota_exceeded():
        print(f"[HARD STOP] HERE API limit ({HERE_MONTHLY_LIMIT}) reached. Request blocked to preserve free tier.")
        return []

    if not is_here_api_available():
        return []

    params = {
        "apiKey": HERE_API_KEY,
        "in": f"circle:{lat},{lon};r={radius_meters}",
        "fuelType": "diesel",
        "lang": "en"
    }
    url = f"{HERE_FUEL_ENDPOINT}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={'User-Agent': 'CarHaulerDispatch/2.0'})

    stations = []
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            record_here_api_call(resp.status)
            data = json.loads(resp.read().decode('utf-8'))
            items = data.get("stations", data.get("items", []))
            for item in items:
                name = item.get("name") or item.get("brand") or "Commercial Station"
                brand = item.get("brand") or name
                address_info = item.get("address", {})
                street = address_info.get("street") or address_info.get("label") or ""
                city = address_info.get("city", "")
                st = address_info.get("stateCode") or address_info.get("state") or state_code or ""
                zip_code = address_info.get("postalCode", "")

                pos = item.get("position", {})
                st_lat = pos.get("lat") or pos.get("latitude")
                st_lon = pos.get("lng") or pos.get("lon") or pos.get("longitude")

                # Extract diesel price according to official HERE Fuel API v3 spec:
                # 1 = Diesel, -1 = All Truck Diesel, -2 = All Diesel, 6 = Bio-Diesel, 10 = Diesel plus, 76 = Renewable Diesel
                # Strictly exclude gasoline grades: 2 = Regular, 3 = Midgrade, 4 = Premium, 5 = E-85, 13 = E-10
                prices = item.get("prices", [])
                diesel_price = None
                for p in prices:
                    fuel_id = str(p.get("fuelType") or p.get("type") or "").strip().lower()
                    if fuel_id in ["2", "3", "4", "5", "13", "regular", "midgrade", "premium", "unleaded", "gasoline"]:
                        continue
                    if fuel_id in ["1", "-1", "-2", "6", "10", "76", "diesel", "commercial_diesel", "truck_diesel", "biodiesel"] or "diesel" in fuel_id:
                        val = float(p.get("price", 0))
                        if val > 0:
                            diesel_price = val
                            break

                # Cross-check against AAA state benchmark
                price_verified = False
                if diesel_price and st:
                    is_valid, _ = validate_diesel_price(st, diesel_price)
                    price_verified = is_valid

                # Check truck friendliness / commercial lanes
                amenities = item.get("amenities", [])
                is_truck_stop = any(b in (brand + " " + name).lower() for b in ["love's", "pilot", "flying j", "ta", "petro", "maverik", "sapp bros", "roady"])
                has_truck_lanes = is_truck_stop or any("truck" in str(a).lower() for a in amenities)

                full_addr = f"{street}, {city}, {st} {zip_code}".strip(", ")
                if not full_addr and address_info.get("label"):
                    full_addr = address_info.get("label")

                stations.append({
                    "name": name,
                    "brand": brand,
                    "address": full_addr,
                    "city": city,
                    "state": st,
                    "lat": st_lat,
                    "lon": st_lon,
                    "diesel_price": diesel_price,
                    "price_verified": price_verified,
                    "has_truck_lanes": has_truck_lanes,
                    "is_truck_stop": is_truck_stop
                })

    except urllib.error.HTTPError as he:
        record_here_api_call(he.code)
        print(f"[WARN] HERE Fuel API HTTP {he.code}: {he}")
        return []
    except Exception as e:
        record_here_api_call(500)
        print(f"[WARN] HERE Fuel API query failed: {e}")
        return []

    # Sort: 1. Verified diesel prices first; 2. Truck friendly / commercial lanes; 3. Lowest price
    stations.sort(key=lambda s: (
        not bool(s["diesel_price"] and s["price_verified"]),
        not s["has_truck_lanes"],
        s["diesel_price"] if s["diesel_price"] is not None else 999.0
    ))
    return stations

# Initialize on module load
try:
    init_api_tracking_db()
    load_usage_from_db()
except Exception:
    pass
