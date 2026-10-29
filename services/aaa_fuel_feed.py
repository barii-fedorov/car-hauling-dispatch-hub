"""
AAA State Diesel Feed Service
Scrapes and caches official daily on-highway retail fuel averages per state from AAA (American Automobile Association).
Maintains PostgreSQL table 'state_fuel_prices' and an in-memory cache.
Provides ground-truth price bounds for verifying fuel station data across all 50 states.
"""

import os
import re
import time
import urllib.request
try:
    import psycopg2
except ImportError:
    psycopg2 = None
from datetime import datetime, timezone

PG_HOST = os.environ.get("POSTGRES_HOST", "postgres")
PG_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
PG_USER = os.environ.get("POSTGRES_USER", "dispatch_admin")
PG_PASS = os.environ.get("POSTGRES_PASSWORD", "DispatchSecurePass2026!_pg")
PG_DB = os.environ.get("POSTGRES_DB", "dispatch_hub")

# In-memory cache: { "OR": {"name": "Oregon", "diesel": 6.74, "regular": 4.84, "updated_at": ts} }
_MEMORY_CACHE = {}
_LAST_SYNC_TS = 0
CACHE_TTL_SECONDS = 3600 * 6  # 6 hours

US_STATE_NAME_TO_CODE = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "district of columbia": "DC",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY"
}

def get_db_connection():
    try:
        return psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB)
    except Exception as e:
        print(f"[WARN] DB connection failed in aaa_fuel_feed: {e}")
        return None

def init_state_fuel_table():
    """Creates the state_fuel_prices table in PostgreSQL if it doesn't exist."""
    conn = get_db_connection()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS state_fuel_prices (
                state_code VARCHAR(8) PRIMARY KEY,
                state_name VARCHAR(64) NOT NULL,
                diesel_price NUMERIC(5,3) NOT NULL,
                regular_price NUMERIC(5,3),
                source VARCHAR(32) DEFAULT 'AAA',
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_state_fuel_updated ON state_fuel_prices(updated_at);
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[WARN] init_state_fuel_table error: {e}")
        if conn:
            conn.close()

def fetch_live_aaa_prices() -> dict:
    """
    Scrapes official daily state gas & diesel price averages from AAA.
    Returns dict: { "OR": {"name": "Oregon", "diesel": 6.736, "regular": 4.836}, ... }
    """
    url = "https://gasprices.aaa.com/state-gas-price-averages/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    results = {}

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode('utf-8')
            matches = re.findall(
                r'<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>',
                html,
                re.DOTALL
            )
            for m in matches:
                st_name_raw = re.sub(r'<[^>]+>', '', m[0]).strip()
                reg_raw = re.sub(r'[^\d.]', '', m[1]).strip()
                dsl_raw = re.sub(r'[^\d.]', '', m[4]).strip()

                st_code = US_STATE_NAME_TO_CODE.get(st_name_raw.lower())
                if st_code and dsl_raw:
                    try:
                        results[st_code] = {
                            "code": st_code,
                            "name": st_name_raw,
                            "diesel": float(dsl_raw),
                            "regular": float(reg_raw) if reg_raw else None
                        }
                    except ValueError:
                        continue
    except Exception as e:
        print(f"[WARN] Failed to scrape AAA gas prices: {e}")

    return results

def sync_state_fuel_prices(force=False) -> bool:
    """
    Synchronizes AAA state prices to PostgreSQL and updates memory cache.
    """
    global _MEMORY_CACHE, _LAST_SYNC_TS

    now = time.time()
    if not force and _MEMORY_CACHE and (now - _LAST_SYNC_TS < CACHE_TTL_SECONDS):
        return True

    live_data = fetch_live_aaa_prices()
    if not live_data:
        # Try loading from DB into memory cache
        return _load_cache_from_db()

    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            for st_code, item in live_data.items():
                cur.execute("""
                    INSERT INTO state_fuel_prices (state_code, state_name, diesel_price, regular_price, source, updated_at)
                    VALUES (%s, %s, %s, %s, 'AAA', NOW())
                    ON CONFLICT (state_code) DO UPDATE
                    SET diesel_price = EXCLUDED.diesel_price,
                        regular_price = EXCLUDED.regular_price,
                        updated_at = NOW();
                """, (st_code, item["name"], item["diesel"], item["regular"]))
            conn.commit()
            cur.close()
            conn.close()
            print(f"[OK] Synced {len(live_data)} state fuel averages from AAA to DB.")
        except Exception as e:
            print(f"[WARN] Error saving AAA fuel data to DB: {e}")
            if conn:
                conn.close()

    _MEMORY_CACHE = live_data
    _LAST_SYNC_TS = now
    return True

def _load_cache_from_db() -> bool:
    global _MEMORY_CACHE, _LAST_SYNC_TS
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("SELECT state_code, state_name, diesel_price, regular_price, updated_at FROM state_fuel_prices;")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        for r in rows:
            _MEMORY_CACHE[r[0]] = {
                "code": r[0],
                "name": r[1],
                "diesel": float(r[2]),
                "regular": float(r[3]) if r[3] else None
            }
        _LAST_SYNC_TS = time.time()
        print(f"[OK] Loaded {len(_MEMORY_CACHE)} state fuel records from DB cache.")
        return bool(_MEMORY_CACHE)
    except Exception as e:
        print(f"[WARN] Error loading state fuel cache from DB: {e}")
        if conn:
            conn.close()
        return False

def get_state_diesel_benchmark(state_or_code: str) -> dict:
    """
    Returns official certified AAA state diesel benchmark:
    { "code": "OR", "name": "Oregon", "diesel": 6.74, "range_low": 6.40, "range_high": 7.10 }
    """
    global _MEMORY_CACHE
    if not _MEMORY_CACHE:
        sync_state_fuel_prices()

    if not state_or_code:
        return None

    cleaned = state_or_code.strip()
    st_code = cleaned.upper() if len(cleaned) == 2 else US_STATE_NAME_TO_CODE.get(cleaned.lower())

    if not st_code or st_code not in _MEMORY_CACHE:
        # Fallback to national average if unknown state
        return {
            "code": st_code or "US",
            "name": state_or_code,
            "diesel": 6.25,
            "range_low": 5.95,
            "range_high": 6.55,
            "is_default": True
        }

    item = _MEMORY_CACHE[st_code]
    diesel_avg = item["diesel"]
    # Realistic truck stop corridor variance (+/- 5% to 7% for retail truck stop lanes vs discount stations)
    return {
        "code": st_code,
        "name": item["name"],
        "diesel": diesel_avg,
        "range_low": round(diesel_avg * 0.95, 2),
        "range_high": round(diesel_avg * 1.06, 2),
        "is_default": False
    }

def validate_diesel_price(state_code: str, price: float) -> tuple[bool, str]:
    """
    Sense-check validator: Checks if a reported diesel price is realistic for the state.
    Returns (is_valid: bool, reason: str)
    """
    bench = get_state_diesel_benchmark(state_code)
    if not bench:
        return True, "No benchmark"

    avg = bench["diesel"]
    min_reasonable = avg * 0.75  # Cannot be >25% below official state average even with big fleet discount
    max_reasonable = avg * 1.35  # Cannot be >35% above state average

    if price < min_reasonable:
        return False, f"Цена ${price:.2f} слишком низкая (галлюцинация). Официальный средний по {bench['name']} — ${avg:.2f}/gal."
    if price > max_reasonable:
        return False, f"Цена ${price:.2f} завышена. Официальный средний по {bench['name']} — ${avg:.2f}/gal."

    return True, "OK"
