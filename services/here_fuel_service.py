"""
HERE Technologies Fuel Prices API Service (v3)
Provides real-time station-level fuel pricing and commercial truck accessibility verification.
Docs: https://developer.here.com/documentation/fuel-prices/dev_guide/topics/introduction.html
Free Tier: 250,000 transactions / month on Base Plan.
"""

import os
import json
import urllib.request
import urllib.parse
from services.aaa_fuel_feed import validate_diesel_price, get_state_diesel_benchmark

HERE_API_KEY = os.environ.get("HERE_API_KEY", "")
HERE_FUEL_ENDPOINT = "https://fuel.hereapi.com/v3/stations"

def is_here_api_available() -> bool:
    return bool(HERE_API_KEY and len(HERE_API_KEY) > 10)

def search_here_fuel_stations(lat: float, lon: float, radius_meters: int = 40000, state_code: str = None) -> list:
    """
    Searches for real fuel stations within radius_meters around coordinates.
    Filters by commercial diesel and truck accessibility.
    Cross-validates all reported prices against AAA state benchmark to prevent anomalies.
    """
    if not is_here_api_available():
        return []

    # in=circle:latitude,longitude;r=radius_in_meters
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
            data = json.loads(resp.read().decode('utf-8'))
            items = data.get("stations", data.get("items", []))
            for item in items:
                name = item.get("name") or item.get("brand") or "Commercial Station"
                brand = item.get("brand") or name
                address_info = item.get("address", {})
                street = address_info.get("street") or address_info.get("label") or ""
                city = address_info.get("city", "")
                st = address_info.get("stateCode") or state_code or ""
                zip_code = address_info.get("postalCode", "")
                
                # Coordinates
                pos = item.get("position", {})
                st_lat = pos.get("lat") or pos.get("latitude")
                st_lon = pos.get("lng") or pos.get("lon") or pos.get("longitude")

                # Extract diesel price
                prices = item.get("prices", [])
                diesel_price = None
                for p in prices:
                    fuel_id = (p.get("fuelType") or p.get("type") or "").lower()
                    if "diesel" in fuel_id:
                        diesel_price = float(p.get("price", 0))
                        break

                # Cross-check against AAA state benchmark if price is present
                price_verified = False
                if diesel_price and st:
                    is_valid, _ = validate_diesel_price(st, diesel_price)
                    price_verified = is_valid
                
                # Check truck friendliness / commercial lanes
                amenities = item.get("amenities", [])
                is_truck_stop = any(b in (brand + " " + name).lower() for b in ["love's", "pilot", "flying j", "ta", "petro", "maverik", "sapp bros", "roady"])
                has_truck_lanes = is_truck_stop or any("truck" in str(a).lower() for a in amenities)

                full_addr = f"{street}, {city}, {st} {zip_code}".strip(", ")

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

    except Exception as e:
        print(f"[WARN] HERE Fuel API query failed: {e}")
        return []

    # Sort prioritizing truck stops and stations with verified prices
    stations.sort(key=lambda s: (s["has_truck_lanes"], s["price_verified"], -(s["diesel_price"] or 999)), reverse=True)
    return stations
